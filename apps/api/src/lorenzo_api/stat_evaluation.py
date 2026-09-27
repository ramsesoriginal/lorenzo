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

A contents formula (ADR 0127) reads a stat of each thing directly inside
the entity, so evaluation can span entities: the caller hands over a
`Contents` with what's inside and their stats (stat_contents.py loads it).

Pure Python, no database access: callers eager-load
`effective_stats -> stat_definition` and
`effective_stats -> computed_stat -> <its kind>` first
(models.formula_load_options).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
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


@dataclass(frozen=True, slots=True)
class SumTerm:
    source_stat_definition_id: uuid.UUID
    coefficient: Decimal


@dataclass(frozen=True, slots=True)
class SumFormula:
    """`round(Σ coefficient × stat + offset)` - ADR 0126."""

    terms: tuple[SumTerm, ...]
    offset: Decimal
    round_mode: RoundMode


@dataclass(frozen=True, slots=True)
class ContentsFormula:
    """`Σ stat × quantity` over what's directly inside - ADR 0127."""

    source_stat_definition_id: uuid.UUID


Formula = LinearFormula | ComparisonFormula | SumFormula | ContentsFormula


@dataclass(frozen=True, slots=True)
class Contents:
    """What contents formulas read (ADR 0127): the effective stats of
    every entity in a containment subtree, and what's directly inside each,
    with its stack count."""

    stats: Mapping[uuid.UUID, Sequence[VEffectiveStat]]
    children: Mapping[uuid.UUID, Sequence[tuple[uuid.UUID, int]]]


class _Cycle:
    """A stat caught in, or depending on, a cycle of formulas or of
    containment. Distinct from "no value", which a contents formula counts
    as 0; a cycle it can't."""


_CYCLE = _Cycle()
_Resolved = Value | None | _Cycle


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
    if computed.sum is not None:
        row_sum = computed.sum
        return SumFormula(
            terms=tuple(
                SumTerm(
                    source_stat_definition_id=term.source_stat_definition_id,
                    coefficient=term.coefficient,
                )
                for term in row_sum.terms
            ),
            offset=row_sum.offset,
            round_mode=RoundMode(row_sum.round_mode),
        )
    if computed.contents is not None:
        return ContentsFormula(
            source_stat_definition_id=computed.contents.source_stat_definition_id
        )
    return None


def input_ids(formula: Formula) -> list[uuid.UUID]:
    """The stats a formula reads - for a contents formula, on each thing
    inside."""
    if isinstance(formula, LinearFormula | ContentsFormula):
        return [formula.source_stat_definition_id]
    if isinstance(formula, SumFormula):
        return [term.source_stat_definition_id for term in formula.terms]
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


def _rounded(result: Decimal, round_mode: RoundMode, target_type: StatValueType) -> Value | None:
    """A linear or sum result, rounded and typed for its target stat."""
    if round_mode is not RoundMode.NONE:
        result = result.quantize(Decimal(1), rounding=_ROUNDING[round_mode])
    if target_type is StatValueType.INT:
        if result != result.to_integral_value():
            return None  # write-time checks make this unreachable via the API
        return int(result)
    if target_type is StatValueType.FLOAT:
        return float(result)
    return None


def apply_linear(
    formula: LinearFormula, source: Value | None, target_type: StatValueType
) -> Value | None:
    number = _number(source)
    if number is None:
        return None
    return _rounded(number * formula.multiplier + formula.offset, formula.round_mode, target_type)


def apply_sum(
    formula: SumFormula, sources: list[Value | None], target_type: StatValueType
) -> Value | None:
    """Every term's stat must have a value, as a linear formula's source
    must (ADR 0104, 0126)."""
    result = formula.offset
    for term, source in zip(formula.terms, sources, strict=True):
        number = _number(source)
        if number is None:
            return None
        result += term.coefficient * number
    return _rounded(result, formula.round_mode, target_type)


def always_whole(
    coefficients: Iterable[Decimal], offset: Decimal, input_types: Iterable[StatValueType]
) -> bool:
    """Whether a linear or sum formula can only ever produce a whole number:
    every input an int stat, every coefficient (or multiplier) and the
    offset whole. An int stat needs no rounding mode then (ADR 0126)."""
    return all(value_type is StatValueType.INT for value_type in input_types) and all(
        number == number.to_integral_value() for number in (*coefficients, offset)
    )


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


def same_entity_input_ids(formula: Formula) -> list[uuid.UUID]:
    """The stats of the same entity a formula reads: its edges in the
    definition-level cycle check (ADR 0104). A contents formula has none -
    it reads a level down (ADR 0127)."""
    return [] if isinstance(formula, ContentsFormula) else input_ids(formula)


