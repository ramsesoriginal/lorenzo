# 0374 - The date lens on the Locations list

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 14, the last of the slices. The lens of
[ADR 0372](0372-the-date-lens-on-the-maps-list.md) on the Locations list, by the same rule and the same code.
No table, no column and no write.

## Decision

`GET /tenants/{t}/locations` takes the same optional date as `GET /maps`: `tied_calendar`, `tied_year`,
`tied_segment`, `tied_day` and `exclude_other`, with the same validation and the same refusals (a date needs
its Calendar and its year, a day needs its month or festival, a Calendar the reader cannot see is the same
404 as a missing one, and a coordinate [ADR 0371](0371-the-periods-a-date-is-tied-through.md) refuses is a 422).

**One rule, two lists.** The classification is not rewritten: the Maps list and the Locations list ask one
function for their two `EXISTS` tests, over `entry_calendar_period` and keyed on the entry, so a Location
and a Map tied to the same periods are tied, untied or tied to other dates alike, for every reader. An
association counts only when the reader sees its period and its calendar; nothing is inferred; the order is
`tied`, `untied`, `other`, then name, then id; `exclude_other` is applied in SQL before the page. Each row
answers `tie` only when a date was asked, and without a date the response is what it was, key for key.

**The flat list only.** The date is applied to the Locations list, where every visible Location is a row.
The tree of the roots (`root=true`) and the parts of a Location are reads of the part-of structure and
take no date: asking for both is a 422 that says so, rather than a tree of which some branches are hidden by
a date. A Location's date is its own and is never inherited from the Location above it or passed to those
inside it; what is part of what stays one fact and what is tied to when stays another.

**Whose dates.** A Location is dated like any other entry, by the existing `PUT /entities/{id}/dates`, by
those who may write it. No Location dating form is added here, and no Location reads a date from its Map or a
Map from its Locations.

## Validation and delivery

Tests, as their own parity set: a Location and a Map tied to the same periods read alike through a day, a
month and a year; the three classes and their order; `exclude_other` with its total and pages; a hidden
period and a hidden calendar reading as absent for a reader and present for a GM; the refusals, including
`root` with a date; no date inherited down part-of, nor up; the list key for key what it was without a date,
with the visible-roots read and the parts read untouched; no association written.

## Excluded

A date on the tree, on the parts read, on the address or on whereabouts; inheritance of a date through part-of;
a Location dating editor; a lens on any other list.
