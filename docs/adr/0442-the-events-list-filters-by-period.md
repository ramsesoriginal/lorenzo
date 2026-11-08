# 0442 - The Events list filters by period

Status: accepted, decided with the maintainer on 2026-11-08. It closes the API half of [#1135](https://github.com/ramsesoriginal/lorenzo/issues/1135), the part of the Events tab that UI-E could not draw ([#1016](https://github.com/ramsesoriginal/lorenzo/issues/1016)): the time filter of the design ([CS2, CS7](../design/web/calendars-sessions/README.md)). Related: [ADR 0313](0313-event-participation-browsing-and-calendar-addresses.md) (the Events list), [ADR 0309](0309-calendar-periods-events-and-date-associations.md) (periods and date associations) and [ADR 0440](0440-calendars-moves-into-the-web-shell.md).

## Context

The time filter narrows the Events list by when things are dated. Calendars first drew it from the browser: it read every Event's dates one request at a time and kept those in the range, which is slow in a large library and cannot filter before pagination or story order.

## Decision

`GET /tenants/{id}/events` takes an optional period filter:

- `dated_calendar_id` and `dated_year`, together: the Events dated in that calendar's year.
- Optionally a range inside the year: `dated_from_segment` with `dated_from_day`, and `dated_to_segment` with `dated_to_day`, each end naming a segment and a day together. Segments are ordered as the calendar's definition orders them, festivals included.
- A period counts when any day it covers is in the range: a day period for its day, a month or festival period for all its days, a year period for the whole year.
- It is applied before the name search, the participant and causal filters, story order and pagination, so `total` and the pages count only what it kept. It works on its own as well as with those filters.
- It reads dates only through periods the reader can see (the same visibility as an Event's dates), and the Events it returns are only those the reader can see already. It therefore never shows an Event a reader may not see, and says nothing about one they may not.
- Half a filter, a range with no calendar and year, an end that names a segment without a day, or a segment the calendar does not have is refused with 422.

Calendars' Events list sends the strip's range to this filter and no longer reads dates in the browser to filter. It still reads each row's dates to draw the date and the ticks on the strip, which are display, not filtering.

## Consequences

- The filter is one SQL subquery joined to the date associations; an Event dated in no period is never in a filtered list, which is what an undated Event should do.
- The generated clients carry the new parameters (`packages/api-client`); the CLI's models are unchanged, since they hold schemas and not query parameters.
- Each row of the list also carries the names of the dates it can see and, for who may read an Event's people, who took part, so the list no longer reads them per row. The strip's ticks still read structured dates per Event.
