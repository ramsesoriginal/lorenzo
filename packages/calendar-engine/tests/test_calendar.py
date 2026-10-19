import random
from decimal import Decimal

import pytest
from pydantic import ValidationError

from lorenzo_calendar import (
    CalendarDate,
    CalendarDefinition,
    Moon,
    Periodic,
    Segment,
    Week,
    from_day,
    moon_phases,
    preview_year,
    to_day,
    weekday,
)


def calendar():
    reference = CalendarDate(year=0, segment="first", day=1)
    return CalendarDefinition(
        segments=(
            Segment(key="first", name="First", days=27),
            Segment(key="festival", name="Festival", days=2, kind="festival", in_week=False),
            Segment(key="second", name="Second", days=27),
            Segment(key="leap", name="Leap", days=1, kind="festival", when=Periodic(every=4)),
        ),
        week=Week(length=7, reference=reference),
        moons=(Moon(key="moon", name="Moon", period=Decimal("14.5"), reference=reference),),
    )


def test_signed_date_day_roundtrip_with_periodic_segments():
    definition = calendar()
    generator = random.Random(308)
    for year in [-1000000, -100, -4, -1, 0, 1, 4, 100, 1000000]:
        for segment in definition.segments:
            if segment.includes(year):
                for day in {1, segment.days, generator.randint(1, segment.days)}:
                    date = CalendarDate(year=year, segment=segment.key, day=day)
                    assert from_day(definition, to_day(definition, date)) == date
    assert to_day(definition, CalendarDate(year=-1, segment="second", day=27)) == -1


def test_weekless_festival_and_month_ordinals():
    definition = calendar()
    result = preview_year(definition, 0)
    assert [s.month_ordinal for s in result.segments] == [1, None, 2, None]
    assert all(d.weekday is None for d in result.segments[1].days)
    assert result.segments[2].days[0].weekday == 27 % 7


def test_segment_reset_and_periodic_offset():
    definition = calendar()
    definition = CalendarDefinition.model_validate(
        {**definition.model_dump(), "week": {**definition.week.model_dump(), "reset": "segment"}}
    )
    assert weekday(definition, CalendarDate(year=7, segment="second", day=1)) == 0
    rule = Periodic(every=4, offset=1)
    assert [year for year in range(-5, 6) if rule.includes(year)] == [-3, 1, 5]


def test_moon_fractional_period_and_negative_dates():
    definition = calendar()
    reference = CalendarDate(year=0, segment="first", day=1)
    assert moon_phases(definition, reference) == {"moon": 0}
    assert moon_phases(definition, from_day(definition, 29)) == {"moon": 0}
    assert moon_phases(definition, from_day(definition, -1)) == {"moon": 7}
    assert moon_phases(definition, from_day(definition, 8)) == {"moon": 4}


def test_invalid_dates_and_definitions_are_not_clamped():
    definition = calendar()
    for date in (
        CalendarDate(year=1, segment="leap", day=1),
        CalendarDate(year=0, segment="first", day=28),
        CalendarDate(year=0, segment="missing", day=1),
    ):
        with pytest.raises(ValueError):
            to_day(definition, date)
    for changes in (
        {"segments": [definition.segments[0], definition.segments[0]]},
        {"segments": [Segment(key="only", name="Only", days=1, when=Periodic(every=4))]},
        {"moons": [dict(key="bad", name="Bad", period="NaN", reference=definition.week.reference)]},
    ):
        with pytest.raises(ValidationError):
            CalendarDefinition.model_validate({**definition.model_dump(), **changes})
    with pytest.raises(ValueError):
        from_day(definition, 10**20)
    with pytest.raises(ValueError):
        preview_year(definition, True)


def test_sample_387_day_weekday_alignment_and_reference_moons():
    lengths = [27, 27, 27, 2, 27, 27, 27, 2, 27, 27, 27, 2, 27, 27, 27, 2, 27, 27, 1]
    reference = CalendarDate(year=3286, segment="segment-1", day=1)
    definition = CalendarDefinition(
        segments=tuple(
            Segment(key=f"segment-{i}", name=f"Segment {i}", days=n)
            for i, n in enumerate(lengths, 1)
        ),
        week=Week(length=7, reference=reference, weekday=4),
        moons=tuple(
            Moon(
                key=f"moon-{i}",
                name=f"Moon {i}",
                period=Decimal(n),
                reference=reference,
                offset=Decimal(shift - (3286 * 387 + 4)),
            )
            for i, (n, shift) in enumerate([(14, 1), (23, 0), (42, 0)], 1)
        ),
    )
    assert sum(len(s.days) for s in preview_year(definition, 3286).segments) == 387
    assert weekday(definition, CalendarDate(year=3242, segment="segment-1", day=1)) == 0
    for day in [1, 2, 27]:
        date = CalendarDate(year=3286, segment="segment-1", day=day)
        phases = moon_phases(definition, date)
        for i, (period, shift) in enumerate([(14, 1), (23, 0), (42, 0)], 1):
            assert (
                phases[f"moon-{i}"] == ((3286 * 387 + 4 + day - 1 - shift) % period) * 8 // period
            )
