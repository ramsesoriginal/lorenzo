"""stat_evaluation (ADR 0104) - pure Python, no database. Stats are plain
stand-ins with the attributes evaluate() reads off a VEffectiveStat row.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from lorenzo_api.models import Comparator, RoundMode, StatValueType
from lorenzo_api.stat_evaluation import (
    ComparisonFormula,
    Contents,
    ContentsFormula,
    LinearFormula,
    SumFormula,
    SumTerm,
    always_whole,
    apply_linear,
    evaluate,
)

_TYPE_COLUMN = {
    StatValueType.INT: "value_int",
    StatValueType.FLOAT: "value_float",
    StatValueType.BOOL: "value_bool",
    StatValueType.TEXT: "value_text",
    StatValueType.ENUM: "value_text",
}


def _stored(def_id: uuid.UUID, value_type: StatValueType, value: object) -> SimpleNamespace:
    row = SimpleNamespace(
        stat_definition_id=def_id,
        stat_definition=SimpleNamespace(value_type=value_type),
        computed_entity_id=None,
        computed_stat=None,
        value_int=None,
        value_float=None,
        value_bool=None,
        value_text=None,
    )
    setattr(row, _TYPE_COLUMN[value_type], value)
    return row


def _linear_row(
    def_id: uuid.UUID,
    value_type: StatValueType,
    source: uuid.UUID,
    multiplier: str,
    offset: str,
    round_mode: RoundMode,
) -> SimpleNamespace:
    linear = SimpleNamespace(
        source_stat_definition_id=source,
        multiplier=Decimal(multiplier),
        offset=Decimal(offset),
        round_mode=round_mode.value,
    )
    return SimpleNamespace(
        stat_definition_id=def_id,
        stat_definition=SimpleNamespace(value_type=value_type),
        computed_entity_id=uuid.uuid4(),
        computed_stat=SimpleNamespace(linear=linear, comparison=None, sum=None, contents=None),
    )


def _comparison_row(
    def_id: uuid.UUID, value_type: StatValueType, **fields: object
) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "right_stat_definition_id": None,
        "right_constant": None,
        "true_value": None,
        "false_value": None,
    }
    comparison = SimpleNamespace(**{**defaults, **fields})
    return SimpleNamespace(
        stat_definition_id=def_id,
        stat_definition=SimpleNamespace(value_type=value_type),
        computed_entity_id=uuid.uuid4(),
        computed_stat=SimpleNamespace(linear=None, comparison=comparison, sum=None, contents=None),
    )


def _sum_row(
    def_id: uuid.UUID,
    value_type: StatValueType,
    terms: list[tuple[uuid.UUID, str]],
    offset: str = "0",
    round_mode: RoundMode = RoundMode.NONE,
) -> SimpleNamespace:
    summed = SimpleNamespace(
        terms=[
            SimpleNamespace(source_stat_definition_id=source, coefficient=Decimal(coefficient))
            for source, coefficient in terms
        ],
        offset=Decimal(offset),
        round_mode=round_mode.value,
    )
    return SimpleNamespace(
        stat_definition_id=def_id,
        stat_definition=SimpleNamespace(value_type=value_type),
        computed_entity_id=uuid.uuid4(),
        computed_stat=SimpleNamespace(linear=None, comparison=None, sum=summed, contents=None),
    )


STRENGTH, MODIFIER, SAVE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@pytest.mark.parametrize(
    ("score", "floor", "truncate"),
    [(9, -1, 0), (10, 0, 0), (11, 0, 0), (8, -1, -1), (18, 4, 4), (1, -5, -4), (3, -4, -3)],
)
def test_dnd_modifier_floor_vs_truncate(score: int, floor: int, truncate: int) -> None:
    """The motivating bug: truncation is wrong for odd scores below 10."""
    for mode, expected in ((RoundMode.FLOOR, floor), (RoundMode.TRUNCATE, truncate)):
        stats = [
            _stored(STRENGTH, StatValueType.INT, score),
            _linear_row(MODIFIER, StatValueType.INT, STRENGTH, "0.5", "-5", mode),
        ]
        assert evaluate(stats)[MODIFIER] == expected


@pytest.mark.parametrize(
    ("value", "mode", "expected"),
    [
        (Decimal("2.5"), RoundMode.ROUND, 3),
        (Decimal("-2.5"), RoundMode.ROUND, -3),  # half away from zero
        (Decimal("2.1"), RoundMode.CEIL, 3),
        (Decimal("-2.1"), RoundMode.CEIL, -2),
        (Decimal("-2.9"), RoundMode.TRUNCATE, -2),
        (Decimal("-2.1"), RoundMode.FLOOR, -3),
    ],
)
def test_round_modes(value: Decimal, mode: RoundMode, expected: int) -> None:
    formula = LinearFormula(uuid.uuid4(), Decimal(1), Decimal(0), mode)
    assert apply_linear(formula, float(value), StatValueType.INT) == expected


def test_float_target_without_rounding_is_exact_decimal_arithmetic() -> None:
    inches, cm = uuid.uuid4(), uuid.uuid4()
    stats = [
        _stored(inches, StatValueType.INT, 70),
        _linear_row(cm, StatValueType.FLOAT, inches, "2.54", "0", RoundMode.NONE),
    ]
    assert evaluate(stats)[cm] == 177.8


def test_chained_formulas_evaluate_in_dependency_order() -> None:
    """save = modifier + 2, modifier = floor((strength - 10) / 2) - listed
    out of order on purpose."""
    stats = [
        _linear_row(SAVE, StatValueType.INT, MODIFIER, "1", "2", RoundMode.FLOOR),
        _linear_row(MODIFIER, StatValueType.INT, STRENGTH, "0.5", "-5", RoundMode.FLOOR),
        _stored(STRENGTH, StatValueType.INT, 14),
    ]
    assert evaluate(stats) == {STRENGTH: 14, MODIFIER: 2, SAVE: 4}


def test_comparison_bool_and_text_results() -> None:
    weight, capacity, overloaded, weight_class = (uuid.uuid4() for _ in range(4))
    stats = [
        _stored(weight, StatValueType.FLOAT, 60.0),
        _stored(capacity, StatValueType.INT, 50),
        _comparison_row(
            overloaded,
            StatValueType.BOOL,
            left_stat_definition_id=weight,
            comparator="gt",
            right_stat_definition_id=capacity,
        ),
        _comparison_row(
            weight_class,
            StatValueType.ENUM,
            left_stat_definition_id=weight,
            comparator="le",
            right_constant=Decimal(50),
            true_value="light",
            false_value="heavy",
        ),
    ]
    values = evaluate(stats)
    assert values[overloaded] is True
    assert values[weight_class] == "heavy"


def test_missing_input_leaves_the_stat_without_a_value() -> None:
    stats = [_linear_row(MODIFIER, StatValueType.INT, STRENGTH, "0.5", "-5", RoundMode.FLOOR)]
    assert evaluate(stats) == {}


def test_bool_is_not_a_number() -> None:
    flag = uuid.uuid4()
    stats = [
        _stored(flag, StatValueType.BOOL, True),
        _linear_row(MODIFIER, StatValueType.INT, flag, "1", "0", RoundMode.FLOOR),
    ]
    assert MODIFIER not in evaluate(stats)


def test_a_cycle_resolves_to_nothing_without_raising() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    stats = [
        _linear_row(a, StatValueType.INT, b, "1", "0", RoundMode.FLOOR),
        _linear_row(b, StatValueType.INT, a, "1", "0", RoundMode.FLOOR),
        _linear_row(c, StatValueType.INT, a, "1", "0", RoundMode.FLOOR),
        _stored(STRENGTH, StatValueType.INT, 10),
    ]
    assert evaluate(stats) == {STRENGTH: 10}


def test_overrides_replace_or_add_a_formula_for_one_call() -> None:
    stats = [
        _stored(STRENGTH, StatValueType.INT, 9),
        _linear_row(MODIFIER, StatValueType.INT, STRENGTH, "0.5", "-5", RoundMode.TRUNCATE),
    ]
    floor = LinearFormula(STRENGTH, Decimal("0.5"), Decimal(-5), RoundMode.FLOOR)
    strong = ComparisonFormula(STRENGTH, Comparator.GE, None, Decimal(15), None, None)

    replaced = evaluate(stats, overrides={MODIFIER: (floor, StatValueType.INT)})
    added = evaluate(stats, overrides={SAVE: (strong, StatValueType.BOOL)})

    assert replaced[MODIFIER] == -1
    assert evaluate(stats)[MODIFIER] == 0  # nothing saved
    assert added[SAVE] is False


# --- sum (ADR 0126) ----------------------------------------------------------


def test_a_sum_adds_its_terms_and_offset() -> None:
    """armour_class = 10 + dex_modifier + worn_ac_bonus; current_hp =
    max_hp - damage, reading another formula's result."""
    dex, worn, ac, max_hp, damage, hp = (uuid.uuid4() for _ in range(6))
    stats = [
        _sum_row(ac, StatValueType.INT, [(dex, "1"), (worn, "1")], offset="10"),
        _sum_row(hp, StatValueType.INT, [(max_hp, "1"), (damage, "-1")]),
        _linear_row(max_hp, StatValueType.INT, STRENGTH, "2", "0", RoundMode.NONE),
        _stored(STRENGTH, StatValueType.INT, 15),
        _stored(dex, StatValueType.INT, 2),
        _stored(worn, StatValueType.INT, 3),
        _stored(damage, StatValueType.INT, 7),
    ]
    values = evaluate(stats)
    assert (values[ac], values[hp]) == (15, 23)


