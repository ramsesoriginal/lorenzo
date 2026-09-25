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
    LinearFormula,
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
        computed_stat=SimpleNamespace(linear=linear, comparison=None),
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
        computed_stat=SimpleNamespace(linear=None, comparison=comparison),
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
