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
leaves the stats involved without a value, and so does a chain of formulas
too long to follow (ADR 0443).

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
from dataclasses import dataclass, field
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_UP,
    Context,
    Decimal,
    Inexact,
)

import structlog

from lorenzo_api.models import (
    Comparator,
    ComputedStat,
    RoundMode,
    StatDefinition,
    StatValueType,
    VEffectiveStat,
)

logger = structlog.get_logger(__name__)

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
    """An aggregate of a stat over what's directly inside - ADR 0127, and its options, ADR 0447.
    The default, `Σ stat × quantity`, is ADR 0127's. `aggregate` may be `min`, `max` or `count`
    (which ignores the stat, so `source_stat_definition_id` may be empty then); `only_active`
    skips a held thing whose `active` switch is off, `only_kind` keeps one kind of held thing,
    `where_stat_definition_id` is a `bool` stat that must be true on the held thing, and
    `if_none` is what `min` and `max` of nothing give."""

    source_stat_definition_id: uuid.UUID | None
    aggregate: str = "sum"
    only_active: bool = False
    only_kind: str | None = None
    where_stat_definition_id: uuid.UUID | None = None
    if_none: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Operand:
    """One input of a `min` or `max`: a stat of the same entity, or a constant (ADR 0444)."""

    stat_definition_id: uuid.UUID | None
    constant: Decimal | None


@dataclass(frozen=True, slots=True)
class ExtremumFormula:
    """The smallest (`min`) or the largest (`max`) of two to five operands, rounded as `sum` is -
    ADR 0444. `min(a, cap)` is a cap, `max(a, 0)` a floor."""

    pick: str
    inputs: tuple[Operand, ...]
    round_mode: RoundMode


@dataclass(frozen=True, slots=True)
class ProductFormula:
    """`round(factor₁ × … × factorₙ × multiplier + offset)` - ADR 0445. A flag is a factor of 1
    or 0."""

    factors: tuple[uuid.UUID, ...]
    multiplier: Decimal
    offset: Decimal
    round_mode: RoundMode


@dataclass(frozen=True, slots=True)
class RatioFormula:
    """`round(numerator ÷ denominator × multiplier + offset)`, the denominator a stat or a
    constant - ADR 0445. A zero denominator gives no value."""

    numerator: uuid.UUID
    denominator: Operand
    multiplier: Decimal
    offset: Decimal
    round_mode: RoundMode


@dataclass(frozen=True, slots=True)
class SelectResult:
    """What a select gives: a constant (one of the number, text and flag) or a stat of the same
    entity - ADR 0446."""

    number: Decimal | None = None
    text: str | None = None
    flag: bool | None = None
    stat_definition_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SelectStep:
    """One step of a select: a `from` value (`threshold`) or a value (`match_value`), exactly one
    of the two, and its result - ADR 0446."""

    threshold: Decimal | None
    match_value: str | None
    result: SelectResult


@dataclass(frozen=True, slots=True)
class SelectFormula:
    """A value from a table - ADR 0446. `threshold`: the result of the highest `from` the source
    reaches. `match`: the result of the step whose value the source holds. When none applies,
    `otherwise`, or no value without one."""

    source: uuid.UUID
    mode: str
    steps: tuple[SelectStep, ...]
    otherwise: SelectResult | None


Formula = (
    LinearFormula
    | ComparisonFormula
    | SumFormula
    | ContentsFormula
    | ExtremumFormula
    | ProductFormula
    | RatioFormula
    | SelectFormula
)


