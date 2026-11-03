# 0378 - Extract writing into a Scene

Status: accepted implementation of RFC 0047 W5g under ADR 0327.

## Decision

Extract a consecutive range of an Edition or Chapter's own manuscript text/picture payloads
into a new reusable Scene. Create a shared Scene telling at the range's former position.
The Scene owns the moved manuscript; the telling reads it through ADR 0342's existing
shared mode. Reuse elsewhere is explicit, and Make independent retains its existing meaning.
No Event, participation, viewpoint, date, knowledge or occurrence is inferred from prose.

Retain stable payload identities, verbatim LorenzoScript and picture bytes. Do not concatenate
texts. Reject a selection containing a Chapter or telling: Scenes and tellings are leaves in
composition. Partial prose can first use the existing safe split action. Other content and
ordinary notes stay at the source; saved history checkpoints its original manuscript.

Keep the library structural lock, conditional source version and complete-outline checks.
Both new entries copy the source outer audience; the Scene manuscript copies its inner
flags, grants and attribution. Check effective access for current participants before moving
prose, including contextual Scene access, and refuse widening rather than rewrite sharing.
The telling stays in the same Edition, so reviewer scope is unchanged. Reviewers gain no
generic Scene access through this operation. Authorize current source, Scene and telling on retry.

Use a separate scene-extraction route and an operational receipt containing source, Scene,
telling, actor, request fingerprint and before/after outlines. It has tenant_id, FORCE RLS,
same-tenant foreign keys and exclusion from repository copies/releases. Client-chosen IDs
make retries safe; collisions roll back all content and structure. Existing Chapter extraction
contracts and fingerprints stay unchanged. Share the extraction transaction rather than
maintaining two implementations of payload moves and checkpointing.

Existing Scene/telling/manuscript copy and release support carries the new content; no new
release format. The outline offers an optional Extract a Scene action beside Extract a Chapter,
with a title and first/last element selection, explicit shared-Scene wording and existing styles.

## Validation

Test text/picture order and stable IDs, source history/notes, both tenant kinds, rejected child
ranges, stale and concurrent requests, exact retries and cross-tenant collisions/rollback.
Test outer/inner and contextual visibility, reviewer reads, repository copies and receipt
exclusion. Retain Chapter extraction tests and prove reuse of the extracted Scene in a second
telling, independent editing and real-API browser operation with phone accessibility checks.
