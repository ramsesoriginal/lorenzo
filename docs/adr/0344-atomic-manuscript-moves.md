# 0344 - Atomic manuscript moves

Status: accepted implementation of RFC 0047 W5a under ADR 0327.

## Decision

Deliver W5 as smaller tested vertical sub-slices. W5a moves an existing Chapter subtree or
Scene telling between Edition/Chapter parents, nests or promotes it, or makes it unassigned.
It does not split prose, join manuscripts or add redirects; those remain subsequent W5 work.
Physical containment and prototype ancestry are unaffected.

A move names the current parent (or none), destination (or none), an optional destination
composition element to insert before, and the versions of the moved entry and affected parents.
The library structural lock serializes the operation with other composition/grant changes.
Authorize and lock the affected entries and their manuscript bundles, validate every version,
reject cycles and invalid kinds, then update both outlines in one transaction. A failure changes
neither outline. Stable entry and payload identities, text, notes and audiences remain intact.
Same-parent ordering keeps the existing composition endpoint; a move uses different parents.

Moves do not silently add reviewers. The destination Edition's reviewer set must be a subset
of the source Edition's set, ignoring accounts that are already library Authors. Unassigned
writing has no review grant. The author must explicitly change sharing before a move that
would introduce readers. Existing review notes keep their original Edition and fixed audience;
authors can inspect detached notes and reviewers lose content moved outside their granted tree.
No membership, Information audience or knowledge rows are changed.

A client-chosen operation id identifies a tenant-scoped receipt. It records the actor, exact
request fingerprint, moved entry and before/after parent outlines as an operational structural
checkpoint. A matching retry returns the original acknowledgement without performing another
move; changed requests or other actors cannot reuse the id. Replay still requires current
Author permission and sight of the moved entry. Receipts force RLS, use same-tenant keys and
are excluded from copies/releases. They are not a second source of manuscript content or a
new published release format. Receipt reads are author-gated and no-store.

The outline exposes Move only when requested: search an Edition or Chapter by title, choose
where it belongs, and confirm the move. Promote uses the current parent's parent, and Make
unassigned uses the same atomic operation. Search results and positions use readable titles,
not codes. Existing brand controls suffice; no new CSS. The request retains its operation id
across a retry and never silently replaces a stale version with fresh state.

## Validation

Prove cross-parent nested moves, promotion, detachment, placement among text/pictures and
other children, source/destination staleness, cycle/tenant/kind rejection, retries after later
moves, reviewer-set protection and unchanged identities/notes/prose. Verify RLS, composite
keys, registry exclusion, repository round trips after moving, and real-API browser workflows.
