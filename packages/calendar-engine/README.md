# lorenzo-calendar

Pure Python validation and calculation for `lorenzo.calendar/1` (ADR 0308).
No database, clock, setting data, or inferred current date. Years include zero.

`CalendarDefinition` validates a definition. `to_day` / `from_day` convert local dates
and calendar-relative day numbers; `preview_year` returns bounded month/festival data,
weekdays and moon phases. References are calculation anchors, not story timestamps.

Run `mise run //packages/calendar-engine:test` and `:lint`.

`RecurrenceRule`, `validate_recurrence` and `occurrence` calculate scheduled observances.
Every-N-years/offset rules use signed years. A date missing in a year returns no occurrence;
it never shifts to a neighbouring date. Calculation creates no entries and records no event.

`lorenzo_calendar.references` parses and resolves `calendar-slug year[/month[/day]]`
coordinates for read-only links (ADR 0313). Months accept a unique normalized name,
stable key, or one-based position in the full definition, including conditional festivals.
Explicit `name:` and `key:` prefixes disambiguate. An absent or ambiguous date is unresolved.

`containing_periods` returns the periods that contain a `PeriodCoordinate`, narrowest first: a day in its
month or festival and year, a month or festival in its year (ADR 0371). It follows the period hierarchy of
stored periods and reads no definition, so it is the one rule the Maps date lens matches with.

`lorenzo_calendar.document` reads the portable calendar document: `parse_document` strictly parses one
file (at most 2 MB) into a `CalendarDocument`, which keeps source material (`Annotation`) and
`DocumentWarning`s apart from the authored definition (ADR 0311). It is not a ledger and says nothing about
temporal truth.
