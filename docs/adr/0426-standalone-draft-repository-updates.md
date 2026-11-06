# 0426 - Explicit repository text updates for standalone drafts

RFC 0047 W9b builds on ADR 0398. ADR 0419 supplies the three-way review direction;
this slice adds its first guarded application mechanism to the existing comparison.

## Decision

An Author may explicitly keep local writing or take repository writing for a copied standalone
Scene or Chapter with a trustworthy manuscript baseline. Both copies must currently be outside
composition, tellings, Carrier coverage and redirects. The bundle must retain the same payload
identities, kinds and order on all three sides; non-text payloads must be unchanged. Changed or
removed structure, connected manuscripts and legacy copies remain comparison-only in this slice.

A comparison includes an opaque version over base, local, upstream and eligibility. Acceptance
requires that version, rechecks current authorization and upstream visibility, and serializes with
local manuscript/graph edits. The selected repository read is the existing live/private or
released/public read; a changed source since review requires another review. Conflicts always
require an explicit Keep yours or Take the update choice. Even clean updates require acceptance.

Taking updates writes all existing description contents/locales and the bundle title in one
transaction, through the ordinary description writer and manuscript revision triggers. Payload
identities and audiences remain unchanged. Keeping local writing changes only the baseline.
Either choice advances the prose baseline to the reviewed upstream, so that choice is not asked
again until upstream changes. Replayed stale versions fail without a second change.

The Writing editor refuses acceptance while drafts are dirty, saving or in conflict. It holds
editing during acceptance and then reloads the saved bundle into the existing editor, rebasing
session progress rather than counting incoming text as writing. Failures preserve the draft.
The shared review control supplies the explicit choices. No application from a read-only view.

Atomic updates involving composition, additional/removed payloads, pictures, tellings, coverage
and legacy baselines remain later W9 slices. No partial graph update is offered.

## Validation

Verify clean/conflicting choices, baseline advancement, stale local/upstream versions, replay,
missing versions, atomic multi-payload history and backlinks, unchanged audiences and binary
payloads, structural refusals, grant revocation and public released reads. Browser tests cover
unsaved protection, acceptance, unchanged session credit, saved revision recovery and reload.
