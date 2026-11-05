# 0397 - Reviewed Scene periods from manuscript prose

RFC 0047 W8f builds on ADR 0309, 0327, 0342 and 0395.

## Decision

In direct Scene Details, an Author can check the current manuscript, including unsaved prose,
for the full names of existing visible calendar periods. Use the authorized, paginated period
read, which checks both the period and its calendar. Match locally using the prose boundaries
and whole-name rules of ADR 0395. Code, math, images and generated navigation do not match.
Each payload remains separate. This slice recognizes authored period names, not natural-language
date arithmetic or unmaterialized calendar coordinates.

Show each unique match with its calendar name. Duplicate names remain ambiguous, even across
calendars; explain that the ordinary Period lookup is available to choose deliberately. Keep
results only in the mounted review. Scanning performs no writes and creates no periods.

Acceptance is an explicit conditional update of the Scene's existing period field. Offer it
only when that field is empty. Recheck the current source, period identity/name/calendar and
visibility before writing with the Scene version captured during the scan. Concurrent Scene
changes require a fresh scan. An existing period is never replaced by a suggestion; the ordinary
Period control remains available for deliberate changes. Acceptance preserves manuscript prose
and refreshes Details, where the ordinary Clear period action remains available.

Matching a date does not assert occurrence, chronology, participation, causality or knowledge.
Several mentioned dates produce choices, never an inferred range or automatic choice.

## Validation

Real-API browser coverage checks formatted prose, duplicate names, existing dates, stale drafts,
concurrent Scene edits, private selection, clear/reload behavior, access scoping and phone
accessibility. Existing prose-matching tests cover Unicode, boundaries and excluded syntax.
No schema, API, copy or release changes are introduced.
