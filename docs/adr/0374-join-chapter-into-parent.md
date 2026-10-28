# 0374 - Join a Chapter into its parent

Status: accepted implementation of RFC 0047 W5f under ADR 0327.

## Decision

Extend ADR 0348 joins to a Chapter's immediate parent Chapter or Edition. Replace the
source placement with its complete ordered elements at the same position. Preserve reading
order, payload/child identities, verbatim LorenzoScript, pictures and child subtrees. The
source title is no longer a structural heading; its entry, notes, audiences and history
remain behind the existing guarded first-element redirect. Empty Chapters remain removable
placements rather than joins. No shared Scene manuscript is absorbed by this operation.

Use the existing join route and receipt with an optional mode, previous (the default) or
parent. In parent mode destination_id equals parent_id and both supplied versions must match
the current parent. Keep old default-mode request fingerprints stable for existing retries.
The source must still be directly placed in that parent. No new table or release format.

Keep the existing structural lock, complete-outline checks, audience/authorship equality,
effective-reader check, checkpoints, actor-bound retries and flat redirect retargeting.
Remaining inside the same Edition preserves reviewer scope. Reorder destination payloads
according to the final interleaved outline, not by appending the source texts at the end.
Rebuild each affected parent's placements once in the same transaction.

Offer an optional Join into parent action on Chapter rows in Chapter/Edition outlines.
Confirmation names both entries and explains the removal of that structural heading and
preservation of the old entry. Reuse the existing controls, styles and guarded source view.
Non-adjacent joins can be composed with the existing explicit move operation; joining Scene
tellings or concatenating independently parsed text blocks is outside this slice.

## Validation

Exercise Chapter and Edition parents with prose before and after the source, pictures,
nested Chapters and Scene tellings. Verify stable order and unchanged source strings,
history, notes, redirect navigation and incoming redirect retargeting. Check both parent
versions, wrong-parent and self joins, audience mismatches, replay, concurrency and rollback.
Retain sibling-join tests, repository copy/release tests and real-API browser coverage,
including phone accessibility and continued destination editing.
