# 0277 - Information shows who wrote it

Status: accepted, decided with the maintainer on 2026-10-12. Slice A2 of [RFC 0043](../rfcs/0043-the-being-sheet.md).

## Context

`information.created_by` has existed since [ADR 0101](0101-editable-information-and-description-payloads.md) (who may edit a row) and [ADR 0029](0029-attribution-created-by-updated-by.md), but `InformationOut` does not show it. [ADR 0271](0271-beings-the-page-and-its-notes.md) said as much: a note cannot say who wrote it. The being sheet shows a note's author.

## Decision

- `InformationOut` gains `created_by` (the user's id, or null) and `created_by_name`: the author's display name, else nickname, else null. It is null for rows written before attribution existed and for an account since deleted.
- **It is visible exactly when the information is.** The information list and the entity read already filter by the caller's visibility; nothing new decides who sees an author. The maintainer accepted that an author is visible to everyone who can read the note.
- Whether an author was a GM is not in the response. A client that wants "GM" knows the campaign's GMs.
- No new table, no migration. The name is read the way `KnowerOut.name` is.

## Not in scope

Hiding authors; "written by a player" as a note audience (an audience is still told by `is_public` and knowers, [ADR 0271](0271-beings-the-page-and-its-notes.md)); editing authorship.

## Consequences

The notes of a being, an item and anything else with information can show their author. The OpenAPI change is additive.
