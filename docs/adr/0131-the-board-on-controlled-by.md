# 0131 - The board on controlled-by: every column in one row, and read-only ones

Status: accepted

## Context

[RFC 0031](../rfcs/0031-equipped-carried-controlled-and-setting-things-down.md) §8 decided how inventory-web's board shows what a being or group controls, and [ADR 0130](0130-the-controlled-by-listing.md) built the listing it reads. This is slice 2. Setting things down, and the stack question it needs, are slice 3.

The board reads `held-by` ([ADR 0123](0123-held-by-listing-and-the-equipped-column.md)) until now. That's where both things testing turned up come from: an owned chest in no container under Equipped, and an empty backpack with no column.

## Decision

### What the board reads

A character's board, a group's board, and a GM's board for any being read `GET .../item-instances/controlled-by/{entity_id}`. The board of unowned things keeps reading `GET .../unowned` ([ADR 0077](0077-unowned-item-instances-endpoint.md)). inventory-web no longer calls `held-by`. loot-bot still does.

`boardColumns.ts` turns either answer into one list of columns, in the order the listing gives them. It's pure, so the wording is tested without a page.

### The columns

All of them sit in the one `grid full-width h-scroll` row.

| Column | Title | Dropping onto it | Says when empty |
| --- | --- | --- | --- |
| `equipped` | Equipped | puts the item into the being | Nothing equipped. |
| `not_carried` | Not carried | takes it out of every container | Nothing here. |
| `container` | the container's name | puts the item inside | This container is empty. |
| `read_only` | the container's name | takes nothing | never empty |

- **Equipped and Not carried** carry the brand's `glow-canonical`, the maintainer's choice. The row gets room above and below so the halo isn't clipped. A group's board has no Equipped.
- **Dropping onto Not carried** is what dropping onto a group's own column already did: `DELETE .../container`. So a single item is set down, and a stack is refused with the API's own message until slice 3 asks and splits it. Keeping the drop out of this slice would take it away from group boards.
- **A read-only column** takes no drops. Its cards can't be dragged, and they open without Move to…. Giving stays, since what's there is Owned.
- **Notes** come from `path` and `container_kind`, as `held-by`'s did: "In Backpack", "Brisk has these", "In Carriage, in Stable". A container in nothing, that nobody carries, says "Not carried". The pill is green for a carried column and amber for any other, as before.
- **Contents not shown.** When `contents_hidden`, a column with nothing listed says "Contents not shown." instead of its empty text, and one with cards ends with "Other contents not shown."
- **"Give what's inside…"** is only offered for a container whose column lists something. An empty backpack has a column now, and nothing in it to give.

### Owner marks, and the rest

Owner marks, bound marks, searching, selecting, giving, splitting, and merging work as before, across every column. "Remove from container" still puts an item into the being's hands, or out of every container on a group's board. It becomes Equip and Set down in slice 3.

### The end-to-end scenes

A scene's character now carries what it's meant to carry: `packed()` puts the backpack and belt pouch into the character, where before it only gave them an owner. `world.carried()` reads `owned-by`, which shows both the same way, so what the tests expect of it doesn't change.

## Not in scope

- Setting down a stack, Equip and Set down in the item dialog, and deleting a container that's in no container: slice 3.
- Merging what's identical: slice 4.
- loot-bot.

## Consequences

- The chest that isn't carried shows under Not carried, and the empty backpack gets a column to drop onto.
- A board lists what its being controls, including what its groups own, without the rest of every group's things.
- A single item can be set down by dropping it on Not carried already. A stack can't be until slice 3.
- `boardColumns.ts`'s `heldBoard` and the `held-by` client call are gone. loot-bot keeps its own.
