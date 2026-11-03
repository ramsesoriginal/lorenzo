# 0383 - Personal manuscript-length goals

RFC 0047 W8a implements the personal manuscript-length measure under ADR 0327.

## Decision

An Author can keep one optional positive word target (up to 100 million) per library, account,
manuscript entry and counting scope. Write compares the direct target with current draft prose,
including unsaved edits. Read compares the assembled target with the completed authorized reading
from ADR 0382. The two targets are independent because an Edition or Carrier can have very little
direct prose and substantial assembled writing. A Book uses its selected Edition. Progress shows
current words and words remaining, or that the target has been reached. Clearing a target leaves
the manuscript intact. Moving writing may change the assembled length. This measure records no
writing activity and attributes no session credit.

The account comes from verified authentication. Reads and writes require library Author access
and a visible Writing entry. Joined sources are guarded. Book review grants do not expose goals.
A tenant-owned operational table has FORCE RLS and a composite same-tenant entry foreign key.
Personal targets are excluded from Edition duplication, repository copies and release documents.
The current count remains a local, reader-scoped calculation. Only the target is sent to the API.

Use a conditional replacement under the existing structural lock. An absent goal is version zero.
Changing or clearing the target advances its version; retain a cleared row so stale writes cannot
restore it accidentally. Identical retries acknowledge current state, missing preconditions fail,
and conflicting stale changes require a fresh read. Return private/no-store responses.

Place the control inside the existing Word count disclosure. Retrieve the target only on demand,
with no work on the typing path beyond ADR 0382's existing refresh. A separate personal writing
session, net-new attribution, timers and reviewed suggestions are subsequent W8 slices.

## Validation

Test account and library isolation, play and repository Authors, missing/stale/retried updates,
competing edits, clearing, joined/invalid entries and operational copy registration. Exercise
setting, reaching, reloading and clearing independent targets with the real API from the browser.