@dataclass(frozen=True, slots=True)
class Contents:
    """What contents formulas read (ADR 0127): the effective stats of
    every entity in a containment subtree, and what's directly inside each,
    with its stack count. `held` says, of a thing inside, its kind and whether its `active`
    switch is on (ADR 0447); a thing it does not list has no kind and no switch."""

    stats: Mapping[uuid.UUID, Sequence[VEffectiveStat]]
    children: Mapping[uuid.UUID, Sequence[tuple[uuid.UUID, int]]]
    held: Mapping[uuid.UUID, HeldThing] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HeldThing:
    """What a contents formula asks of a thing inside (ADR 0447): its kind, `item_instance` or
    None for a thing that is not one, and its `active` switch (true for a thing without one)."""

    kind: str | None
    active: bool


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
        held = computed.contents
        return ContentsFormula(
            source_stat_definition_id=held.source_stat_definition_id,
            aggregate=held.aggregate,
            only_active=held.only_active,
            only_kind=held.only_kind,
            where_stat_definition_id=held.where_stat_definition_id,
            if_none=held.if_none,
        )
    if computed.select is not None:
        chosen = computed.select
        return SelectFormula(
            source=chosen.source_stat_definition_id,
            mode=chosen.mode,
            steps=tuple(
                SelectStep(
                    threshold=step.threshold,
                    match_value=step.match_value,
                    result=SelectResult(
                        number=step.result_number,
                        text=step.result_text,
                        flag=step.result_bool,
                        stat_definition_id=step.result_stat_definition_id,
                    ),
                )
                for step in chosen.steps
            ),
            otherwise=(
                SelectResult(
                    number=chosen.otherwise_number,
                    text=chosen.otherwise_text,
                    flag=chosen.otherwise_bool,
                    stat_definition_id=chosen.otherwise_stat_definition_id,
                )
                if (
                    chosen.otherwise_number is not None
                    or chosen.otherwise_text is not None
                    or chosen.otherwise_bool is not None
                    or chosen.otherwise_stat_definition_id is not None
                )
                else None
            ),
        )
    if computed.product is not None:
        product = computed.product
        return ProductFormula(
            factors=tuple(factor.source_stat_definition_id for factor in product.factors),
            multiplier=product.multiplier,
            offset=product.offset,
            round_mode=RoundMode(product.round_mode),
        )
    if computed.ratio is not None:
        ratio = computed.ratio
        return RatioFormula(
            numerator=ratio.numerator_stat_definition_id,
            denominator=Operand(
                stat_definition_id=ratio.denominator_stat_definition_id,
                constant=ratio.denominator_constant,
            ),
            multiplier=ratio.multiplier,
            offset=ratio.offset,
            round_mode=RoundMode(ratio.round_mode),
        )
    if computed.extremum is not None:
        extremum = computed.extremum
        return ExtremumFormula(
            pick=extremum.pick,
            inputs=tuple(
                Operand(
                    stat_definition_id=operand.source_stat_definition_id,
                    constant=operand.constant,
                )
                for operand in extremum.inputs
            ),
            round_mode=RoundMode(extremum.round_mode),
        )
    return None


def input_ids(formula: Formula) -> list[uuid.UUID]:
    """The stats a formula reads - for a contents formula, on each thing
    inside: its stat, when it has one, and the stat it filters by."""
    if isinstance(formula, ContentsFormula):
        return [
            i
            for i in (formula.source_stat_definition_id, formula.where_stat_definition_id)
            if i is not None
        ]
    if isinstance(formula, LinearFormula):
        return [formula.source_stat_definition_id]
    if isinstance(formula, SumFormula):
        return [term.source_stat_definition_id for term in formula.terms]
    if isinstance(formula, ExtremumFormula):
        return [
            operand.stat_definition_id
            for operand in formula.inputs
            if operand.stat_definition_id is not None
        ]
    if isinstance(formula, ProductFormula):
        return list(formula.factors)
    if isinstance(formula, SelectFormula):
        results = [step.result for step in formula.steps]
        if formula.otherwise is not None:
            results.append(formula.otherwise)
        return [formula.source] + [
            r.stat_definition_id for r in results if r.stat_definition_id is not None
        ]
    if isinstance(formula, RatioFormula):
        ids = [formula.numerator]
        if formula.denominator.stat_definition_id is not None:
            ids.append(formula.denominator.stat_definition_id)
        return ids
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


def numeric_value(value: Value | None, definition: StatDefinition | None) -> Value | None:
    """What a formula reads of a stat's value (ADR 0444): a bool is 1 or 0 and an enum is the
    `sort_order` of the value it holds, a value its enum no longer allows has no number. Any other
    value is as it is. An enum's values are loaded with its definition."""
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, str):
        return value
    if definition is None or definition.value_type is not StatValueType.ENUM:
        return value
    return next((row.sort_order for row in definition.enum_values if row.value == value), None)


def picked_operand(
    formula: ExtremumFormula, read: Callable[[uuid.UUID], Value | None]
) -> int | None:
    """The position of the operand a `min` or `max` took, the first one when several tie, or None
    when an input has no value (ADR 0444). `read` is a stat's value as a formula reads it
    (`numeric_value`)."""
    numbers: list[Decimal] = []
    for operand in formula.inputs:
        number = (
            operand.constant
            if operand.stat_definition_id is None
            else _number(read(operand.stat_definition_id))
        )
        if number is None:
            return None
        numbers.append(number)
    target = min(numbers) if formula.pick == "min" else max(numbers)
    return numbers.index(target)


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


