# 0530 - A calendar's current date, and where Events are dated

Status: accepted and built, 2026-11-27, asked for by the maintainer as slice A4 of UI-H's API work ([ADR 0528](0528-ui-h-retiring-the-old-frame-and-auditing-the-apps.md), H3): "the current date can be a field on a calendar". Two small additions the Calendars and Social pages wait for: a calendar that knows what day it is at the table (for the time filter's "This month", [ADR 0440](0440-calendars-moves-into-the-web-shell.md)), and one read of where a year has Events (for the strip's marks in Social's Event chooser, [ADR 0527](0527-social-moves-into-the-web-shell.md)).

## Context

[The design](../design/web/calendars-sessions/README.md) kept the status bar's in-world date to the Session being looked at, because no campaign or calendar has a *current* date in the data, and its time filter's "This month" shortcut was left undrawn for the same reason. The maintainer chose the smallest honest answer: the date is a field of the calendar, set by someone who may write it, and nothing infers it.

The time filter's strip draws a mark on every day something is dated on. Calendars gets them from the periods it already reads for its own month. Social, which has no calendar of its own, would have to read every Event's dates one at a time.

## Decision

- **A calendar has `today`**: `{year, segment, day}` or null (a nullable `jsonb` column on `calendar`, no new table, no new policy). It is read with the calendar (`GET …/calendars/{id}`, and in the list's detail), by anyone who can read the calendar.
- **`PUT …/calendars/{id}/today`** sets it from `{"today": {…}}` or clears it with `{"today": null}`. It needs `If-Match` (428 without it, 412 when stale), is refused with 422 when the day does not exist in that calendar (`segment_for`, the same check periods use), and is allowed to whoever may write the calendar. It is logged (`calendar.today_set`). It does not move by itself: nothing advances it, and no other page infers it.
- **Replacing the definition keeps `today` when the day is still there and clears it when it is not**, so a date can never name a day its calendar no longer has. The response of that write says which.
- **`GET …/events/dated-days?calendar_id=&year=`** returns, for one calendar's year, `[{segment, day, count}]`: where Events are dated (`day` null for a whole segment, `segment` null for the whole year) and how many, in the calendar's own order. It reads through the periods and the Events the reader may see, as the Events list's period filter does ([ADR 0442](0442-the-events-list-filters-by-period.md)), so it tells a reader nothing about an Event they cannot see. One read for the year; no per-Event reads.

## Consequences

- Calendars can draw "This month" and a marked today; Social's Event chooser can draw the strip's ticks with one request. Both are H4's work.
- An API client that wrote a calendar from a read keeps working: the new field is optional in what it sends (the `definition` route does not take it).
- Migration `c05300000001` adds the column; downgrade drops it. A calendar copied or released with a repository keeps its `today` as it keeps the rest of the row (it is the table's own data, not an audience, so no copy rule changes).
- Tests: `tests/test_calendar_today.py` (set, refuse a day that does not exist, conditional writes, kept or cleared with the definition, null clears; the year's dated days with counts, the other year, an empty year, a missing calendar).
