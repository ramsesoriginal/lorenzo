"""Calendar definitions and pure, bounded local-date calculation (ADR 0308)."""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

YEAR_LIMIT = 1_000_000
Year = Annotated[int, Field(strict=True, ge=-YEAR_LIMIT, le=YEAR_LIMIT)]
Positive = Annotated[int, Field(strict=True, ge=1, le=1000)]
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
Name = Annotated[str, Field(min_length=1, max_length=200)]


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CalendarDate(Value):
    year: Year
    segment: Key
    day: Positive


class PeriodCoordinate(Value):
    """The coordinates of a stored period (ADR 0309): a year, a month or festival of it, a day of
    that. A day has its month or festival."""

    year: Year
    segment: Key | None = None
    day: Positive | None = None

    @model_validator(mode="after")
    def day_has_its_segment(self) -> Self:
        if self.day is not None and self.segment is None:
            raise ValueError("A day needs its month or festival")
        return self


class Periodic(Value):
    every: Annotated[int, Field(strict=True, ge=1, le=1000)]
    offset: Year = 0

    def includes(self, year: int) -> bool:
        return (year - self.offset) % self.every == 0

    def before(self, year: int) -> int:
        """Signed number of included years between year zero and this year."""
        return (year - 1 - self.offset) // self.every - (-1 - self.offset) // self.every


class Segment(Value):
    key: Key
    name: Name
    days: Positive
    kind: Literal["month", "festival"] = "month"
    in_week: bool = True
    when: Periodic | None = None

    def includes(self, year: int) -> bool:
        return self.when is None or self.when.includes(year)

    def before(self, year: int) -> int:
        return self.days * (year if self.when is None else self.when.before(year))


class Week(Value):
    length: Annotated[int, Field(strict=True, ge=1, le=100)]
    names: tuple[Name, ...] | None = None
    reset: Literal["never", "segment"] = "never"
    reference: CalendarDate
    weekday: Annotated[int, Field(strict=True, ge=0, le=99)] = 0

    @model_validator(mode="after")
    def valid_week(self) -> Self:
        if self.names is not None and len(self.names) != self.length:
            raise ValueError("Weekday names must match the week length")
        if self.weekday >= self.length:
            raise ValueError("Reference weekday must be inside the week")
        return self


class Moon(Value):
    key: Key
    name: Name
    period: Annotated[
        Decimal, Field(gt=0, le=1_000_000, max_digits=20, decimal_places=10, allow_inf_nan=False)
    ]
    reference: CalendarDate
    offset: Annotated[
        Decimal, Field(default=Decimal(0), max_digits=20, decimal_places=10, allow_inf_nan=False)
    ]