def test_a_sum_rounds_and_keeps_fractions_for_a_float() -> None:
    level, attack, reach = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    stats = [
        _stored(level, StatValueType.INT, 5),
        _stored(STRENGTH, StatValueType.INT, 2),
        _sum_row(
            attack, StatValueType.INT, [(STRENGTH, "1"), (level, "0.5")], "0", RoundMode.FLOOR
        ),
        _sum_row(reach, StatValueType.FLOAT, [(level, "0.5")], "1"),
    ]
    values = evaluate(stats)
    assert (values[attack], values[reach]) == (4, 3.5)


def test_a_sum_with_an_unset_term_has_no_value() -> None:
    total, missing = uuid.uuid4(), uuid.uuid4()
    stats = [
        _stored(STRENGTH, StatValueType.INT, 10),
        _sum_row(total, StatValueType.INT, [(STRENGTH, "1"), (missing, "1")]),
    ]
    assert total not in evaluate(stats)


def test_a_cycle_through_a_sum_resolves_to_nothing() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    stats = [
        _stored(STRENGTH, StatValueType.INT, 10),
        _sum_row(a, StatValueType.INT, [(STRENGTH, "1"), (b, "1")]),
        _linear_row(b, StatValueType.INT, a, "1", "0", RoundMode.FLOOR),
    ]
    assert evaluate(stats) == {STRENGTH: 10}


