# 0263 - inventory-web: editing stat values

Status: accepted

## Context

A GM can set an item's tags in inventory-web ([ADR 0112](0112-inventory-web-the-whole-item.md)), and read its other stats in the item view, but cannot change a number or a choice: weight, price, a binding rule. Those were changed with the CLI or by hand against the API. It is a row of the v1.0 checklist (#376).

The API side exists. A stat write sets the item's own value for a stat ([ADR 0037](0037-effective-stat-resolution.md)); `DELETE .../stats/{id}` removes it so the item inherits again, and a write that adds the stat's group is `acquire_group` ([ADR 0142](0142-acquiring-a-stat-group-on-the-generic-stat-put.md), [ADR 0225](0225-stat-writes-that-can-be-checked-and-undone.md)). A decimal stat must be sent with its point ([ADR 0037](0037-effective-stat-resolution.md)), which a browser's `JSON.stringify` does not do for `3.0`. Bench does all of this already ([ADR 0227](0227-bench-stat-values-and-tags.md), [ADR 0247](0247-bench-entry-editor-polish.md)); this is the same rule set on the item page.

Two limits of what the item read gives. An entity's `stats` say what each resolves to and whether that is the item's `own`, not which ancestor it comes from. And the `If-Match` of a stat write is checked against the stat row's own version, which the item read does not carry, so the item's `ETag` cannot be sent for it.

## Decision

- **A Stats section on the item page**, in the GM's group beside Tags, for catalog items and instances alike (they share the page). Players do not see it; the API still decides who may write.
- **One row per stat that is not a tag**, by group and name: the label, the value the item resolves to in a field of the stat's type, and where it comes from in words: "Set on this item", "Inherited", or "Not set". A stat the item has no value for is an empty field.
- **The field fits the type.** A whole number for `int`, a number for `float` (a point or a comma, no exponent), text for `text`, a choice among the values for `enum`. What cannot be read as its type is refused before anything is sent, saying what is wanted.
- **Save sets the item's own value.** Changing an inherited value makes it the item's own. A decimal is written with its point kept (the body is serialized by hand, as in Bench). The write asks for `acquire_group`, so a stat of a group the item does not have yet is given it.
- **"Use inherited" clears it**, with `DELETE .../stats/{id}`; shown only when the value is the item's own.
- **Bool stats stay as they are**: they are tags, edited by the Tags section's three states. A bool outside the `tags` group has no editor here yet.
- **Changed by someone else.** Just before a write the item is read again; if the stat's own state or own value is no longer what the person saw, nothing is written, the page says "Someone changed this stat while you were editing. The current value is shown." and shows the current value. A different inherited value is not a conflict. This is a compare, not an `If-Match`, because of the second limit above; it leaves a window between the read and the write that the server cannot close until the item read carries the stat's version.
- **After a change** the item view above is read again, so readers' view moves with it. Errors are shown as everywhere else on the page.
- **Wording** follows [the identity guide](../brand/identity.md) §14.3: "library" for the tenant, plain words for the rest ("Use inherited", not "DELETE"). The stat label is the one the item view uses.
- **Not here:** making, renaming or deleting stats, groups or enum values (the vocabulary), formulas. A stat that holds a formula shows its value; trying to set a value on it is refused by the API with its own message.

## Consequences

- A GM can set up an item's numbers and choices without leaving the page, and undo a value by clearing it.
- Stat values and tags are now two sections for what is one family of API calls; the split is by type, which is what the person sees.
- The compare before a write costs one read per save, and the window it leaves is the price of not having a stat version on the read. If the item read gains per-stat versions, the compare becomes an `If-Match` and this ADR is amended.
- The slice has no dependence on anything new in `apps/api` or `packages/api-client`.
