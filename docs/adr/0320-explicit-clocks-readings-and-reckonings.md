# 0320 - Explicit clocks, Event readings and calendar reckonings

Status: accepted, agreed with the maintainer on 2026-10-22. First implementation slice of
RFC 0028's newly accepted clock scope. ADR 0321 records constant clock relationships.

## Decision

A Clock is an entry with a `clock` component, name, slug, Information and an outer audience.
It is ticking or explicitly timeless. Missing clock data means unmodeled, never timeless.
No default clock, calendar, setting, epoch or current story date is seeded. Clock components
are independently authored, without prototype inheritance or automatic placement resolution.

Explicit Event readings and calendar reckonings are dedicated tenant relations, not Information
or causal assertions. A reading names one Event and one ticking clock. A reckoning names one
calendar and one ticking clock, pairing an authored calendar date's start with an exact clock
reading; calendar days and clock-local day units advance one for one within that reckoning.
Several calendars can reckon one clock. Existing Event/period associations remain unchanged:
association is not a clock reading, and no backfill or inference is performed.

Values use bounded exact rational arithmetic, serialized as strings, with no binary float math.
A point is exact; a range preserves endpoint inclusion. Selecting a whole calendar day records
its half-open day interval, not an invented midnight instant. Fractional day coordinates are
supported without an hours/minutes calendar editor. Timeless clocks permit neither readings
nor reckonings. Removing a referenced clock or making it timeless is refused until dependencies
are resolved. Whole-tenant purge remains possible.

Existing calendar-authoring standing governs Clock creation and editing; Authors, GMs and
full-visibility administrators manage structured readings/reckonings. Player Event capabilities
are unchanged. All relations start private and can be explicitly shared with readers of both
endpoints. The outer audience never grants inner Information access. No read, preview, count,
revision, activity entry or error reveals hidden endpoints or private relations.

Every write is version checked and locks affected entries in deterministic order. Stale edits
keep drafts and require saved-state review. Clock relations have explicit dependency guards.
Reckoning edits do not rewrite entered readings. Calendar-definition changes that alter a
reckoning's day mapping are refused until reckonings are explicitly removed/reviewed and
re-established; harmless renames remain possible. No read materializes calendar periods.

Lorenzo Calendars offers Clock list/detail editing, reckonings and an optional Event reading
panel, reusing Information/audiences, slugs, brand controls and bounded private-cache rules.
Untimed workflows stay unchanged. New tenant tables use tenant_id, FORCE RLS, composite
same-tenant foreign keys and copyable-table registration. Copy/release remaps dependencies;
copies stay local and upstream changes require explicit review. Older releases remain readable.

## Validation and delivery

Deliver one API-and-Calendars vertical PR stacked on this feature's documentation PR. Test
rational bounds, ranges and inclusivity, day/date boundaries, timelessness, visibility including
hidden counts/revisions, stale and concurrent writes, raw DB integrity, copy/update/release,
deletion/purge, generated contracts and desktop/phone real-API browser flows.

## Excluded

Placement inheritance, today, clock rates (ADR 0321), changing rates over history, traveller
sync inference, ageing, historical state, branching, loops and inferred learning. Neither
calendar formatting nor readings alter Event order, personal lived order or session/play order.
