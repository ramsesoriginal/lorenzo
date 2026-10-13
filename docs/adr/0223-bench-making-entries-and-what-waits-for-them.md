# 0223 - Bench: making entries, and what waits for them

Status: accepted, decided with the maintainer on 2026-10-09. The second part of slice B3 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md). Builds on [ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md) (the layer), [ADR 0222](0222-ids-made-by-the-client.md) (ids made by the client) and [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md), [ADR 0216](0216-parents-for-any-entry.md) (the routes that make an entry with kinds and set its parents).

## Decision

- **`entry.create` is a command.** The client makes the entry's id (`crypto.randomUUID()`) when the command is written, so the entry exists for the person at once, in the list and under its parent, and every later command names it. It carries the name, the kinds and the parents; it is sent as `POST /entities` with that id, and a replay (`200`) is as good as a create (`201`). An id the server refuses is **needs attention**, with its words.
- **Kinds are what K2 makes**: an item, a being, both, or none (a bare entry, which is what a group is). A being or a bare entry can be made and have its parents set (K3) here, but only an item has a name that can be changed so far, so the name field of anything else is read-only and says why.
- **What waits for a create.** A command that uses an entry (its own, or a parent it names) waits for any earlier create of that entry still in the outbox. So a rename or a new parent on a new entry, and a new entry under another that is not made yet, are sent after it, in the order written, whether the person is offline or the create is slow. If a create is stuck (needs attention), what waits on it waits too, and other entries carry on. The runner never sends a parent that does not exist yet.
- **Cancel and undo.** A create that has not been sent can be cancelled, and cancelling it **takes with it every command that waits on that entry**: a rename and a child made under it. Undo of the entry's last change does this for a create. Giving up a stuck create (Discard) does the same. **A create that has been sent is not undone here**: that would be deleting the entry, which comes with the library count and the confirmation of RFC 0041 K9 and RFC 0039 section 9, so Undo is disabled and says nothing is queued rather than doing something unasked.
- **The entry pane and the parents pane read the entry's detail** (`GET /entities/{id}`: kinds, parents, children, `ETag`), not an item's, so every kind shows the same way. The parents pane lists the children too: the server's, and those made here that are not sent yet. Renaming still goes to `PATCH /items/{id}` and setting parents to `PUT /entities/{id}/parents`, each with `If-Match`.
- **An inventory item** (`item_instance`) is shown, but its parents are not edited here: it changes its parent through its own route.
- **The form.** The explorer has a name, a kind and a parent (defaulting to the entry that is open), and Add. The new entry opens.

## Consequences

- Bench must not be deployed before the API with W2 is: without it the server would ignore the `id` and give the entry another, and the commands waiting on it would name an id that does not exist. The ADR 0222 change is merged first.
- A create has no base to compare, so there is no conflict on it. A name or a link name that is taken is not a conflict either: names are not unique, and Bench sends no link name, so the entry has none until one is set.
- Deleting an entry, duplicating it (K4), a link name, and a kind added or removed afterwards are later commands on the same layer.
