# 0238 - inventory-web: "Not in the list", and the unsorted badge

Status: accepted, decided with the maintainer on 2026-10-10.

Slice 4 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) (§8, and the badge of §4). Builds on [ADR 0187](0187-inventory-web-adding-an-item-to-a-board.md) (the board's "Add an item" card), [ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md) (the placeholder item) and [ADR 0193](0193-lorenzo-inventory-import-and-export.md) (what the CLI writes for one). No API change.

## Context

A player can add to their character only what the public catalog lists ([ADR 0186](0186-player-self-service-enforcement.md)). When what they carry is not in it, the "Add an item" card is a dead end: a search finds nothing and there is nowhere to go. The CLI already has the way out, the *unsorted item* ([ADR 0193](0193-lorenzo-inventory-import-and-export.md)): a public placeholder item in each library, carrying the player's own name and notes, for a GM to match to a real item later. The board neither lets a player make one nor shows which things are one.

## Decision

### "Not in the list" on the Add an item card

Under the catalog search, a second action: **Not in the list? Add it as an unsorted item**. It is always there when the card is, and not only after an empty search, since a search can offer near misses that are not what the player means. It opens a second form beside the first:

- **Name** (required, filled in with what was typed in the search), **Description** (optional), **Weight** in pounds (optional, a decimal comma is fine) and **Value** (optional, free text), and the button *Add to {being}*.
- **One create.** `POST .../item-instances` with the library's `unsorted` item as the prototype, owned by the board's being, named as the player wrote it, in Not carried: the same as adding anything from the catalog, so the card's standing ([ADR 0187](0187-inventory-web-adding-an-item-to-a-board.md)), the self-service switch and the API's refusals are unchanged and said in the API's words.
- **Then the notes, as the CLI writes them** ([ADR 0193](0193-lorenzo-inventory-import-and-export.md)): a private note titled "Note" holding the description, and one titled "Details" with a line each for the weight (`Weight: 0.5 lb`) and the value (`Value: 2 gp`), each told to the owner's character so the player can read it back ([ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md)). A GM sees the same two notes whichever tool made the item. If a note fails after the item was made, the item stays and the card says which note was not saved.
- **Undo** works as it does for any added item: the instance is deleted, and its notes with it.
- **The `unsorted` item** is found by its slug, once, and only if it is an item. A library without it gets no form, and the card says so: *This library can't take unsorted items yet. Ask your GM to run `lorenzo seed --layer core`.*

### The badge

A card on the board shows an **Unsorted** badge, a word beside *Bound* and *Someone's*, when the instance's prototypes include the library's `unsorted` item. The item is resolved once per board load, by the same slug; if it cannot be resolved there is no badge and nothing else changes. The item dialog is not changed.

## Not in scope

- **The GM's view for sorting** them ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) slice 5), which is its own ADR.
- **Editing an unsorted item's notes**, or turning one back into a catalog pick: the player's notes are edited as any note is ([ADR 0113](0113-inventory-web-slugs-and-player-notes.md)), and sorting is the GM's.
- **Any other kind** of placeholder, and a limit on how many a player can make ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md): a table matter, not a code one).

## Consequences

- A player is never stuck: what the catalog does not know can still go on their sheet, and the GM gets it with the name, notes, weight and value the player wrote.
- The notes' wording lives in two places, `apps/cli` and `apps/inventory-web`, since they share no code; a test on each side pins the layout.
- A board load makes one more lookup (the `unsorted` slug), and a card is a word longer when it is one.
