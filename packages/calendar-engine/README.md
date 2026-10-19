# Authored calendars

Pure Python validation and calculation for `lorenzo.calendar/1` (ADR 0308).
No database, clock, setting data, or inferred current date. Years include zero.

`CalendarDefinition` validates a definition. `to_day` / `from_day` convert local dates
and calendar-relative day numbers; `preview_year` returns bounded month/festival data,
weekdays and moon phases. References are calculation anchors, not story timestamps.

Run `mise run //packages/calendar-engine:test` and `:lint`.