class CalendarDefinition(Value):
    format: Literal["lorenzo.calendar/1"] = "lorenzo.calendar/1"
    segments: Annotated[tuple[Segment, ...], Field(min_length=1, max_length=128)]
    week: Week | None = None
    moons: Annotated[tuple[Moon, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def valid_definition(self) -> Self:
        keys = [s.key for s in self.segments]
        if len(set(keys)) != len(keys):
            raise ValueError("Segment keys must be unique")
        if sum(s.days for s in self.segments) > 10_000:
            raise ValueError("A year may contain at most 10000 days")
        if not any(s.when is None for s in self.segments):
            raise ValueError("At least one segment must occur every year")
        moon_keys = [m.key for m in self.moons]
        if len(set(moon_keys)) != len(moon_keys):
            raise ValueError("Moon keys must be unique")
        if self.week is not None:
            segment = segment_for(self, self.week.reference)
            if not segment.in_week:
                raise ValueError("The week reference must participate in the week")
        for moon in self.moons:
            segment_for(self, moon.reference)
        return self


def segment_for(definition: CalendarDefinition, date: CalendarDate) -> Segment:
    for segment in definition.segments:
        if segment.key == date.segment:
            if not segment.includes(date.year) or date.day > segment.days:
                raise ValueError("Date does not exist in this year")
            return segment
    raise ValueError("Unknown segment key")


def year_start(definition: CalendarDefinition, year: int, *, weekdays: bool = False) -> int:
    return sum(s.before(year) for s in definition.segments if not weekdays or s.in_week)


def to_day(definition: CalendarDefinition, date: CalendarDate, *, weekdays: bool = False) -> int:
    target = segment_for(definition, date)
    total = year_start(definition, date.year, weekdays=weekdays)
    for segment in definition.segments:
        if segment is target:
            return total + (date.day - 1 if not weekdays or segment.in_week else 0)
        if segment.includes(date.year) and (not weekdays or segment.in_week):
            total += segment.days
    raise ValueError("Unknown segment key")


def from_day(definition: CalendarDefinition, number: int) -> CalendarDate:
    if isinstance(number, bool) or not isinstance(number, int):
        raise ValueError("Day number must be an integer")
    low, high = -YEAR_LIMIT, YEAR_LIMIT + 1
    if number < year_start(definition, low) or number >= year_start(definition, high):
        raise ValueError("Day number is outside the supported year range")
    while low + 1 < high:
        middle = (low + high) // 2
        if year_start(definition, middle) <= number:
            low = middle
        else:
            high = middle
    remaining = number - year_start(definition, low)
    for segment in definition.segments:
        if segment.includes(low):
            if remaining < segment.days:
                return CalendarDate(year=low, segment=segment.key, day=remaining + 1)
            remaining -= segment.days
    raise ValueError("Day number is outside the calendar")


def weekday(definition: CalendarDefinition, date: CalendarDate) -> int | None:
    segment = segment_for(definition, date)
    week = definition.week
    if week is None or not segment.in_week:
        return None
    if week.reset == "segment":
        difference = date.day - week.reference.day
    else:
        difference = to_day(definition, date, weekdays=True) - to_day(
            definition, week.reference, weekdays=True
        )
    return (week.weekday + difference) % week.length


def moon_phases(definition: CalendarDefinition, date: CalendarDate) -> dict[str, int]:
    day = to_day(definition, date)
    phases = {}
    with localcontext() as ctx:
        ctx.prec = 50
        for moon in definition.moons:
            elapsed = Decimal(day - to_day(definition, moon.reference)) - moon.offset
            # Decimal remainder retains the sign; normalize to [0, period).
            fraction = ((elapsed % moon.period) + moon.period) % moon.period / moon.period
            phases[moon.key] = int(fraction * 8)
    return phases


class DayPreview(Value):
    date: CalendarDate
    weekday: int | None
    moons: dict[str, int]


class SegmentPreview(Value):
    key: str
    name: str
    kind: Literal["month", "festival"]
    month_ordinal: int | None
    days: list[DayPreview]


class YearPreview(Value):
    year: Year
    segments: list[SegmentPreview]


def preview_year(definition: CalendarDefinition, year: int) -> YearPreview:
    # Validate even an empty/invalid year before returning calculated data.
    CalendarDate(year=year, segment=definition.segments[0].key, day=1)
    segments = []
    ordinal = 0
    for segment in definition.segments:
        if not segment.includes(year):
            continue
        if segment.kind == "month":
            ordinal += 1
        days = []
        for number in range(1, segment.days + 1):
            date = CalendarDate(year=year, segment=segment.key, day=number)
            days.append(
                DayPreview(
                    date=date,
                    weekday=weekday(definition, date),
                    moons=moon_phases(definition, date),
                )
            )
        segments.append(
            SegmentPreview(
                key=segment.key,
                name=segment.name,
                kind=segment.kind,
                month_ordinal=ordinal if segment.kind == "month" else None,
                days=days,
            )
        )
    return YearPreview(year=year, segments=segments)


class RecurrenceRule(Value):
    segment: Key
    day: Positive
    when: Periodic = Periodic(every=1)


def validate_recurrence(definition: CalendarDefinition, rule: RecurrenceRule) -> None:
    if not any(s.key == rule.segment and rule.day <= s.days for s in definition.segments):
        raise ValueError("The recurrence needs an existing segment and day")


def occurrence(
    definition: CalendarDefinition, rule: RecurrenceRule, year: int
) -> CalendarDate | None:
    validate_recurrence(definition, rule)
    if not rule.when.includes(year):
        return None
    date = CalendarDate(year=year, segment=rule.segment, day=rule.day)
    try:
        segment_for(definition, date)
    except ValueError:
        return None
    return date


def containing_periods(coordinate: PeriodCoordinate) -> tuple[PeriodCoordinate, ...]:
    """The periods that contain a period, narrowest first and itself included (ADR 0371): a day is
    in its month or festival and its year, a month or festival in its year. The period hierarchy
    and nothing else: no numbers between, no neighbour, and no calendar rule is consulted."""
    found = [coordinate]
    if coordinate.day is not None:
        found.append(PeriodCoordinate(year=coordinate.year, segment=coordinate.segment))
    if coordinate.segment is not None:
        found.append(PeriodCoordinate(year=coordinate.year))
    return tuple(found)
