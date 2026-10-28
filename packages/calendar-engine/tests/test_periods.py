import pytest
from pydantic import ValidationError
from test_calendar import calendar

from lorenzo_calendar import CalendarDate, PeriodCoordinate, containing_periods


def coordinate(year, segment=None, day=None):
    return PeriodCoordinate(year=year, segment=segment, day=day)


def test_a_day_is_in_its_month_and_its_year():
    assert containing_periods(coordinate(1100, "frostmoon", 7)) == (
        coordinate(1100, "frostmoon", 7),
        coordinate(1100, "frostmoon"),
        coordinate(1100),
    )


def test_a_month_is_in_its_year_and_a_year_in_itself():
    assert containing_periods(coordinate(-5, "feast")) == (
        coordinate(-5, "feast"),
        coordinate(-5),
    )
    assert containing_periods(coordinate(0)) == (coordinate(0),)


def test_what_contains_a_date_does_not_depend_on_anything_else():
    # The neighbours of a day, the next year and a month of another name are never in the result.
    got = set(containing_periods(coordinate(1100, "frostmoon", 7)))

    assert coordinate(1100, "frostmoon", 6) not in got
    assert coordinate(1101) not in got
    assert coordinate(1100, "thawmoon") not in got
    assert containing_periods(coordinate(1100, "frostmoon", 7)) == containing_periods(
        coordinate(1100, "frostmoon", 7)
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"year": 1, "day": 3},
        {"year": 1_000_001},
        {"year": -1_000_001},
        {"year": 1, "segment": "Frost"},
        {"year": 1, "segment": "1frost"},
        {"year": 1, "segment": "a" * 65},
        {"year": 1, "segment": "frost", "day": 0},
        {"year": 1, "segment": "frost", "day": 1001},
        {"year": 1.5},
        {"year": True and "1"},
    ],
)
def test_a_coordinate_is_what_a_period_is(bad):
    with pytest.raises(ValidationError):
        PeriodCoordinate(**bad)


def test_the_keys_are_the_keys_of_a_calendars_own_segments():
    definition = calendar()
    for segment in definition.segments:
        got = containing_periods(coordinate(3, segment.key, 1))
        assert [c.segment for c in got] == [segment.key, segment.key, None]
    date = CalendarDate(year=3, segment=definition.segments[0].key, day=1)
    assert (
        coordinate(date.year, date.segment, date.day)
        == containing_periods(coordinate(3, date.segment, 1))[0]
    )
