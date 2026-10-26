# 0345 - Extract outline elements into a Chapter

Status: accepted implementation of RFC 0047 W5b under ADR 0327.

## Decision

After atomic moves (ADR 0344), deliver extraction of a contiguous range of complete outline
elements into a new nested Chapter. The source is an Edition or Chapter. The selection may
contain whole manuscript text/picture payloads and existing Chapter/telling references. Replace
the range with the new Chapter at the same position; retain the selected order inside it.
This preserves every LorenzoScript payload verbatim, including its local footnotes and links.
Splitting inside a text payload and joining with guarded redirects remain subsequent W5 slices.

The source outline version, selected stable element ids, new Chapter id and title form one
conditional atomic request. Serialize with other structural changes and lock the source bundle.
Reject stale versions, non-contiguous/unknown/duplicate selections, inaccessible content and id
collisions before committing. Reparent existing children and payloads without changing their
identities, prose, picture bytes or notes. The original entry and its research/notes remain.

The new Chapter stays under its source, so Edition review access does not widen. Copy the
source's explicit outer audience and manuscript audience, including named knowledge grants,
to the new Chapter and its manuscript bundle; preserve the original bundle's authorship.
Do not infer sharing from the new Chapter's name. Existing child audiences are unchanged.
Ordinary entry and Information authorization still applies independently of composition.

Store an operational extraction receipt with actor, exact request fingerprint, source entry,
new Chapter and before/after outlines. Exact retries acknowledge the first result even after
later editing or moving; current Author access to both entries remains required. Receipt ids
cannot be reused for different requests or by another actor. FORCE RLS and same-tenant foreign
keys apply; receipts are excluded from copies/releases. The resulting content uses existing
Chapter, placement and payload copy/release contracts, without a new release format.

Before payload reassignment, save the source manuscript's pre-operation revision through the
existing transaction checkpoint mechanism. Its history stays with the original bundle and is
subject to current editing permission. Do not recover old audiences. Structural checkpoints
record composition separately; later recovery never silently rewinds the whole structure.

The outline exposes an optional Extract a Chapter control: choose the first and last complete
elements using readable labels, give the Chapter a title and confirm. Keep the operation id and
original version across retries. No new styling or editor framework is introduced.

## Validation

Test mixed text/picture/child extraction, byte-for-byte LorenzoScript, stable identities,
unchanged notes, audiences and reviewer reach, saved pre-extraction prose, stale and concurrent
requests, exact retries after later changes and tenant/id collisions with full rollback.
Verify copy/release round trips, operational exclusions and real-API browser extraction,
continuous reading, phone layout and accessibility.
