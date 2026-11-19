# 0520 - Move a block to another Chapter

Status: accepted, answering Q1 of [ADR 0494](0494-writing-moves-into-the-web-shell.md), which the maintainer first answered "keep" and then asked for.

## Context

A text or picture could move only within its page; to take it to another Chapter a writer had to split, extract a new Chapter, and move that. [ADR 0378](0378-extract-writing-into-a-scene.md) and [ADR 0374](0374-join-chapter-into-parent.md) already guard the things such a move must guard: both outlines are read whole, the two entries are shared alike, and nobody gains a reader.

## Decision

- **`POST /tenants/{tenant_id}/writing/entries/{id}/payloads/{payload_id}/move`** moves one text or picture of a Chapter's or Edition's manuscript into another Chapter's or Edition's, before `before_element_id` or at the end. `If-Match` carries the source's version and the body the destination's (428 without, 412 if either changed), both outlines must be complete, the two entries must have the same sharing as for a join (409 in words otherwise), and the destination gets a manuscript made like the source's when it has none.
- **No receipt and no undo of its own**: the versions make a repeat fail (412), and a block is moved back by the same operation. A receipt table, with its copy rules, is not worth it for a move this small.
- **Writing's block menu has "Move to another Chapter"**: it asks for the destination by title (Chapters and Editions), saves, reads both versions and moves the block to the end of the destination.

## Consequences

- The generated clients gain the operation.
- ADR 0494's Q1 answer is changed from "keep" to this.
