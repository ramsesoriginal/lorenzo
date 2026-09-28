# 0132 - Setting things down: out of every container, a stack in single items

Status: accepted

## Context

[RFC 0031](../rfcs/0031-equipped-carried-controlled-and-setting-things-down.md) §5 and §7 decided how things are set down, now that an owned item in no container is simply not carried ([ADR 0130](0130-the-controlled-by-listing.md)). This is slice 3.

Two earlier decisions stand in the way:

- **A stack can't leave every container.** Its count lives on its containment row ([ADR 0041](0041-containment-quantity-and-stacking.md)), so `DELETE .../container` refuses a stack with `409 stack-needs-container` ([ADR 0115](0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md)).
- **A deleted container's contents go to its owner** when it's in no container ([ADR 0128](0128-capacity-and-moving-anyway.md)). That put them into the owner's hands, which now means Equipped.

inventory-web's board ([ADR 0131](0131-the-board-on-controlled-by.md)) still offers "Remove from container", which puts an item into the being's hands. Dropping onto Not carried was meant to set a card down. On a being's board, though, the drop handler still read a column without a container as the being's own, so it equipped the card instead.

## Decision

### Setting down a stack

`DELETE .../item-instances/{id}/container` sets an item down: out of every container, still whose it is. A single item leaves as before.

A stack of *n* is still refused with `409 stack-needs-container`, so no client splits one by surprise, unless the request says `?split=true`. Then it becomes *n* single items, all in no container:

- **The stack itself** keeps its id, its information, its notes, and its slug, as one item.
- **Each of the other *n* − 1** is a new instance of the same prototype(s), with the same owner and a copy of every stat the stack has of its own. So a `+1`, or a lifted binding, holds for every piece. That goes further than a split, which copies only `binding` ([ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md), 0129).

It combines with `override` and `lift_binding`:

- **Binding** is checked as for any move ([ADR 0129](0129-binding-and-lifting-it.md)): a bound stack isn't set down unless a GM moves it anyway.
- **Capacity** never refuses taking something out.

What it records:

- **The activity log** gets one `item_instance.container_cleared` entry, its detail saying what the stack was split into.
- **The change feed** records the stack as moved, and each new piece the way it records a newly created instance.
- **The response** is the instance that kept its id, as before.

### Deleting a container that's in no container

Its contents are set down. They no longer go to its owner. A single thing just leaves every container.

A stack among them refuses the delete with `409 stack-needs-container`, naming it, unless the delete says `?split=true`. Then the stack is split as above.

A container that's inside something still passes its contents one level out, counts kept, as before.

### inventory-web

- **Set down** replaces "Remove from container" in Move to…. It's offered for anything in a container, including what's equipped. Putting something into the being's hands is Move to…'s Equipped destination, the column it already lists. A group's board has no Equipped.
- **Dropping onto Not carried** sets a card down. A column with no container now means out of every container on every board, not the being's own column.
- **A stack is asked about first**, whether from the dialog or a drop: "Setting down Arrow ×20 leaves 20 separate items. Set it down?" The board then sends `?split=true`. A selection dropped onto Not carried is asked about once for every stack among it.
- **Undo.** Setting down a single item gets the usual Undo. After a split there's none, and the board reloads to show the pieces.
- **The board of unowned things** sets things down the same way.
- **Deleting an instance** from Manage items asks about a `stack-needs-container` refusal with the API's own words, then deletes again with `?split=true`.

## Not in scope

- Merging what's identical, which picks the pieces up again as one stack: slice 4.
- loot-bot, which keeps `held-by` and doesn't set things down yet.

## Consequences

- Anything can be set down, stacks included, knowingly.
- Setting down a large stack makes as many instances as it had units, until slice 4 merges them again.
- Deleting a container that's lying somewhere no longer hands its contents to its owner.
- `?split=true` is new on two routes. Without it, both behave as before, apart from what a deleted container's contents do.
