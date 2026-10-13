# 0217 - Entity kinds: the routes, the updates and the publish check

Status: accepted, decided with the maintainer on 2026-10-08. Slice K2 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md), tracked in #553. Builds on [ADR 0218](0218-the-copyable-table-registry.md) (the registry of copyable tables), [ADR 0121](0121-repository-updates-and-re-sync.md) (updates) and [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md) (the detector, which already lists `kinds_changed`); needed by Bench and Studio to author a being, a sentient sword or a category node.

## Context

Kinds are marker rows: an entry is an item if it has an `item` row, a being if it has a `being` row, and may be both ([ADR 0012](0012-entity-table.md), [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md)). The API made them only through routes of their own: an item through `POST /items`, a character through `POST /characters`, and nothing deleted a being. A kind changed after the first publish was ignored by updates (`_IGNORED = {"kinds"}`), so a library's entry could drift from its repository's without a word, and the detector listed `kinds_changed` for a change the engine never carried. This slice builds the routes, makes updates carry kinds, and gates publishing on a list of combinations a round-trip matrix proves.

## Decision

### Making an entry: `POST /tenants/{id}/entities`

The body is `{name, slug?, kinds?, parents?, in_public_catalog?}` and the answer `201` with the entry's detail, a `Location` and an `ETag`. The entry, its link name, its marker rows and its parent edges are made in one transaction. `kinds` is a list of `item` and/or `being`; empty (or left out) makes a bare entry, which is what a group is, and a kind listed twice is one. `in_public_catalog` is valid only with `item` and is a `422` otherwise, whatever its value. The gate is the one `POST /items` has: a member of the library.

`409` for a link name already taken, `422` for a parent that is not an entry of the library, and nothing is made in either case. `character` and `item_instance` are not values of `kinds` (a `422`): a being becomes a character through `PUT /characters/{id}`, an inventory item is made from a catalog item. The activity entry is `entity.created`, with the kinds and the number of parents.

### Adding and removing a kind: `PUT` and `DELETE /tenants/{id}/entities/{entity_id}/kinds/{kind}`

`kind` is `item` or `being` (another value is a `422`). Both honour `If-Match`, touch the entry (`updated_by` and `updated_at`, so its `ETag` moves even for the same person), and answer the entry's detail with the new `ETag`.

- **`PUT`** answers `201` when the marker row was made and `200` when the entry already had the kind and nothing changed, as `PUT /characters/{id}` does. `item` may carry its own column in the body, `{"in_public_catalog": true}`; sent to a kind that has none it is a `422`, and sent to an `item` the entry already is it sets the column (`200`): a `PUT` says what the kind is. An **inventory item may take `being` (a summoned creature kept as inventory) and never `item`**: `409`.
- **`DELETE`** takes the kind away and answers `200` with the entry, which survives, whether or not it had the kind (as the other sub-resource deletes, [ADR 0064](0064-group-write-api.md)). Removing `item` is `409` while an inventory item inherits from the entry directly, the guard `DELETE /items/{id}` has; removing `being` is `409` while the entry is a character, whose key would cascade away with it: demote it first ([ADR 0036](0036-user-player-character-crud-api.md)).
- Each change that happens is one activity entry, `entity.kind_added` or `entity.kind_removed`, with the kind; one that does not happen is neither written nor logged.

### Deleting an entry: `DELETE /tenants/{id}/entities/{entity_id}`

`204`, with `If-Match`, the gate of the other routes here, and **the guards of every kind the entry has, composed**, so that a being made by this API can be removed and nothing is deleted from under something that depends on it:

| The entry is | Answer |
| --- | --- |
| an inventory item | `409`: its own route moves what it holds back out ([ADR 0128](0128-capacity-and-moving-anyway.md)) |
| a character | `409`: demote it first |
| a campaign's own entry | `409`: it goes with its campaign (the key is `RESTRICT`) |
| a catalog item an inventory item inherits from | `409`, as `DELETE /items/{id}` |
| anything else: a bare entry, an item, a being that is no character, an item that is also a being | deleted, with its kind rows, link name, parents and stats |

The kind-specific deletes keep working and delete the whole entry as before. What a library copied is untouched: it sees the entry as removed upstream. The count of libraries that hold it is K9's. A being that owns or holds things, or that others inherit from, goes as an item does: the edges go, the others stay.

### What an entry says it is

