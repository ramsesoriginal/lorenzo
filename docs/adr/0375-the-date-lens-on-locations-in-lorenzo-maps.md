# 0375 - The date lens on Locations in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 14. Extends
[ADR 0373](0373-the-date-lens-in-lorenzo-maps.md) to the Locations page for the list of
[ADR 0374](0374-the-date-lens-on-the-locations-list.md). Desktop only.

## Decision

**The Locations page can be looked at through a date,** by the same control as the Maps page: the shared
period picker in its one-choice mode, read only, opening empty, with no *Today*, and not on the page at all
when the library has no calendar. The words are the same too: *Tied to this date*, *Not tied to a date* and
*Tied to other dates*, never *existed at*; the Locations tied to other dates come last in a quieter colour; the
same checkbox leaves them out and says how many are left; *Clear the date* returns the page.

**The tree gives way to the list while a date is chosen.** The page shows *Where things are* as a tree of
roots, each opened for what is inside it. A date is not a property of a branch, so with one chosen the page
shows the visible Locations as a flat list, each with its words, and says so in a line: *With a date chosen
the Locations are listed by name, not by where they are.* Clearing the date brings the tree back as it was.
A search narrows either.

**One control, written once.** The lens control the Maps page uses is shared by both pages from one module,
and the words from one place, so a change to either reaches both. The Location page and the Map page show
nothing about dates.

## Validation and delivery

Browser tests against the real API: no calendar, no control on either page; a library with a calendar and
three Locations (tied to the day's month, tied to another year, tied to nothing) one of them inside another,
read through a day and a year: the flat list, the words, the order, the faded class, the checkbox and its count,
the line that says why the tree went, and the tree back on clearing; a player who cannot see a date reading it
as not tied; axe in light and dark with a date chosen. Unit tests of the shared words as the Maps page
already has them.

## Excluded

A date on the Location page, a Location dating form, a tree that hides branches by a date, and a range.
