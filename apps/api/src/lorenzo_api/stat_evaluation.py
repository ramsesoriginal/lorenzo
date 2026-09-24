"""Evaluating computed stats - see ADR 0104/RFC 0016.

v_effective_stat decides, per entity and stat, which candidate wins: a
stored value or a formula (ADR 0037's closest-hop rule). When a formula
wins, its row carries no value; `evaluate` computes it here, against the
resolved stats of the entity being read - not the ancestor that holds the
formula, so a prototype's `strength_modifier` uses each instance's own
strength.

There is no interpreter: each formula kind is a fixed function with
parameters. Formulas can read other computed stats, so evaluation follows
dependencies, memoized. A computed stat whose inputs don't resolve has no
value, like an unset stat. Evaluation never raises on bad data: a cycle
that slipped past the write-time check (routers/computed_stats.py) just
leaves the stats involved without a value.

Pure Python, no database access: callers eager-load
`effective_stats -> stat_definition` and
`effective_stats -> computed_stat -> linear/comparison` first.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from lorenzo_api.models import (
    Comparator,
    ComputedStat,
    RoundMode,
    StatValueType,
    VEffectiveStat,
)

Value = int | float | str | bool

_ROUNDING = {
    RoundMode.FLOOR: ROUND_FLOOR,
    RoundMode.CEIL: ROUND_CEILING,
    RoundMode.ROUND: ROUND_HALF_UP,
    RoundMode.TRUNCATE: ROUND_DOWN,
}


@dataclass(frozen=True, slots=True)
class LinearFormula:
    source_stat_definition_id: uuid.UUID
    multiplier: Decimal
    offset: Decimal
    round_mode: RoundMode


@dataclass(frozen=True, slots=True)
class ComparisonFormula:
    left_stat_definition_id: uuid.UUID
    comparator: Comparator
    right_stat_definition_id: uuid.UUID | None
    right_constant: Decimal | None
    true_value: str | None
    false_value: str | None


Formula = LinearFormula | ComparisonFormula


def formula_of(computed: ComputedStat) -> Formula | None:
    """The plain formula a stored computed_stat row describes, or None if
    neither concrete row exists (data inserted around the API)."""
    if computed.linear is not None:
        row = computed.linear
        return LinearFormula(
            source_stat_definition_id=row.source_stat_definition_id,
            multiplier=row.multiplier,
            offset=row.offset,
            round_mode=RoundMode(row.round_mode),
        )
    if computed.comparison is not None:
        cmp = computed.comparison
        return ComparisonFormula(
            left_stat_definition_id=cmp.left_stat_definition_id,
            comparator=Comparator(cmp.comparator),
            right_stat_definition_id=cmp.right_stat_definition_id,
            right_constant=cmp.right_constant,
            true_value=cmp.true_value,
            false_value=cmp.false_value,
        )
    return None


def input_ids(formula: Formula) -> list[uuid.UUID]:
    """The stats a formula reads."""
    if isinstance(formula, LinearFormula):
        return [formula.source_stat_definition_id]
    ids = [formula.left_stat_definition_id]
    if formula.right_stat_definition_id is not None:
        ids.append(formula.right_stat_definition_id)
    return ids


def stored_value(stat: VEffectiveStat) -> Value | None:
    """The value a stored winner holds, by its definition's value_type
    (an enum value is stored as text, ADR 0103)."""
    value_type = stat.stat_definition.value_type
    if value_type is StatValueType.INT:
        return stat.value_int
    if value_type in (StatValueType.TEXT, StatValueType.ENUM):
        return stat.value_text
    if value_type is StatValueType.FLOAT:
        return stat.value_float
    if value_type is StatValueType.BOOL:
        return stat.value_bool
    return None


def _number(value: Value | None) -> Decimal | None:
    """Only int/float operands count - bool is an int subclass in Python
    but never a number here."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return Decimal(str(value))


def apply_linear(
    formula: LinearFormula, source: Value | None, target_type: StatValueType
) -> Value | None:
    number = _number(source)
    if number is None:
        return None
    result = number * formula.multiplier + formula.offset
    if formula.round_mode is not RoundMode.NONE:
        result = result.quantize(Decimal(1), rounding=_ROUNDING[formula.round_mode])
    if target_type is StatValueType.INT:
        if result != result.to_integral_value():
            return None  # write-time checks make this unreachable via the API
        return int(result)
    if target_type is StatValueType.FLOAT:
        return float(result)
    return None


def apply_comparison(
    formula: ComparisonFormula, left: Value | None, right: Value | None, target_type: StatValueType
) -> Value | None:
    left_number = _number(left)
    right_number = (
        formula.right_constant if formula.right_stat_definition_id is None else _number(right)
    )
    if left_number is None or right_number is None:
        return None
    outcome = {
        Comparator.LT: left_number < right_number,
        Comparator.LE: left_number <= right_number,
        Comparator.EQ: left_number == right_number,
        Comparator.NE: left_number != right_number,
        Comparator.GE: left_number >= right_number,
        Comparator.GT: left_number > right_number,
    }[formula.comparator]
    if target_type is StatValueType.BOOL:
        return outcome
    if target_type in (StatValueType.TEXT, StatValueType.ENUM):
        return formula.true_value if outcome else formula.false_value
    return None


def apply_formula(
    formula: Formula, resolve: Callable[[uuid.UUID], Value | None], target_type: StatValueType
) -> Value | None:
    if isinstance(formula, LinearFormula):
        return apply_linear(formula, resolve(formula.source_stat_definition_id), target_type)
    right = (
        resolve(formula.right_stat_definition_id)
        if formula.right_stat_definition_id is not None
        else None
    )
    return apply_comparison(formula, resolve(formula.left_stat_definition_id), right, target_type)


def evaluate(
    stats: Iterable[VEffectiveStat],
    *,
    overrides: Mapping[uuid.UUID, tuple[Formula, StatValueType]] | None = None,
) -> dict[uuid.UUID, Value]:
    """Every resolvable stat's value, by stat_definition_id. A stat with
    no value (unset inputs, or caught in a cycle) is absent.

    `overrides` replaces - or adds - a stat's formula for this one call
    only, without it being saved: the dry-run preview (ADR 0104).
    """
    by_id = {stat.stat_definition_id: stat for stat in stats}
    overrides = overrides or {}
    values: dict[uuid.UUID, Value | None] = {}
    visiting: set[uuid.UUID] = set()

    def resolve(stat_definition_id: uuid.UUID) -> Value | None:
        if stat_definition_id in values:
            return values[stat_definition_id]
        if stat_definition_id in visiting:
            return None  # a cycle: nothing in it resolves
        value: Value | None = None
        override = overrides.get(stat_definition_id)
        stat = by_id.get(stat_definition_id)
        if override is not None:
            visiting.add(stat_definition_id)
            value = apply_formula(override[0], resolve, override[1])
            visiting.discard(stat_definition_id)
        elif stat is not None and stat.computed_entity_id is None:
            value = stored_value(stat)
        elif stat is not None and stat.computed_stat is not None:
            formula = formula_of(stat.computed_stat)
            if formula is not None:
                visiting.add(stat_definition_id)
                value = apply_formula(formula, resolve, stat.stat_definition.value_type)
                visiting.discard(stat_definition_id)
        values[stat_definition_id] = value
        return value

    for stat_definition_id in [*by_id, *overrides]:
        resolve(stat_definition_id)
    return {key: value for key, value in values.items() if value is not None}