def test_a_sum_override_evaluates_for_one_call() -> None:
    total = uuid.uuid4()
    stats = [_stored(STRENGTH, StatValueType.INT, 10)]
    formula = SumFormula((SumTerm(STRENGTH, Decimal(3)),), Decimal(1), RoundMode.NONE)
    assert evaluate(stats, overrides={total: (formula, StatValueType.INT)})[total] == 31


@pytest.mark.parametrize(
    ("coefficients", "offset", "types", "whole"),
    [
        (["1", "1"], "10", [StatValueType.INT, StatValueType.INT], True),
        (["15"], "0", [StatValueType.INT], True),
        (["2.0"], "-1", [StatValueType.INT], True),
        (["0.5"], "0", [StatValueType.INT], False),
        (["1"], "0.5", [StatValueType.INT], False),
        (["1"], "0", [StatValueType.FLOAT], False),
    ],
)
def test_always_whole(
    coefficients: list[str], offset: str, types: list[StatValueType], whole: bool
) -> None:
    assert always_whole([Decimal(c) for c in coefficients], Decimal(offset), types) is whole


# --- contents (ADR 0127) -----------------------------------------------------


def _contents_row(
    def_id: uuid.UUID, value_type: StatValueType, source: uuid.UUID
) -> SimpleNamespace:
    return SimpleNamespace(
        stat_definition_id=def_id,
        stat_definition=SimpleNamespace(value_type=value_type),
        computed_entity_id=uuid.uuid4(),
        computed_stat=SimpleNamespace(
            linear=None,
            comparison=None,
            sum=None,
            contents=SimpleNamespace(source_stat_definition_id=source),
        ),
    )


