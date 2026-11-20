# 0515 - Undo a Chapter extraction

Status: accepted, the second part of the undo operation of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (its Q2), after [ADR 0513](0513-undo-a-manuscript-split.md). Undo for a Scene extraction is [ADR 0517](0517-undo-a-scene-extraction.md); for a join it is not built.

## Context

An extraction ([ADR 0345](0345-extract-outline-into-chapter.md)) moves a consecutive range of text, pictures and child Chapters into a new Chapter and leaves a private receipt with the `before` and `after` orders of the source and of the new Chapter.

## Decision

- **`DELETE /tenants/{tenant_id}/writing/entries/{id}/extractions/{operation_id}`** puts the writing back and removes the new Chapter: the moved texts and pictures return to the source's manuscript at their places, the child Chapters are placed again where they were, and the new Chapter is deleted with its receipt.
- **Who and when:** the author who made it, with `If-Match` carrying the source's version as last read (428 without, 412 if it changed), and only while the source's outline is what the extraction left and the new Chapter's outline is what it was made with. Otherwise 409 in words. A second undo answers 404, since the receipt went with the Chapter.
- **Not in this slice:** a Scene extraction (its telling and shared Scene need their own care) and a join.

## Consequences

- The generated clients gain the operation.
- Writing's Make a Chapter offers Undo on the page it reloads to, in the same way as a split.
