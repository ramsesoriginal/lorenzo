# 0430 - Repository text updates for placed leaf Chapters

RFC 0047 W9c extends ADR 0429 using the composition and structural lock of ADRs 0341/0344.

## Decision

A copied leaf Chapter directly placed in an Edition may accept direct manuscript text updates
when its placement still matches the copy on both sides. New copies record a structural context
alongside their prose baseline: Edition, Book, following payload anchor and position, all using
source identities. No context is inferred for older connected copies.

The Chapter must have no children, telling, coverage or redirect dependencies. Its Edition and
Book must also be free of coverage/redirect dependencies. Nested Chapters and dependent structural
changes remain comparison-only. Existing standalone draft updates continue unchanged.

Comparison translates local entity/payload identities through the repository copy links. Unknown
local identities never match source identities. Eligibility requires equal base/local/upstream
context and unchanged payload shape. Both current contexts enter the review version, so moving or
reordering a Chapter after review refuses the stale request. Acceptance uses the existing tenant
structural lock and manuscript locks and never changes placements, grants or audiences.

Keep/take choices, atomic text/history/backlink writes, unsaved-draft protection and zero incoming
session credit are unchanged. Continuous Edition reading and existing reviewers see accepted text
through the same stable Chapter. This is a text update in unchanged composition, not a partial
structural update. No new table, release format, CSS or editor is introduced.

## Validation

Test remapped copy context, private/live and public/released source updates, stale local and source
placements, missing old context, nested/covered/redirected refusals, unchanged placement and history,
and accepted text in continuous reading. Exercise acceptance and reload through the real Writing
browser flow and retain the standalone regressions.