`GET .../entities/{id}` and the answers above gain **`kinds`**: `item`, `item_instance`, `being`, `character`, in that order, the same four values `GET .../entities/resolve` reports. The two reads also carry an `ETag` now, the weak tag from `updated_at` that items have, so a client has something to send in `If-Match` for a being or a bare entry.

### Updates carry kinds

`repository_updates.py` no longer ignores `kinds`: a changed set of kinds is a field of the entry's row in the diff, a set like prototypes and enum values, merged element by element with `added` and `removed`, and never a conflict. A library's own extra kind (a character it made of its copy) is not a difference.

- **Kind added** (`item` or `being`): the marker row is added to the library's copy. An added `item` takes the repository's `in_public_catalog`. It is skipped, with the reason, if the library's copy is an inventory item (never an `item`).
- **Kind removed** is applied only if the library's copy allows it, and otherwise skipped with the reason, as an enum value still in use is: `an inventory item still inherits from it here` for `item`, `it is a character here` for `being`. A skipped field is offered again.
- **`character` and `item_instance`** are not changed by an update, whichever way: `a character is made in the library itself`. A repository that demotes a character does not demote the library's, which would end its roster.
- An entry's `in_public_catalog` going from a value to nothing (the entry stopped being an item) changes nothing by itself: the kind is what is removed, or refused, and a refusal must not make the library's item private.
- A kind change is a release's `kinds_changed` breaking row ([ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md)), so a library applying it confirms it; the words Kind added and Kind removed are the hub's to put on it. Updates and the detector are held to one definition: both read the entry's sorted kinds, and a test changes each kind of two entries and asserts that the detector reports `kinds_changed` exactly when the library is offered a change of `kinds`, and neither for a rename.

### Publishing: a list of combinations a matrix proves

A draft repository may hold any combination of kinds the routes allow. **Publishing** (`PUT .../published`, and so every release) is refused with `409 repository-has-unproven-kinds` while an own entry has a combination not in `PUBLISHABLE_KIND_COMBINATIONS` (`lorenzo_api/entity_kinds.py`), whatever `acknowledge_breaking` says; nothing is published. The problem carries `entries` (`id`, `name`, `kinds`) and says it in words: “Ashfang” (being and character and item). `GET .../release-preview` lists the same as `unproven_kinds`, so the composer says it before the publish is made.

The list is: no kind; `item`; `being`; `item` and `being`; `item_instance`; `being` and `character`. The last two are what repositories held before kinds could be combined. Any other combination (an inventory item that is also a being, an item that is also a character) is creatable in a draft and not publishable until it is proven and added.

**The matrix** (`tests/test_kind_matrix.py`) runs each combination, in a plain repository and in a bridge ([RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md)), through a first copy (kinds, parent, stat, note), an update that adds the entry, an update that changes its name, parents and stats (a note changed upstream is not carried, which the test says), a kind added and removed after the copy where a route can make the change, and a purge (no marker row left of the old copy; in a bridge, the parent the bridge attached is shown as taken and no longer there). A kind is added or removed only for the four combinations a route can change; for an inventory item and a character it is made and unmade in the library. A test holds the matrix to the list in both directions: a combination added to the list without a row fails, and a row that is not on the list fails. It passes for every combination on the list with no change to the copy or update engine, an item that is also a being included.

## Not in scope

- The Bench and Studio screens, and the library count in the delete dialog (K9).
- `character` and `item_instance` as values of `kinds`; making either through this API.
- Whether an item that is also a being behaves in `GET /beings`, the item list's joins and a GM's reach: the audit of RFC 0041's first spike. The matrix proves copy, update and purge only.
- Parents of an existing entry (K3's `PUT /entities/{id}/parents`): `POST /entities` takes `parents` with its own check that every id is an entry of the library, which the two routes share when both are in.
- Kinds as data, and a marker `kind` on the registry's lines: the registry lists tables ([ADR 0218](0218-the-copyable-table-registry.md)); a new kind adds its line and its row in the matrix.

## Consequences

- An author can make a being, a sentient sword or a category node, change what an entry is, and delete an entry that is no character, inventory item or campaign's own, without a route per kind.
- Updates now show and apply a changed kind set, so an update test that assumed kinds are skipped changes with it (none did in this repository).
- `GET .../entities/{id}` has a required `kinds`, which a generated client that builds the shape by hand (a test fixture) must now give; `release-preview` has a required `unproven_kinds`. Both additions, so the check for breaking changes finds none.
- A repository that holds an inventory item that is also a being, or any combination not on the list, cannot be published until it is changed or proven.