def apply_formula(
    formula: LinearFormula | ComparisonFormula | SumFormula,
    resolve: Callable[[uuid.UUID], Value | None],
    target_type: StatValueType,
) -> Value | None:
    if isinstance(formula, LinearFormula):
        return apply_linear(formula, resolve(formula.source_stat_definition_id), target_type)
    if isinstance(formula, SumFormula):
        return apply_sum(
            formula,
            [resolve(term.source_stat_definition_id) for term in formula.terms],
            target_type,
        )
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
    entity_id: uuid.UUID | None = None,
    contents: Contents | None = None,
) -> dict[uuid.UUID, Value]:
    """Every resolvable stat's value, by stat_definition_id, for the entity
    `stats` belong to. A stat with no value (unset inputs, or caught in a
    cycle) is absent.

    `overrides` replaces - or adds - a stat's formula for this one call
    only, without it being saved: the dry-run preview (ADR 0104).
    `contents` is what a contents formula reads, with `entity_id` naming
    the entity inside it; without them, a contents formula has no value
    (ADR 0127).
    """
    evaluation = _Evaluation(entity_id, stats, overrides or {}, contents)
    for stat_definition_id in [*evaluation.rows_of(entity_id), *(overrides or {})]:
        evaluation.resolve(entity_id, stat_definition_id)
    return {
        stat_definition_id: value
        for (holder, stat_definition_id), value in evaluation.values.items()
        if holder == entity_id and value is not None and not isinstance(value, _Cycle)
    }


class _Evaluation:
    """One evaluate() call: memoized by (entity, stat), since a contents
    formula resolves stats of the things inside too."""

    def __init__(
        self,
        entity_id: uuid.UUID | None,
        stats: Iterable[VEffectiveStat],
        overrides: Mapping[uuid.UUID, tuple[Formula, StatValueType]],
        contents: Contents | None,
    ) -> None:
        self.root = entity_id
        self.overrides = overrides
        self.contents = contents
        self.rows: dict[uuid.UUID | None, dict[uuid.UUID, VEffectiveStat]] = {
            entity_id: {stat.stat_definition_id: stat for stat in stats}
        }
        self.values: dict[tuple[uuid.UUID | None, uuid.UUID], _Resolved] = {}
        self.visiting: set[tuple[uuid.UUID | None, uuid.UUID]] = set()

    def rows_of(self, entity_id: uuid.UUID | None) -> dict[uuid.UUID, VEffectiveStat]:
        if entity_id not in self.rows:
            loaded = self.contents.stats.get(entity_id, ()) if self.contents and entity_id else ()
            self.rows[entity_id] = {stat.stat_definition_id: stat for stat in loaded}
        return self.rows[entity_id]

    def resolve(self, entity_id: uuid.UUID | None, stat_definition_id: uuid.UUID) -> _Resolved:
        key = (entity_id, stat_definition_id)
        if key in self.values:
            return self.values[key]
        if key in self.visiting:
            return _CYCLE
        stat = self.rows_of(entity_id).get(stat_definition_id)
        formula: tuple[Formula, StatValueType] | None = None
        value: _Resolved = None
        if entity_id == self.root and stat_definition_id in self.overrides:
            formula = self.overrides[stat_definition_id]
        elif stat is not None and stat.computed_entity_id is None:
            value = stored_value(stat)
        elif stat is not None and stat.computed_stat is not None:
            stored = formula_of(stat.computed_stat)
            if stored is not None:
                formula = (stored, stat.stat_definition.value_type)
        if formula is not None:
            self.visiting.add(key)
            value = self._apply(entity_id, *formula)
            self.visiting.discard(key)
        self.values[key] = value
        return value

    def _apply(
        self, entity_id: uuid.UUID | None, formula: Formula, target_type: StatValueType
    ) -> _Resolved:
        if isinstance(formula, ContentsFormula):
            return self._contents(entity_id, formula, target_type)
        inputs: dict[uuid.UUID, Value | None] = {}
        for input_id in input_ids(formula):
            resolved = self.resolve(entity_id, input_id)
            if isinstance(resolved, _Cycle):
                return _CYCLE
            inputs[input_id] = resolved
        return apply_formula(formula, inputs.__getitem__, target_type)

    def _contents(
        self, entity_id: uuid.UUID | None, formula: ContentsFormula, target_type: StatValueType
    ) -> _Resolved:
        """What's inside without the stat, or without a value, counts as 0;
        one caught in a cycle makes the total one too (ADR 0127)."""
        if self.contents is None or entity_id is None:
            return None
        total = Decimal(0)
        for child, quantity in self.contents.children.get(entity_id, ()):
            resolved = self.resolve(child, formula.source_stat_definition_id)
            if isinstance(resolved, _Cycle):
                return _CYCLE
            number = _number(resolved)
            if number is not None:
                total += number * quantity
        return _rounded(total, RoundMode.NONE, target_type)