WEIGHT, OWN_WEIGHT, CONTENTS_WEIGHT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _weighed(own: int | None) -> list[SimpleNamespace]:
    """The weight recipe: weight = own_weight + contents_weight, and
    contents_weight = contents(weight)."""
    rows = [
        _sum_row(WEIGHT, StatValueType.INT, [(OWN_WEIGHT, "1"), (CONTENTS_WEIGHT, "1")]),
        _contents_row(CONTENTS_WEIGHT, StatValueType.INT, WEIGHT),
    ]
    if own is not None:
        rows.append(_stored(OWN_WEIGHT, StatValueType.INT, own))
    return rows


def test_contents_adds_up_what_is_inside_at_every_depth() -> None:
    """A backpack (2) holding a rope (1), 20 arrows (1 each), an unweighed
    torch, and a pouch (1) with 3 coins (1 each): 2 + 1 + 20 + 0 + 4."""
    backpack, rope, arrows, torch, pouch, coins = (uuid.uuid4() for _ in range(6))
    contents = Contents(
        stats={
            rope: _weighed(1),
            arrows: _weighed(1),
            torch: _weighed(None),
            pouch: _weighed(1),
            coins: _weighed(1),
        },
        children={
            backpack: [(rope, 1), (arrows, 20), (torch, 1), (pouch, 1)],
            pouch: [(coins, 3)],
        },
    )

    values = evaluate(_weighed(2), entity_id=backpack, contents=contents)

    assert (values[CONTENTS_WEIGHT], values[WEIGHT]) == (25, 27)


def test_contents_of_nothing_is_zero() -> None:
    empty = uuid.uuid4()
    values = evaluate(_weighed(3), entity_id=empty, contents=Contents(stats={}, children={}))
    assert (values[CONTENTS_WEIGHT], values[WEIGHT]) == (0, 3)


def test_contents_without_what_it_reads_has_no_value() -> None:
    values = evaluate(_weighed(3), entity_id=uuid.uuid4())
    assert CONTENTS_WEIGHT not in values
    assert WEIGHT not in values


def test_a_containment_cycle_leaves_what_depends_on_it_without_a_value() -> None:
    """A pack inside its own pouch: neither has a contents weight, nor a
    weight, and neither does a chest holding the pack. The chest's own
    unrelated stats still resolve."""
    chest, pack, pouch = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    contents = Contents(
        stats={pack: _weighed(2), pouch: _weighed(1)},
        children={chest: [(pack, 1)], pack: [(pouch, 1)], pouch: [(pack, 1)]},
    )

    for entity in (pack, pouch):
        values = evaluate(contents.stats[entity], entity_id=entity, contents=contents)
        assert WEIGHT not in values and CONTENTS_WEIGHT not in values
    chests = evaluate(
        [*_weighed(5), _stored(STRENGTH, StatValueType.INT, 12)],
        entity_id=chest,
        contents=contents,
    )
    assert WEIGHT not in chests
    assert chests[STRENGTH] == 12


def test_contents_may_read_its_own_stat_a_level_down() -> None:
    """weight = contents(weight) on a sack: its things' weights, not its own."""
    sack, stone = uuid.uuid4(), uuid.uuid4()
    contents = Contents(
        stats={stone: [_stored(WEIGHT, StatValueType.FLOAT, 1.5)]},
        children={sack: [(stone, 2)]},
    )
    values = evaluate(
        [_contents_row(WEIGHT, StatValueType.FLOAT, WEIGHT)], entity_id=sack, contents=contents
    )
    assert values[WEIGHT] == 3.0


def test_a_contents_override_evaluates_for_one_call() -> None:
    box, gem = uuid.uuid4(), uuid.uuid4()
    contents = Contents(
        stats={gem: [_stored(STRENGTH, StatValueType.INT, 4)]}, children={box: [(gem, 3)]}
    )
    formula = ContentsFormula(STRENGTH)
    values = evaluate(
        [],
        overrides={SAVE: (formula, StatValueType.INT)},
        entity_id=box,
        contents=contents,
    )
    assert values[SAVE] == 12
