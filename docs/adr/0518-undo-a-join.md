# 0518 - Undo a join

Status: accepted, the last part of the undo operation of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (its Q2), after [ADR 0513](0513-undo-a-manuscript-split.md), [ADR 0515](0515-undo-a-chapter-extraction.md) and [ADR 0517](0517-undo-a-scene-extraction.md).

## Context

A join ([ADR 0348](0348-chapter-joins-and-guarded-redirects.md), [ADR 0374](0374-join-chapter-into-parent.md)) moves a Chapter's writing into its destination, empties the Chapter's outline, and leaves a guarded redirect from the joined Chapter to its destination. It also retargets the redirects that pointed at the joined Chapter. The receipt kept the `before` and `after` outlines but not which redirects were retargeted.

## Decision

- **`DELETE /tenants/{tenant_id}/writing/entries/{id}/joins/{operation_id}`**, with `id` the joined Chapter, returns its writing to it and restores the outlines of the Chapter, the destination and the parent as they were; the redirect it made is removed and the ones it retargeted point at the Chapter again.
- **The receipt now records the redirects the join retargeted.** A join made before that has no undo (409 in words), rather than a guess.
- **Who and when:** the author who made it. `If-Match` carries the **destination's** version as last read (428 without, 412 if it changed), because the joined Chapter itself reads as a redirect. Only while the destination and the parent are exactly what the join left and the joined Chapter is still empty; otherwise 409. A second undo answers 404, as its receipt is deleted.

## Consequences

- The generated clients gain the operation.
- Writing's outline page offers Undo join on the page the join returns to.
- Every restructuring of ADR 0494 that has an API operation now has an undo.
