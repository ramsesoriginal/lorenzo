# 0388 - New from parent and duplicate, in Bench

Status: accepted, decided with the maintainer on 2026-11-03. Slice K4 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §4, tracked in #976. Builds on [ADR 0216](0216-parents-for-any-entry.md) and [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md) (parents and kinds for any entry), [ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md) and [ADR 0223](0223-bench-making-entries-and-what-waits-for-them.md) (the command layer and making entries), and [ADR 0253](0253-bench-formulas-and-the-stat-vocabulary.md) (formulas).

## Context

RFC 0041 §4 names two author actions: **new from parent**, an entry whose only content is `parents: [P]`, and **duplicate**, an entry with the same kinds, parents, stat values, formulas, description and notes. Both are client-side first: a sequence of routes that exist, so that the first dialog answers what a person wants copied before a server route is built. Bench already has the pieces: `entry.create` takes kinds and parents, and a stat value, a description and a note are commands on an entry the client made the id of ([ADR 0222](0222-ids-made-by-the-client.md)), so each waits for the create. The New form already offers a parent and defaults it to the open entry; what is missing is the action itself, where the person is looking at the entry.

`POST /groups/{id}/duplicate` ([ADR 0064](0064-group-write-api.md)) copies a group's roster, not an entry, and is no precedent for what a copy of an entry holds.

## Decision

### New from this entry

**New under this** in the entry pane, and "New entry under *name*" in the command palette, open the Entries pane's New form with the open entry as its parent, its kind the parent's (a being under a being, an item otherwise) and the name field focused. Nothing is made until Add is pressed. No new route: it is `entry.create` with `parents: [P]`.

### Duplicate

**Duplicate** in the entry pane and "Duplicate *name*" in the palette make a copy as commands, on the same layer as every other edit, so they show at once, wait without a connection, and are undone with Undo (cancelling the create takes the rest with it, [ADR 0223](0223-bench-making-entries-and-what-waits-for-them.md)):

- **Copied:** the kinds it can be made with (an item, a being, a fact, or none), the direct parents, the entry's **own** stat values (an inherited value is not copied; the copy inherits it the same way), and the description and every note, as text.
- **Formulas** the entry holds itself are copied once the copy is on the server: a formula is its own write with its own version and its effect cannot be shown from the mirror ([ADR 0253](0253-bench-formulas-and-the-stat-vocabulary.md)), so they are online and direct, after the create is sent. With no connection the copy is made without them and the pane says so.
- **Named** *Copy of Name*, or *Copy of Name (2)* and so on, the first that no entry of the repository has, so its link name (made from its name, as for any entry made here) does not collide.
- **Not copied:** the link name, which is made from the new name; the main picture and any other picture (a picture is another upload of bytes, and what a person wants copied of one is for the dialog to learn); containment and ownership; who knows what; and a copy link, since a duplicate of something a library copied is the library's own entry with no origin ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §4). **Notes arrive GM only**: a note is made restricted by default, and carrying each note's audience would need a write of its own for each; the pane says so, and Make Everyone's is the existing control.
- **Not offered** for an inventory item or a character: `POST /entities` makes neither ([ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md)), so the action is disabled and says why.

The copy opens, selected, as a new entry does.

### What is not built

- **`POST /entities/{id}/duplicate`.** The server route, in one transaction with the choices the dialog turns out to need, waits for use of this one, as the RFC says. Nothing here fixes its body.
- **Studio.** It has no screen that makes or edits an entry, so it gets neither action.

## Consequences

- An author makes a variation of an entry, or a new entry under a category, from where they are working, offline included.
- A duplicate of an entry with many notes is many commands; each is sent in order, and a failure of one is that command's own to fix, as for any command.
- Notes copied GM only is a visible step a person must undo by hand when the note was Everyone's; the first use of the action is the evidence for a server route that carries audiences.