_WHOLE_TYPES = (StatValueType.INT, StatValueType.BOOL, StatValueType.ENUM)


def apply_extremum(
    formula: ExtremumFormula,
    resolve: Callable[[uuid.UUID], Value | None],
    target_type: StatValueType,
) -> Value | None:
    """Every stat operand must have a value, as a sum's terms must; the result is the smallest or
    the largest operand, so it is whole when every operand is (ADR 0444)."""
    numbers: list[Decimal] = []
    for operand in formula.inputs:
        if operand.stat_definition_id is None:
            assert operand.constant is not None
            numbers.append(operand.constant)
            continue
        number = _number(resolve(operand.stat_definition_id))
        if number is None:
            return None
        numbers.append(number)
    result = min(numbers) if formula.pick == "min" else max(numbers)
    return _rounded(result, formula.round_mode, target_type)


def choose_step(
    formula: SelectFormula, raw: Value | None, definition: StatDefinition | None
) -> int | None:
    """The position of the step a select takes for the value its source holds, or None when no
    step applies (ADR 0446). `threshold`: the step with the highest `from` the source's number
    reaches (a bool is 1 or 0, an enum its `sort_order`, ADR 0444). `match`: the step whose value
    the source holds."""
    if raw is None:
        return None
    if formula.mode == "match":
        for position, step in enumerate(formula.steps):
            if step.match_value is not None and step.match_value == raw:
                return position
        return None
    number = _number(numeric_value(raw, definition))
    if number is None:
        return None
    best: int | None = None
    for position, step in enumerate(formula.steps):
        if step.threshold is None or step.threshold > number:
            continue
        if best is None or step.threshold > (formula.steps[best].threshold or Decimal(0)):
            best = position
    return best


def apply_product(
    formula: ProductFormula,
    resolve: Callable[[uuid.UUID], Value | None],
    target_type: StatValueType,
) -> Value | None:
    """Every factor must have a value, as a sum's terms must (ADR 0445)."""
    result = Decimal(1)
    for factor in formula.factors:
        number = _number(resolve(factor))
        if number is None:
            return None
        result *= number
    return _rounded(result * formula.multiplier + formula.offset, formula.round_mode, target_type)


_RATIO_PRECISION = 28
"""The digits a quotient keeps (ADR 0445): Python's default, spelled out so a change of the
thread's context cannot change what a formula says."""


def divide(numerator: Decimal, denominator: Decimal) -> tuple[Decimal, bool] | None:
    """The quotient at the ratio precision and whether that rounded it, or None for a zero
    denominator."""
    if denominator == 0:
        return None
    context = Context(prec=_RATIO_PRECISION)
    quotient = context.divide(numerator, denominator)
    return quotient, bool(context.flags[Inexact])


def ratio_inputs(
    formula: RatioFormula, resolve: Callable[[uuid.UUID], Value | None]
) -> tuple[Decimal, Decimal] | None:
    numerator = _number(resolve(formula.numerator))
    if formula.denominator.stat_definition_id is None:
        denominator = formula.denominator.constant
    else:
        denominator = _number(resolve(formula.denominator.stat_definition_id))
    if numerator is None or denominator is None:
        return None
    return numerator, denominator


def apply_ratio(
    formula: RatioFormula,
    resolve: Callable[[uuid.UUID], Value | None],
    target_type: StatValueType,
) -> Value | None:
    """A stat with no value, or a zero denominator, gives no value (ADR 0445). The quotient is
    rounded at the ratio precision before the multiplier, the offset and the mode apply."""
    operands = ratio_inputs(formula, resolve)
    if operands is None:
        return None
    divided = divide(*operands)
    if divided is None:
        return None
    return _rounded(
        divided[0] * formula.multiplier + formula.offset, formula.round_mode, target_type
    )


def ratio_was_rounded(
    formula: RatioFormula, resolve: Callable[[uuid.UUID], Value | None]
) -> bool | None:
    """Whether the division of a ratio lost digits at the ratio precision (ADR 0445), None when
    it has no value."""
    operands = ratio_inputs(formula, resolve)
    divided = None if operands is None else divide(*operands)
    return None if divided is None else divided[1]


