# 0373 - The date lens in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 13. Extends
[ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) for the lens of [ADR 0372](0372-the-date-lens-on-the-maps-list.md).
Desktop only.

## Decision

**The Maps list can be looked at through a date.** Under the search there is a *Tied to a date* control,
the shared period picker ([ADR 0323](0323-the-calendar-period-picker.md)) in its one-choice mode and read
only: it creates no period and the page never offers to. It opens empty. There is no default date and no
*Today*. When the library has no calendar the control is not on the page at all, and the list is what it
was.

**With a date chosen**, the list asks for it and reads each Map's `tie`. A Map is written with the words
*Tied to this date*, *Not tied to a date* or *Tied to other dates* beside its name, never *existed at*; Maps
tied to other dates come last and are drawn faded, and Maps tied to this date come first. A checkbox, *Leave
out Maps tied only to other dates*, sends `exclude_other` and says how many are left. *Clear the date*
returns the list to what it was. The chosen date is not remembered, not put in the address and not sent
anywhere but the list's request.

**A Map page** shows nothing about dates: a Map's time is only the lens's business, and nothing on the page
says where or when anything is.

## Validation and delivery

Unit tests of the words and of the request the choice makes. Browser tests against the real API: no
calendar, no control; a library with a calendar and three Maps (tied to the day's month, tied to another
year, tied to nothing) read through a day, a month and a year; the order and the faded class; the checkbox
and its count; clearing; a player who cannot see a Map's date reading it as not tied; axe in light and dark
with a date chosen.

## Excluded

Choosing a date on a Map page, editing a Map's dates here, a date lens on the Locations list, and a range.
