# 0348 - Chapter joins and guarded redirects

Status: accepted implementation of RFC 0047 W5e under ADR 0327.

## Decision

Join two adjacent sibling Chapters into the earlier Chapter. Append the later Chapter's
complete ordered text/picture payloads and children, preserving their identities and each
LorenzoScript string verbatim; do not concatenate independently parsed texts. Remove only
the later Chapter's placement. Its identity, notes, audiences and saved manuscript history
remain. Require at least one source element; title-only Chapters can instead be removed
from an outline without deleting their entry. Other join shapes remain later W5 work.

The request names the source, destination and parent versions and a client-chosen operation
id. Serialize with the library structural lock, then lock the entries and bundles before
checking versions and adjacency. Both complete outlines must be readable. Require matching
outer audiences and matching manuscript audiences (including grants and authorship); an
empty destination bundle may be created with the source's audience. Same-parent adjacency
keeps Edition reviewer scope unchanged. Never silently widen or rewrite sharing.

Checkpoint both original manuscripts before moving payloads. Compact payload and placement
orders in one transaction and record an operational receipt with actor, request fingerprint
and before/after outlines. Exact retries return the acknowledgement without applying another
join; current access to both entries is still required. Receipts are excluded from copies.

A content row marks the source manuscript as joined and names its destination and first moved
stable element (payload or child). This is the destination section's anchor, not a character
offset. Source manuscript mutation, recreation, placement and further source composition are
refused, including through generic Information routes; ordinary notes and history reads remain
available. There is only one editable copy of the moved content.

A source read reports that it was joined. Reveal a destination link only after independently
checking the destination and anchor's current visibility and membership in that destination.
No automatic content forwarding or grant follows from the redirect. Deleting the anchor or
destination clears that reference but preserves the joined marker; moving the anchor elsewhere
makes the old link unavailable. A later join of the destination retargets incoming redirects
atomically while preserving their anchors, so redirects are flat and cannot loop.

Redirects are copied and released with remapped references; require their complete destination
content when copying a live link. Release format 18 adds them while readers for older releases
supply an empty set. Both content and receipt tables force RLS and use same-tenant foreign keys.

The outline offers Join with previous only for adjacent Chapters, with an explicit confirmation.
Opening the former source shows its title, the guarded destination link and its ordinary notes,
without an editor or automatic recovery of old drafts. The destination reading view identifies
stable element anchors. Reuse existing controls and styles.

## Validation

Cover mixed prose/pictures/children, notes and pre-operation revisions, unchanged LorenzoScript,
audience mismatches, generic write guards, destination/anchor visibility and deletion, subsequent
joins, stale/concurrent/replayed requests, cross-tenant collisions and rollback. Verify RLS,
repository copy/release round trips and historical formats. Exercise join, source-link navigation,
read-only source and continued destination editing through the real API/browser with phone
accessibility checks.
