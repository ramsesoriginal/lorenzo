# 0308 - Authored calendars and their calculation

Status: accepted, decided with the maintainer on 2026-10-19. Calendar slice of RFC 0028.

## Context

RFC 0028 proposes calendars alongside an undecided causal and historical model. The maintainer
accepted an independent delivery: author calendars, materialize selected periods, associate
minimal Events and Facts with dates, import donjon exports through the CLI, and edit/view in a
dedicated app. This ADR accepts calendar calculation only; ADR 0309 to 0311 define the rest.

## Decision

A Calendar is an entry with a `calendar` component and an independently versioned, validated
JSON definition (`lorenzo.calendar/1`). It has ordinary information bundles and a link name.
Rules do not inherit through prototypes. No setting data, epoch, default calendar or clock is
seeded. An unused library has no calendar rows and existing untimed responses stay unchanged.

The definition has an ordered list of segments with stable keys independent of display names.
Each segment has a positive day count, month/festival classification and an independent flag
saying whether its days advance the weekday. An optional periodic rule includes it exactly
when `(year - offset) % every == 0`, with positive `every`. Festivals do not consume a month
ordinal. Days are numbered from one. Weeks have a positive length and optional names; they
advance continuously across participating days. A segment-reset week is an explicit option.

Years are signed integers including zero. Calculation uses proleptic rules, not historical
reforms. An explicit reference date and weekday anchor determine weekday alignment. A moon
has a positive decimal period and an explicit new-moon reference date plus decimal day offset;
phase follows elapsed calendar days, including days outside the week. Eight phase bands are
shown. Gregorian exception rules, arbitrary formulas, changing rules within history, hours,
relative prose parsing and approximate dates are later decisions.

`packages/calendar-engine` is a pure Python package shared by actual Python consumers. API
preview endpoints return bounded calculated year/month data; the web app renders it without a
second calendar evaluator. Inputs and work are bounded, including segment/day counts, integer
years and periodic cycles. Decimal arithmetic preserves fractional moon periods. Invalid dates
are errors, never silently clamped. Conversions between local dates and calendar-relative day
numbers round-trip, including negative years and leap/festival boundaries. Day numbers are
calculation coordinates and never clock readings, universal instants or causal evidence.

Calendar create/read/update and year preview are tenant-scoped. Writes use existing authoring
standing and `If-Match`; structural updates lock the calendar before checking its version.
Creation permits stable client ids through existing collision rules. Definition updates also
advance the containing entry version. The definition and existence/name share an outer
audience, initially restricted; information audiences remain separately explicit. Appropriate
privileged Authors/GMs retain existing access. Sharing information never opens its calendar.
Lists filter before pagination and counts; direct reads and previews use the same gate.

Rules are edited in place with concurrency checks, not an append-only history of definitions.
Repository releases retain their own immutable definition snapshots. A definition change that
would invalidate a referenced materialized period or recurrence is refused until references
are explicitly resolved; renaming keeps keys and identities. Rules never silently move dates.

Every tenant table forces RLS, uses composite same-tenant FKs and joins the copyable-table
registry. Copies remap calendar ids and keep local definitions. Definition snapshots take part
in base/upstream/local update review; changed definitions are a whole-field conflict rather
than an implicit merge of rules. Release documents, digests, public previews and purge handle
calendars explicitly and preserve older release readers. Removing a referenced calendar is
refused; whole-tenant deletion still succeeds. No read crosses library boundaries implicitly.

## Validation and delivery

The calendar-core PR includes the package, API, repository paths, generated contracts and tests.
Tests cover date/day round trips; negative years; every-N rules; weekless festivals;
segment-reset weeks; fractional moons; visibility and hidden counts; concurrent writes; tenant
isolation; and copy/update/release/purge. Fixtures are not tenant seeds. API consumers retain
existing untimed contracts apart from the explicitly accepted new kind values.

## Not in scope

Clock rates/readings, today, placement/inheritance, causality, lived/play order, branching,
learning, historical state, and the rest of RFC 0028 remain undecided. The calendar slice does
not authorize entry gates for physical inventory or beings, epistemic verdicts or confidence.
