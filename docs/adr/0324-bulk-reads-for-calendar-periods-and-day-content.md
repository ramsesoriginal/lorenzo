# 0324 - Bulk reads for calendar periods and day content

Status: accepted, decided with the maintainer on 2026-10-22. Serves ADR 0323 and the performance slice; additive to the existing API, so no breaking-change entry.

## Context

Calendars shows a month's saved days with two paged reads per saved period: `/entities/{id}/information?size=100`, which returns full payloads to build a 180-character snippet, and `/calendar-periods/{id}/entries`. It runs four days at a time, a whole-year view queues every saved day of every segment, and each rendered note may add an `entities/resolve` call. Sessions lists periods with `GET /entities?kind=calendar_period`, which carries no calendar, year, segment or day. There is no read of periods by coordinates or by id and no read of several periods' content at once.

## Decision

Three additions to the API. All are tenant-scoped, apply the same visibility gates as the reads they replace (calendar, period and entry outer audiences, and each Information audience), and never reveal a hidden row through a count, a position or a page boundary ([ADR 0309](0309-calendar-periods-events-and-date-associations.md), [ADR 0315](0315-reader-scoped-event-order-and-sharing.md)).

- **`GET /tenants/{tenant_id}/calendar-periods`**: a paged list of periods the caller can see, with the calendar's name, `granularity`, `year`, `segment`, `day`, `name`, `slug` and `parent_entity_id`. Filters: `calendar_id`, `year`, `segment`, and `id` (repeated, at most 100) to read chosen periods by id. Ordered by calendar name, year, segment order and day. It is what the picker and Sessions use to show "3 Frostmoon 1100 (Pal-Vaz)" and replaces the flat entity list.
- **`GET /tenants/{tenant_id}/calendars/{calendar_id}/years/{year}/period-summaries`**: for one year, optionally one `segment`, the saved periods the caller can see, each with its coordinates, its visible Information rows (at most ten; each with its title, and the source text of its first description cut at a word at 600 characters, with `truncated` saying whether it was cut), the number of visible dated entries and the first ten of them (`entity_id`, `name`, `slug`). The client renders and shortens the text as it does today, so a link in a note still resolves; summaries carry no other payloads and no unrelated Information. The list is paged like the other lists (a page is at most 100 periods), so a month is one request and a year is a request per page. It replaces the two reads per period.
- **`POST /tenants/{tenant_id}/calendars/{calendar_id}/periods/batch`**: materializes up to 1000 listed coordinates in one transaction, creating missing parents, and returns the periods in request order. It needs the same standing as the single write, locks the calendar once, is idempotent for coordinates that exist, and fails whole on an invalid date. It exists for a range chosen in the picker and is not used for browsing.

The OpenAPI schema, the generated client types and the CLI's models are regenerated. Reads are covered by tests for each audience combination (hidden calendar, hidden period, hidden entry, restricted Information, an administrative opt-out), pagination with hidden rows, and the absence of any write on a read.

## Not in scope

A range or interval as a stored concept; a tenant-wide timeline of periods; changing `YearPreview`; summaries of years or calendars rather than periods.

## Consequences

- A month view is one summary request instead of two per saved day; a whole year is one request per year or segment.
- Sessions names a period without loading the library's periods.
- The responses are viewer-specific and so are cached by viewer ([ADR 0325](0325-one-read-cache-and-what-it-may-hold.md)).
- A client that ignores the new routes keeps working; the old routes stay.
