# 0134 - Board refinements: who has a column, read-only marked, and your character opened for you

Status: accepted

## Context

Testing the board after [RFC 0031](../rfcs/0031-equipped-carried-controlled-and-setting-things-down.md) ([ADR 0130](0130-the-controlled-by-listing.md)–[ADR 0133](0133-merging-what-is-identical.md)) turned up five things:

- **Moving a container doesn't update its column.** Dropping a chest from Not carried onto Equipped moves its card, but its column still says "Not carried". A drag moves the card on the page and doesn't ask for the board again, so each column's note stays what it was when the board loaded.
- **"Not carried" says too little.** A container that another being carries says "In Alice", or only "Not carried" once the board is out of date, where "Not carried, with Alice" would be clear. The listing's `path` can't say which of its entries is a being: an `EntitySummary` has no kind.
- **Read-only columns look like the others.** Nothing in their markup says they're read-only.
- **A player with one character has to pick it.** The board opens empty unless the URL names a character.
- **Nothing is remembered.** Coming back to the board, a player picks their character again each time.

## Decision

### `carried_by` on each column

Each column of `GET .../item-instances/controlled-by/{entity_id}` gains `carried_by`. It's the nearest being around the column's container, by containment alone, or `null` when no being carries it. So a pouch in Alice's backpack is carried by Alice, and so is Alice's backpack.

On the board, a column that the board's being doesn't carry, but some other being does, says "Not carried, with Alice". This replaces "In Alice" and its longer forms. A being's own column still says "Brisk has these", and everything else is noted as before.

### A moved container brings the board up to date

After a drag that moves a card with a column of its own, the board loads again, so every note is right. The Undo stays. Move to…, and every other action, already reload the board.

### Read-only columns are marked

A read-only column carries the class `board-column--read-only`, styled with a dashed border, so it can be told apart and restyled.

### The board opens on your character

When the URL names no character or group, the board opens one by itself:

1. **The one last opened** on this library's board, in this browser, if it's still in the list.
2. **Otherwise your only character**, if you have exactly one.

It does the same on switching back to "Your characters". Choosing a character or group on the board remembers it, in `localStorage` and per library, the way the last library is ([ADR 0131](0131-the-board-on-controlled-by.md)'s branch, `lastTenant.ts`). Logging out forgets it, so the next person to log in on this browser doesn't open someone else's character.

A URL that names a character or group still wins, as before.

## Not in scope

- Remembering what a GM browses, or the board of unowned things. Only your own characters and groups are remembered.
- A place a thing is set down ([RFC 0031](../rfcs/0031-equipped-carried-controlled-and-setting-things-down.md)'s "Places").

## Consequences

- A column says who has it, not only where it is.
- A player with one character lands on their board straight away, and everyone else lands on the one they used last.
- `carried_by` is a new field in the listing, not a change to one.