def always_whole(
    coefficients: Iterable[Decimal], offset: Decimal, input_types: Iterable[StatValueType]
) -> bool:
    """Whether a linear or sum formula can only ever produce a whole number:
    every input a whole stat (an int, or a bool or an enum read as a number, ADR 0444), every
    coefficient (or multiplier) and the offset whole. An int stat needs no rounding mode then
    (ADR 0126)."""
    return all(value_type in _WHOLE_TYPES for value_type in input_types) and all(
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


MAX_FORMULA_CHAIN = 200
"""The most formulas a write may chain, one reading the next (ADR 0443). Evaluation recurses
through the chain, so an unbounded one cannot be read."""


def _chains_below(
    edges: Mapping[uuid.UUID, set[uuid.UUID]],
    readers: Mapping[uuid.UUID, list[uuid.UUID]],
    unread: dict[uuid.UUID, int],
) -> dict[uuid.UUID, int]:
    """Topological order, a stat after everything it reads: Kahn's walk from the stats that read
    nothing, so `below[n]` (the longest chain starting at n) is final when n comes up."""
    below: dict[uuid.UUID, int] = {}
    ready = [node for node, count in unread.items() if count == 0]
    while ready:
        node = ready.pop()
        below[node] = max((below[source] + 1 for source in edges.get(node, ())), default=0)
        for reader in readers.get(node, ()):
            unread[reader] -= 1
            if unread[reader] == 0:
                ready.append(reader)
    return below


def formula_chains_below(edges: Mapping[uuid.UUID, set[uuid.UUID]]) -> dict[uuid.UUID, int]:
    """For each stat of the definition-level graph, how many formulas lie below it in the longest
    chain that starts at it (0 for a stat nothing computes). A stat caught in a cycle is left out
    (a write that would make a cycle is refused, ADR 0104; one that got in has no chain)."""
    readers: dict[uuid.UUID, list[uuid.UUID]] = {}
    unread = {node: len(sources) for node, sources in edges.items()}
    for node, sources in edges.items():
        for source in sources:
            readers.setdefault(source, []).append(node)
            unread.setdefault(source, 0)
    return _chains_below(edges, readers, unread)


def longest_formula_chain(edges: Mapping[uuid.UUID, set[uuid.UUID]], through: uuid.UUID) -> int:
    """The number of formulas in the longest chain of the definition-level graph that runs through
    `through`: a path of k edges is k formulas, the last stat on it being one that is read, not
    computed. Iterative, since the graph it is asked about may hold a chain too deep to recurse
    (ADR 0443); a stat caught in a cycle that slipped past the write-time check adds nothing."""
    readers: dict[uuid.UUID, list[uuid.UUID]] = {}
    unread = {node: len(sources) for node, sources in edges.items()}
    for node, sources in edges.items():
        for source in sources:
            readers.setdefault(source, []).append(node)
            unread.setdefault(source, 0)
    below = _chains_below(edges, readers, unread)
    # `above[n]` is the longest chain ending at n, from the readers' side.
    above: dict[uuid.UUID, int] = {}
    for node in sorted(below, key=below.__getitem__, reverse=True):
        above[node] = max(
            (above[reader] + 1 for reader in readers.get(node, ()) if reader in above), default=0
        )
    return above.get(through, 0) + below.get(through, 0)


def apply_formula(
    formula: LinearFormula
    | ComparisonFormula
    | SumFormula
    | ExtremumFormula
    | ProductFormula
    | RatioFormula,
    resolve: Callable[[uuid.UUID], Value | None],
    target_type: StatValueType,
) -> Value | None:
    if isinstance(formula, ExtremumFormula):
        return apply_extremum(formula, resolve, target_type)
    if isinstance(formula, ProductFormula):
        return apply_product(formula, resolve, target_type)
    if isinstance(formula, RatioFormula):
        return apply_ratio(formula, resolve, target_type)
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
    counted: dict[tuple[uuid.UUID | None, ContentsFormula], int] | None = None,
) -> dict[uuid.UUID, Value]:
    """Every resolvable stat's value, by stat_definition_id, for the entity
    `stats` belong to. A stat with no value (unset inputs, or caught in a
    cycle) is absent.

    `overrides` replaces - or adds - a stat's formula for this one call
    only, without it being saved: the dry-run preview (ADR 0104).
    `contents` is what a contents formula reads, with `entity_id` naming
    the entity inside it; without them, a contents formula has no value
    (ADR 0127). `counted`, when given, receives how many things each contents formula took, by
    (entity, formula) (ADR 0447).
    """
    evaluation = _Evaluation(entity_id, stats, overrides or {}, contents)
    for stat_definition_id in [*evaluation.rows_of(entity_id), *(overrides or {})]:
        try:
            evaluation.resolve(entity_id, stat_definition_id)
        except RecursionError:
            # A chain of formulas too long to follow (ADR 0443; the write-time limit is
            # MAX_FORMULA_CHAIN, but a longer one may be stored): this stat has no value, as one
            # caught in a cycle has none, and the read goes on.
            logger.warning(
                "formula chain too deep to evaluate", stat_definition_id=str(stat_definition_id)
            )
            evaluation.visiting.clear()
            evaluation.values[(entity_id, stat_definition_id)] = _CYCLE
    if counted is not None:
        counted.update(evaluation.counted)
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
        # How many things each contents formula took, by (entity, formula), for the explanation
        # (ADR 0447).
        self.counted: dict[tuple[uuid.UUID | None, ContentsFormula], int] = {}

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
        if isinstance(formula, SelectFormula):
            return self._select(entity_id, formula, target_type)
        inputs: dict[uuid.UUID, Value | None] = {}
        for input_id in input_ids(formula):
            resolved = self.resolve(entity_id, input_id)
            if isinstance(resolved, _Cycle):
                return _CYCLE
            inputs[input_id] = self._as_number(entity_id, input_id, resolved)
        return apply_formula(formula, inputs.__getitem__, target_type)

    def _select(
        self, entity_id: uuid.UUID | None, formula: SelectFormula, target_type: StatValueType
    ) -> _Resolved:
        """The result of the step the source selects, or `otherwise`; a source with no value, or
        a result stat with none, gives none, and a cycle makes the formula one (ADR 0446)."""
        raw = self.resolve(entity_id, formula.source)
        if isinstance(raw, _Cycle):
            return _CYCLE
        stat = self.rows_of(entity_id).get(formula.source)
        position = choose_step(formula, raw, stat.stat_definition if stat is not None else None)
        result = formula.steps[position].result if position is not None else formula.otherwise
        if result is None or raw is None:
            return None
        if result.stat_definition_id is not None:
            resolved = self.resolve(entity_id, result.stat_definition_id)
            if isinstance(resolved, _Cycle):
                return _CYCLE
            number = _number(self._as_number(entity_id, result.stat_definition_id, resolved))
            return None if number is None else _rounded(number, RoundMode.NONE, target_type)
        if target_type is StatValueType.BOOL:
            return result.flag
        if target_type in (StatValueType.TEXT, StatValueType.ENUM):
            return result.text
        if result.number is None:
            return None
        return _rounded(result.number, RoundMode.NONE, target_type)

    def _as_number(
        self, entity_id: uuid.UUID | None, stat_definition_id: uuid.UUID, value: Value | None
    ) -> Value | None:
        stat = self.rows_of(entity_id).get(stat_definition_id)
        return numeric_value(value, stat.stat_definition if stat is not None else None)

    def _contents(
        self, entity_id: uuid.UUID | None, formula: ContentsFormula, target_type: StatValueType
    ) -> _Resolved:
        """What's inside without the stat, or without a value, counts as 0 in a sum;
        one caught in a cycle makes the total one too (ADR 0127). The options keep only what
        is switched on, of one kind, or true for a stat, and `min`, `max` and `count` ignore
        the stack count (ADR 0447)."""
        if self.contents is None or entity_id is None:
            return None
        total = Decimal(0)
        numbers: list[Decimal] = []
        counted = 0
        for child, quantity in self.contents.children.get(entity_id, ()):
            held = self.contents.held.get(child)
            if formula.only_kind is not None and (held is None or held.kind != formula.only_kind):
                continue
            if formula.only_active and held is not None and not held.active:
                continue
            if formula.where_stat_definition_id is not None:
                kept = self.resolve(child, formula.where_stat_definition_id)
                if isinstance(kept, _Cycle):
                    return _CYCLE
                if kept is not True:
                    continue
            if formula.aggregate == "count":
                counted += 1
                continue
            assert formula.source_stat_definition_id is not None
            resolved = self.resolve(child, formula.source_stat_definition_id)
            if isinstance(resolved, _Cycle):
                return _CYCLE
            number = _number(resolved)
            if formula.aggregate == "sum":
                counted += 1
                if number is not None:
                    total += number * quantity
            elif number is not None:
                counted += 1
                numbers.append(number)
        self.counted[(entity_id, formula)] = counted
        if formula.aggregate == "count":
            return _rounded(Decimal(counted), RoundMode.NONE, target_type)
        if formula.aggregate == "sum":
            return _rounded(total, RoundMode.NONE, target_type)
        if not numbers:
            if formula.if_none is None:
                return None
            return _rounded(formula.if_none, RoundMode.NONE, target_type)
        picked = min(numbers) if formula.aggregate == "min" else max(numbers)
        return _rounded(picked, RoundMode.NONE, target_type)
