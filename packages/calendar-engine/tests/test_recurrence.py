import pytest

from lorenzo_calendar import (
    CalendarDefinition,
    Periodic,
    RecurrenceRule,
    occurrence,
    validate_recurrence,
)

DEFINITION = CalendarDefinition.model_validate(
    {
        "segments": [
            {"key": "month", "name": "Month", "days": 3},
            {"key": "leap", "name": "Leap", "days": 1, "when": {"every": 4, "offset": 1}},
        ]
    }
)


def test_signed_years_and_missing_days_skip_without_moving():
    rule = RecurrenceRule(segment="leap", day=1)
    assert occurrence(DEFINITION, rule, -3).year == -3
    assert occurrence(DEFINITION, rule, 1).segment == "leap"
    assert occurrence(DEFINITION, rule, 2) is None
    odd = RecurrenceRule(segment="month", day=3, when=Periodic(every=2, offset=1))
    assert occurrence(DEFINITION, odd, -1).day == 3
    assert occurrence(DEFINITION, odd, 0) is None


def test_rules_need_structural_dates_not_an_arbitrary_reference_year():
    validate_recurrence(DEFINITION, RecurrenceRule(segment="leap", day=1))
    with pytest.raises(ValueError):
        validate_recurrence(DEFINITION, RecurrenceRule(segment="leap", day=2))
    with pytest.raises(ValueError):
        validate_recurrence(DEFINITION, RecurrenceRule(segment="missing", day=1))
