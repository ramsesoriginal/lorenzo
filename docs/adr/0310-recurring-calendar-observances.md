# 0310 - Recurring calendar observances

Status: accepted, decided with the maintainer on 2026-10-19. Builds on ADR 0308 and 0309.

## Decision

A recurring observance is an entry with ordinary lore and audiences, connected to a calendar
by a recurrence rule. It names a stable segment key and day, with every-N-years and offset.
An occurrence on a date absent in that year is skipped, never moved. Definition edits must
validate existing rules. Leap segments define which days exist; observance rules define what
recurs on them. Import never infers either rule from a name.

Year/month reads calculate visible occurrences without creating period or Event entries.
An observance is not every particular celebration: an author may explicitly make an Event
for one occurrence and use the date association from ADR 0309. No observed occurrence is
inferred from a schedule. Dates never become causal or knowledge evidence.

Rules require visibility of both observance and calendar and existing authoring standing.
Conditional writes lock/version the relevant source entry. Copies remap identities and carry
rules; release documents, previews and purge support them. Structured rules share the source
entry's outer gate; notes keep their own audiences. No occurrence counts reveal hidden rules.

## Validation

Every-N/offset over signed years, leap-only and missing dates, month/year boundaries, multiple
observances, hidden rules, concurrent edits, repository copy/releases and zero write-on-read.
