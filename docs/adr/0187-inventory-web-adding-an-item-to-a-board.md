# 0187 - inventory-web: adding an item from the board

Status: accepted, decided with the maintainer on 2026-10-05.

The first client of [RFC 0034](../rfcs/0034-player-self-service.md)'s slice 3: where a player makes their own item, which [ADR 0186](0186-player-self-service-enforcement.md) made something the API allows.

## Context

A player can now make an instance of a public item for their own character, owned and not carried, when self-service is on for them ([ADR 0185](0185-player-self-service-the-switches.md), [0186](0186-player-self-service-enforcement.md)). Nothing in inventory-web offers it: a GM instantiates from `/items` ([ADR 0072](0072-item-catalog-prototype-set-editing.md) onward), and a player has no way to reach that page's form. The board is where a player already looks at their things, and its new item should arrive there, in Not carried, ready to be moved.

## Decision

### Where, and for whom

A card under the board's toolbar, **Add an item**, on a being's board. What it shows depends on whose board it is and who is looking:

| Viewer, board | The card |
| --- | --- |
| A player, their own character, self-service on for it | The form |
| A player, their own character, self-service off for every one of its seats | A note: the GM has switched this off for that character |
| A GM of the library, any being | The form (a manager is judged by the manager rules, so the API decides) |
| Anyone, a group's board, the board of unowned things | Nothing: a player can't create for a group, and unowned loot is a GM's to place |
| A player, another player's character | Nothing |

"On" is read from `GET /me`'s `players[].self_service_effective` ([ADR 0186](0186-player-self-service-enforcement.md)): any of the viewer's seats in this library that plays the character is on. That is a convenience to decide what to show, never authorization: the API's answer stands, and an answer it gives (switched off, not in the public catalog) is shown as it says it.

### The form

- **Find it.** A search field over the catalog the viewer may list: for a player the public catalog ([ADR 0116](0116-players-read-catalog-items-and-a-public-catalog.md)), for a library member the whole of it. It offers the first few items when focused, before anything is typed, since a player can't know the names a GM chose, and says so when there is nothing: "Nothing is in the catalog yet." or "No item matches “…”."
- **Then confirm.** Picking an item doesn't create it. It shows what was picked, an optional name ("Call it": the item's own title is the default, as for any create), and one button, **Add to *Alice***, with a way to pick again. Creating something is a write and a stray click on a suggestion shouldn't make one.
- **What it makes.** One instance, owned by the board's character and in no container: *Not carried* ([RFC 0031](0031-equipped-carried-controlled-and-setting-things-down.md)), which is where ADR 0186 puts it. No slug, no quantity, no container: self-service allows none of them, and a GM has `/items` for those. More than one is "add it again".
- **After.** The board reloads, the new card is revealed, scrolled to and focused, and a line says what happened ("Added Sword to Alice's Not carried"), through the same one-slot **Undo** banner a give or a move uses. Undoing deletes the new instance, which its owner may.
- **When it fails**, in the API's own words, in the card, with the form still there: a switch turned off since the page loaded, a catalog item un-published, a library that is full.

### Smaller changes it needs

- `createItemInstance` takes an optional `name`.
- The combobox gains two optional behaviours, `browseOnFocus` and an `emptyMessage`, used only here. Every existing use is unchanged.
- The board takes the holder's name with `load`, since a character's own board has no "Viewing …" line to read it from, and `reload` returns when it is done, so the new card can be revealed.
- The undo controller learns one more kind, `delete-created`.

## Not in scope

- Adding into a container, or more than one at a time, or with a slug.
- Giving oneself a pack. The API allows it ([ADR 0186](0186-player-self-service-enforcement.md)); a screen for it is its own decision.
- account-hub's switches, which are the GM's side of this and the next slice of RFC 0034.
- Phones: inventory-web's phone support is its own v1.0 row.

## Consequences

- A player's loop is complete in one place: find it, add it, see it land, move it.
- A GM gets the same shortcut on any board, and `/items` stays the place for the unusual create.
- The "off" note tells a player why, rather than leaving them to wonder where the feature went.
- One more reader of `GET /me` on the board, which the page already fetches for the GM check.
