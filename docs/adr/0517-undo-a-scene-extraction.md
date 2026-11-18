# 0517 - Undo a Scene extraction

Status: accepted, the third part of the undo operation of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (its Q2), after [ADR 0513](0513-undo-a-manuscript-split.md) and [ADR 0515](0515-undo-a-chapter-extraction.md). Undo for a join is not built.

## Context

A Scene extraction ([ADR 0378](0378-extract-writing-into-a-scene.md)) moves a range of texts and pictures into a new Scene and puts a telling of that Scene in their place. Its private receipt holds the same `before` and `after` orders as a Chapter extraction's, and names the Scene and its telling.

## Decision

- **The same operation, `DELETE /tenants/{tenant_id}/writing/entries/{id}/extractions/{operation_id}`**, answers for a Scene extraction too: the moved texts and pictures return to the source's manuscript at their places, and the telling and the Scene are deleted with the receipt. Its answer names the removed Scene as `chapter_id`, as the receipt of a Chapter does.
- **Who and when** are as in ADR 0515: the author who made it, `If-Match` with the source's version as last read, and only while the source's outline and the Scene's contents are what the extraction left; otherwise 409. A second undo answers 404.

## Consequences

- No new route; the generated clients are unchanged except for the description.
- Writing's Make a Scene offers Undo Scene on the page it reloads to.
