# 0230 - Bench: the explorer as a tree, and kinds

Status: accepted, decided with the maintainer on 2026-10-09. Slice W-D of [RFC 0042](../rfcs/0042-bench-workbench-interface.md) (several parents, kinds menu, bare entries). Builds on [ADR 0229](0229-parents-in-the-entry-list.md) (parents in the entry list), [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md) (the kind routes) and [ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md) (the command layer).

## Context

The explorer was a flat list by name. An entry can have any number of parents ([ADR 0216](0216-parents-for-any-entry.md)) and any of the kinds item and being, or none ([ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md)); Bench could show neither, and could not change an entry's kinds.

## Decision

### The explorer

- **Three orders**, as a toggle at the top of the pane: **Inherits** (the default: a tree of what entries inherit from), **Kind** (grouped: items, beings, inventory items, characters, bare entries) and **A to Z** (the flat list there was). The choice is remembered on the device.
- **A tree has a row for each place an entry has.** An entry with two parents shows under both, with a mark that says it has several parents, and selecting it marks every row it is in. The pane says "N entries · M places in the list" when the two differ. An entry whose parents are not in the list is a root; a cycle (the API refuses them) cannot loop the tree.
- **Folding** an entry hides what is under it; folds last until the page is loaded again.
- **The rows are plain data** (`buildRows`), tested alone; the pane only draws them. They are built from the list's `parent_ids` ([ADR 0229](0229-parents-in-the-entry-list.md)), and what the person has changed and not yet sent shows at once: a new entry under its parent, an entry moved by a parents change. A kind change moves it between groups.

### Kinds

- **One command, `entry.set-kind`, for one kind** (`item` or `being`): the value is whether the entry has it. Each kind is its own field, so the three-way compare, undo and Keep mine / Use theirs work as for the other fields, and a change can fail on its own (it needs no all-or-nothing rule for several routes). A yes or no cannot be in conflict: the server has the base, so it is sent, or has mine, so it is already there.
- Sent with `PUT .../kinds/{kind}` or `DELETE .../kinds/{kind}` and `If-Match`; a stale one reads the entry again once.
- **A "What is this entry?" box** on the entry gives the two kinds as checkboxes, with the prototype's words. Both off is a bare entry, which is what a group is. An inventory item cannot take `item` (the API says `409`), so that box is disabled for one; a refusal the box cannot foresee, such as taking `item` from an entry that inventory items inherit from, is Needs attention with the API's words.
- The other kinds the API knows (inventory item, character) are made by their own routes and are shown, not edited. The prototype's sketched kinds (location, event, and the rest) are not offered: they are not in the API.

## Not here

- Dragging an entry to a new place in the tree, "Move to…" and a filter box. Parents are changed in the entry's own pane, as before.
- The bulk export for the offline mirror (RFC 0039 W3): the list's parents are enough for the tree, not for offline.

## Consequences

- Hierarchies and several parents are visible; "where does this come from" no longer needs opening each entry.
- The tree is drawn from the whole list, so a very large repository is one long scroll until folding and a filter box exist.
