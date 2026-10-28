# 0371 - The periods a date is tied through

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 13. A pure function in
`packages/calendar-engine`, read by the lens of [ADR 0372](0372-the-date-lens-on-the-maps-list.md). It reads
no row and decides nothing about what exists.

## Decision

`lorenzo_calendar.containing_periods(coordinate)` takes a `PeriodCoordinate` (a signed year, and
optionally a month or festival key and a day, the coordinates of [ADR 0309](0309-calendar-periods-events-and-date-associations.md))
and returns the coordinates of the periods that contain it, narrowest first, itself included:

| The coordinate is | It is contained in |
| --- | --- |
| a day, `(1100, "frostmoon", 7)` | itself, then the month `(1100, "frostmoon")`, then the year `(1100)` |
| a month or festival, `(1100, "frostmoon")` | itself, then the year |
| a year, `(1100)` | itself |

This is the period hierarchy of ADR 0309, and nothing else: a year contains its days because they are
its months' days, never because a number falls between two others. It is the same calendar, and the
function takes no calendar; the caller keeps it. It does not look at the definition, so a day the
calendar has no such date for contains and is contained like any other and simply has no periods tied to
it. A range, a "nearest" or "latest before" period, and a period in another year never come out of it.

`PeriodCoordinate` validates what the periods themselves validate: a signed year within a million, a key of
lowercase letters, digits and hyphens that starts with a letter (at most 64), a day from 1 to 1000, and a
day only with a month or festival. Anything else is a `ValueError` the caller turns into its own refusal.

## Validation and delivery

Tests: the three shapes, the order, that the result is a function of the coordinate alone, every refusal,
and that the keys agree with the keys of a stored period (a parametrised check against the calendar
definition's own segment keys). The README names it.

## Excluded

Descendants (what a year contains), spans, and any time argument for a read other than the Maps list.
