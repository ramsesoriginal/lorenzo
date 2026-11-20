# 0513 - Undo a manuscript split

Status: accepted, the first part of the undo operation of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (its Q2). Undo for an extraction and a join is not built.

## Context

[ADR 0346](0346-safe-paragraph-splits.md) and [0347](0347-syntax-aware-manuscript-splits.md) split a text block at a safe boundary and keep a private receipt with the two payload ids. The design asks for Undo after a split, an extraction and a join. An extraction's receipt keeps the `before` and `after` placements, but undoing it also means moving payloads back and removing the new Chapter; a join is likewise a larger inverse. A split is the simple one: its inverse is the concatenation it came from.

## Decision

- **`DELETE /tenants/{tenant_id}/writing/entries/{id}/splits/{operation_id}`** joins the two texts the split made: the first text becomes first plus second, the second payload is deleted, and the order numbers close up. The receipt goes with the second payload (its foreign key cascades), so an undo is used once and a second one answers 404.
- **Who and when:** the author who made the split, with `If-Match` carrying the entry's version as the caller last read it (428 without it, 412 if the entry changed since, which includes any later edit). If the two texts no longer follow one another the answer is 409 in words.
- **Not in this slice:** undo for an extraction and for a join. They stay in the tracking issue.

## Consequences

- The generated clients gain the operation.
- Writing's Split here offers Undo on the page it reloads to, while the tab's session remembers the receipt (a `sessionStorage` key, listed in the storage policy).
