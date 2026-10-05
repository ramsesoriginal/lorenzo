# 0190 - `lorenzo item` and `lorenzo character`: self-service from the command line

Status: accepted, decided with the maintainer on 2026-10-06.

## Context

The API lets a player make instances for their own character ([ADR 0186](0186-player-self-service-enforcement.md)), and the web board has a card for it ([ADR 0187](0187-inventory-web-adding-an-item-to-a-board.md)). The CLI authenticates as a person, so a player can already run `lorenzo pack give <pack> --owner <their character>`. But nothing makes a single item or a stack, and finding what you may add, or which character is yours, takes `lorenzo api`. Importing an inventory later ([RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md)'s follow-up) is a sequence of exactly those creates, so it should rest on commands that already work for a player, not on a path only a GM has.

## Decision

Three small commands over operations the API already has. No API change.

- **`lorenzo item list --tenant T [--query Q] [--json]`**: the catalog you may list: for a player the public one ([ADR 0116](0116-players-read-catalog-items-and-a-public-catalog.md)), for a library member all of it. Id and title, one row each.
- **`lorenzo character list --tenant T [--all] [--json]`**: your characters, or with `--all` the library's, which is who you can give things to. Id, name, PC or not.
- **`lorenzo item add ITEM --tenant T [--owner CHARACTER] [--name N] [--quantity N] [--into CONTAINER] [--json]`**: makes one instance of the item, owned by the character, in no container: *Not carried*.

### Names, not only ids

- **ITEM** is an id, a slug, or the item's exact title (case-insensitive). A title that matches several is refused with the candidates and their ids, never guessed.
- **`--owner`** is an id or a name of one of **your own** characters, and can be left out when you control exactly one. Another being's id is passed through, since a GM may make things for it; the API decides.
- **`--into`** is the id or slug of a container instance. A player's own items have no slug, so an id, which `item add --json` prints.

### What the API decides, and the one thing the CLI checks

Standing, public items, the switch, no slug, a container only if the character holds it: all the API's, answered in its own words, as for the web ([ADR 0186](0186-player-self-service-enforcement.md)). The CLI takes no `--slug`, which a player may not set, and checks one thing itself: `--quantity` above 1 needs `--into`, since a count lives on a container ([ADR 0140](0140-a-stack-when-an-item-instance-is-created.md)), and says so before asking.

Printed as `Added Rope to Ashfang.` with the new id on its own line, so a script can read it; `--json` prints the instance.

## Not in scope

- Moving, equipping, giving or deleting what was made: `lorenzo api` still does those, and each is its own command when something needs it.
- The importer for an inventory, which is what this is groundwork for.
- A dry run: creating an instance has none.

## Consequences

- A player can build up a character's gear from a script with commands that follow the same rules as the screens.
- An inventory import has the primitives it needs, and its own mapping questions can be decided separately.
- Looking an item up by title costs one list call, which is why an id or a slug stays the precise form.
