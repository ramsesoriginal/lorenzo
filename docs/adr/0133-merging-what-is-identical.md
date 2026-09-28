# 0133 - Merging what's identical: a move that stacks like with like

Status: accepted

## Context

[RFC 0031](../rfcs/0031-equipped-carried-controlled-and-setting-things-down.md) §6 decided that a move may merge what it moves into an identical instance already there. This is slice 4, the last. Setting a stack down makes single items of it ([ADR 0132](0132-setting-things-down.md)), and picking them up again should make a stack again.

[ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md) left out "automatic merging of stacks that land in the same container by coincidence - explicit only". Its `POST .../merge` merges one named instance into another, in the same container, with the same owner.

## Decision

### `merge_identical` on moves

`PUT .../item-instances/{id}/container` and `POST .../item-instances/bulk-move` take `merge_identical: true` in their bodies. It's `false` by default, so every other client moves as before.

After the move, if the container it went into directly holds an instance identical to the moved one, the moved one merges into it, as `POST .../merge` does: its count is added to that one's, and it's deleted.

- **Several identical ones already there**: it merges into the one with the lowest id, so the result doesn't depend on timing.
- **In a bulk move**, what earlier entries moved counts as already there. So things moved together that are identical to each other end up one stack.
- **Only what moves merges.** Identical instances already side by side stay as they are.
- **Nothing merges out of every container.** Setting down has no count to add to.

Capacity and binding are checked for the move as before. Merging changes no load.

### What's identical

Two item instances are identical when they have:

- the same name,
- the same prototype(s),
- the same owner,
- the same stat values of their own,

and neither has information of its own (a description, a note, [ADR 0113](0113-inventory-web-slugs-and-player-notes.md)), a slug, or a formula of its own. The name goes past the RFC's list: a renamed instance, "Grandpa's sword", is its own thing. It's computed in `lorenzo_api/identical.py`.

The pieces a set-down stack became (ADR 0132) are identical to each other, apart from the one that kept the stack's information, notes, or slug.

### What a move answers, and records

- **`PUT .../container`** returns the instance it ended up in: its own, or the one it merged into.
- **A `bulk-move` entry's `item_instance`** is the instance it ended up in too, while its `entity_id` stays the moved one's. A client tells a merge by the two ids differing.
- **Records.** The move is recorded as before. The merge is recorded as an `item_instance.merged` activity entry on the instance it went into, and as a `merged` change in the feed, as `POST .../merge` records one.

### inventory-web

- **Every move into a container asks for it**: dragging a card or a selection, a GM's "Move anyway", and Move to…. An Undo doesn't ask, since it puts one thing back exactly where it was.
- **After a move that merged**, there's no Undo, and the board reloads to show the stack.

This revisits ADR 0044's "explicit only" just far enough: merging is still something a caller asks for, per request.

## Not in scope

- Tidying up identical instances already side by side.
- Merging on anything but a move: creating, giving, handing over.
- loot-bot.

## Consequences

- Twenty arrows set down and picked up again are one stack again.
- A thing with a note, a slug, or a name of its own is never merged away, and neither is anything that differs in a stat value.
- A move can delete the instance it moved. A client that asks for merging has to use the id the answer gives it.
