# 0241 - inventory-web: the Unsorted view

Status: accepted, decided with the maintainer on 2026-10-10. Numbered 0240 when claimed; renumbered to 0241 when another branch merged 0240 first.

Slice 5 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) (§5 and §6). Builds on [ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md) (the placeholder, the prototype change and the `?prototype_id=` filter), [ADR 0193](0193-lorenzo-inventory-import-and-export.md) and [ADR 0238](0238-inventory-web-not-in-the-list-and-the-unsorted-badge.md) (what makes an unsorted item). No API change.

## Context

Unsorted items now arrive from two sides, an import and a player's *Not in the list*, and nothing lets a GM turn them into the things they stand for. The API can ([ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md): a manager changes an instance's prototype, the name and notes stay, and the holders are told), but only by hand. The same thing is usually unsorted for several players ("Torch", "torch", "Torches"), so the work is mostly the same decision repeated.

## Decision

### A page: Unsorted

`/unsorted/?tenant=…`, linked from the header beside *Items*. It is a GM's page (a campaign GM, as *Items* is); anyone else is told so. It reads **every instance of the library's `unsorted` item** (`GET .../item-instances?prototype_id=`, narrowed by the caller's reach as that list always is) and says so if the library has no such item (*run `lorenzo seed --layer core`*) or nothing is unsorted.

### Grouped by the name the player wrote

Instances are grouped by their name, compared without case, accents, punctuation or surrounding space, so "Torch" and "torch." are one group. A group shows the name as most often written (the first in code-point order if two are equally common, so it never varies), **how many**, and **who holds them**. Opening it lists each instance with a tick box, its holder and the player's notes (*Note*, *Details*: weight and value), read when the group is opened and not before.

### What a GM does with a group

- **Assign**: pick a catalog item and every ticked instance in the group (all of them to start with) takes it as its prototype (`PATCH .../item-instances/{id}` with `prototype_id`, [ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md)). The names and notes stay; the holders are told by the API. Unticking one leaves it unsorted, for the one that was not like the rest.
- **Create**: a catalog item named from the group (the name can be changed first, and *In the public catalog* ticked), its description taken from the first note that has one, then assigned as above. A failed description leaves the item made and says so.
- **Keep**: takes the group out of this page until it is reloaded. Nothing is written; an instance that stays unsorted shows up next time.

Suggestions come first: the library's catalog, ranked against the group's name by a **fuzzy score** (a name or word that contains the other, the words they share, and the letters they share in threes), the best three offered as one-click picks, and a search over the whole catalog for the rest. Matching is on titles only.

### Bulk, and when it goes wrong

An assign or create over a group is **one `PATCH` per instance, one after another**, with a count (*3 of 5…*); the API has no bulk route for it and a loop was fast enough in use, as RFC 0035 §6 allowed for. One failure does not stop the rest: the page says how many were sorted and which were not, in the API's words, and the failures stay in the group to try again.

## Not in scope

- **The German-to-English preprocessing table** the CLI matches with: it lives in `apps/cli` as Python data, and a GM here is a person looking at a list and can read a suggestion; sharing it is a package, not part of this page. Titles are matched as typed.
- **A bulk API route**, unless a loop over `PATCH` proves too slow; then it is its own ADR.
- **Telling the player** (RFC 0035 §7): the API does it on every prototype change ([ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md)).
- **Remembering a Keep.** A GM who keeps something is saying *leave it*, and the cost of seeing it again is one click.
- **Un-sorting** and editing notes: the item page already does the latter ([ADR 0113](0113-inventory-web-slugs-and-player-notes.md)).

## Consequences

- The loop from *a player writes what they have* to *the GM sorts it* is closed in inventory-web, with the player's own words kept on every sorted item.
- A page that sorts many items can partly fail; telling the GM which, instead of stopping at the first, is the cost of not having a bulk route.
- Fuzzy matching is a few lines of TypeScript in `apps/inventory-web`, tested there. If a second app wants it, it becomes a package then.
