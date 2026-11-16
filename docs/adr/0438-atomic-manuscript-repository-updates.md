# 0438. Atomic manuscript repository updates

Date: 2026-11-07

## Status

Accepted — completes W9 of [RFC 0047](../rfcs/0047-lorenzo-writing.md).

## Context

The direct-text updates in ADRs 0429, 0430, 0435 and 0436 deliberately refuse
changed structure. An upstream extraction, shared Scene edit or reordered Carrier
must be reviewable without accepting half of its dependent changes. The remaining
W9 work is explicitly scoped as one implementation PR, stacked on that work.

## Decision

Add an Author-only composition review alongside the existing direct-text endpoint.
The review follows the connected manuscript dependencies of the selected copied
entry in the saved baseline, local library and currently readable upstream content.
It covers Books, Editions, Chapters, Scenes, tellings, biographies and Carriers,
including direct manuscript bundles, stable payloads and attachments, placements,
sharing-versus-independent telling references, coverage, guarded redirects,
numbering and structural contents. Ordinary notes, world metadata and prototypes
retain their existing repository-update semantics.

A review presents separately selectable manuscript bundles and structural records,
with original, local and upstream values. Nothing is applied merely because it is
conflict-free. Every accepted group has an explicit keep-local or take-upstream
choice; the selected dependent changes are validated and committed together. An
invalid combination is refused in full, with an actionable explanation. Local-only
entries and unselected records survive. Upstream entity removal does not delete the
local entity; it remains available as unassigned writing where appropriate.

Copy links retain source-normalized manuscript structure as well as the existing
bundle baseline and payload identities. Coverage identities are retained too.
Existing identities survive updates; new elements receive local identities.
Historical structure is never inferred for older copies. Where the older baseline
is absent, the review labels it unknown and requires an explicit decision before
establishing a new baseline. Taking an unknown baseline is still an explicit
replacement, never a claimed three-way merge.

New writing needed by accepted changes is reviewed explicitly and copied in the
same transaction. References outside the manuscript graph must already resolve
through ordinary copy links; missing world dependencies are identified for the
Author to copy first through the existing repository review. Name collisions and
locally deleted entries are never resolved by silently merging or resurrecting them.

The source is the existing gated live repository or immutable published release,
not an unrestricted read of its tenant. Review and application use consistent
snapshots, permission checks and a conditional token covering baseline, local,
upstream and dependency state. Application serializes local structural writes and
locks affected bundles; a stale or replayed request cannot partially apply.

Keep existing entry and Information audiences and review grants. Refuse any
structural selection that would add readers through a move, a shared telling,
coverage or redirect; changing sharing remains a separate explicit author action.
New copied writing starts private. Check all affected manuscripts for edit/history
access. Preserve saved prose in manuscript revisions and a private operational
checkpoint of the structural before/after state; neither is release content.

Use the shared repository review UI inside Writing's existing details/outline
surfaces, with names instead of raw identifiers and no new visual system. The
review includes affected dependent writing, including shared Scenes. Block applying
while affected local drafts or in-flight saves could be overwritten, retain drafts
on failure, refresh the accepted composition, and rebase writing-session counts so
imported or rearranged words do not count as new writing.

## Consequences

The old direct-text endpoint remains compatible, while connected and changed
compositions have a complete review path. Atomicity, stable anchors, removed source
entries, mixed local/upstream choices, binary replacements, released sources,
permissions, stale requests and browser draft recovery require integration tests.
Source/PDF export is W10 and is not part of this PR. No new editor, collaborative
live writing or additional publication format is introduced.
