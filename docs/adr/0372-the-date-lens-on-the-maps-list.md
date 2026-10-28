# 0372 - The date lens on the Maps list

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 13. Reads the existing
`entry_calendar_period` ([ADR 0309](0309-calendar-periods-events-and-date-associations.md)); no table, no column
and no write. The Locations list takes the same lens in its own later slice.

## Decision

`GET /tenants/{t}/maps` takes an optional date, by coordinates and never by a period id:

| Parameter | Meaning |
| --- | --- |
| `tied_calendar` | the calendar, a visible Calendar |
| `tied_year` | the signed year |
| `tied_segment` | the month or festival key, optional |
| `tied_day` | the day, optional and only with `tied_segment` |
| `exclude_other` | `true` leaves out the rows tied only to other dates; the default is to show them |

Without `tied_calendar` the request is what it is today: the same rows, the same order and not one more
key or join. With it, `tied_year` is required, a day needs its month, and the coordinate must be one
`containing_periods` accepts; a calendar the reader cannot see is the same 404 as one that is not there.
`exclude_other` alone, or any `tied_*` without the calendar, is a 422.

**Every Map is classified** for the reader and answers a `tie` of exactly one of:

- `tied`: it has an association with a period that contains the selected one (the selected period itself,
  its month or festival, its year: ADR 0371), in the selected calendar. Several associations are alternatives.
- `other`: it has at least one association the reader sees, and none of them contains the selected period.
- `untied`: it has no association the reader sees.

An association counts only when the reader sees the period and its calendar, as ADR 0309 requires for reading
a date link; a link the reader cannot see is absent, so a Map tied only to a hidden period is `untied` to
them, in every row, page and count. Nothing is inferred: no recency, no nearest Map, no "latest before".

**Order** is class (`tied`, `untied`, `other`), then name, then id. `exclude_other` is applied in SQL before
the page, so the page and its total count what is left. The classification is two `EXISTS` tests in the same
statement; there is no extra read per Map and no recursive query.

**Words** are fixed in the interface and never "existed at": *tied to this date*, *not tied to a date* and
*tied to other dates*. The API says the class and no sentence.

**What takes no time.** Distance, routes, whereabouts, the address and inventory reads have no date argument,
and a Map's placements are its Map's time: another layout in another era is another Map.

## Validation and delivery

Tests: the three classes and their order; a year, a month and a day each matching through their ancestors and
not through descendants or neighbours; two associations in two calendars; `exclude_other` with its total and
pages; a hidden period, a hidden calendar and a hidden association each reading as absent for a reader and
present for a GM; the 404 and 422 refusals; the list byte for byte what it was when no `tied_*` is sent; no
association row written; an old release without dates.

## Excluded

A default date, a "today", a span, a calendar picked for the reader, ordering by closeness, and the same lens
on any other list.
