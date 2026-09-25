# 0115 - Giving can hand an item over, and a stack leaves a container into its owner

Status: accepted

## Context

[ADR 0051](0051-loot-bot-give-command.md) decided that giving an item changes its owner and nothing else. It stays in its container, because ownership and containment are independent facts. ADR 0051 named the way out itself: an explicit opt-in to "also uncontain it", if leaving the item behind proved surprising.

inventory-web's board showed the problem ([ADR 0114](0114-inventory-web-end-to-end-tests.md)'s tests pin it). After Pia gives Brisk her spellbook, it's his, but it's still in her backpack. His board shows a "Backpack" column for a backpack he doesn't own.

Uncontaining has a trap. A stack's count lives on its containment row ([ADR 0041](0041-containment-quantity-and-stacking.md)). An item with no row has no count. ADR 0041 says `DELETE .../container` moves a whole stack "as one unit, `quantity` riding along". In fact it deletes the row, and the count with it: inventory-web's "Remove from container" turns "Arrow ×3" into one Arrow.

ADR 0041 expected the fix: a stackable thing should always be contained by something, "even a structural bucket (e.g. a per-character 'Equipped' or 'Carried' entity)". Containment already allows any entity to contain any other ([ADR 0016](0016-containment.md)). The change feed already counts a character that contains something as holding it ([ADR 0099](0099-player-facing-change-feed.md)).

## Decision

The maintainer chose the character as the bucket: a thing carried in no container is contained by the character itself.

### A character carries what's in no container

An item can be contained directly by a character, with `PUT .../item-instances/{id}/container` naming the character. That's what "carried, in no container" means from now on. A stack there keeps its count.

- **Listing.** `GET .../item-instances/owned-by/{owner}` lists an item contained directly by its owner with the loose ones, in the group whose `container` is null. To a reader, it's in no container.
- **The item itself.** `ItemInstanceOut.container_entity_id` still names the character, so a client can tell.

Existing uncontained items stay as they are. Being uncontained remains valid for a single item (ADR 0041), so there's no backfill.

### Giving can hand it over

`SetOwnerRequest` (`PUT .../owner`) and `BulkAssignItem` (`POST .../bulk-assign`) gain `move_to_owner: bool`, default `false`.

- **True.** The item is also contained by its new owner, in the same transaction: out of the giver's backpack, into the recipient's hands, its count kept.
- **A partial give** (bulk-assign with a `quantity`, which splits with an owner per [ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)) puts the split-off stack there too.
- **False** is ADR 0051's behaviour, and the default. Handing over is the opt-in ADR 0051 asked for.

Recording follows the existing rules:

- **Activity log.** A give that also moves logs `item_instance.container_set` beside `item_instance.owner_set` ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md) logs real moves).
- **Change feed.** It records one change. Its holders before and after already tell the giver it left and the recipient it arrived.

### A stack can't leave every container

`DELETE .../item-instances/{id}/container` on a stack of more than one is refused with `409 StackNeedsContainerError`, because deleting the row would drop its count. A client moves the stack into its owner instead, with `PUT .../container`. A single item leaves its container as before. This corrects ADR 0041's claim.

### inventory-web

- **Give to…,** for one item or a selection, gets a **Hand it over** checkbox when what's given is in a container. Its note says the alternative: "Otherwise it stays in the Backpack, theirs now." It starts unchecked.
- **Undo** of a handed-over give restores the container as well as the owner.
- **"Remove from container",** and dropping cards on the character's own column, put the item into the character, so a stack keeps its count. On the board of unowned items there's no character to hold it. There the old `DELETE` stays, and the API refuses a stack with its message.
- **The board** shows an item contained by its owner in the owner's column: the owned-by grouping above puts it there.

## Not in scope

- A hand-over option on loot-bot's `/give`. It keeps ADR 0051's behaviour. loot-bot never clears a container, so the `409` doesn't touch it.
- Moving the recipient's gift into one of their containers. The giver can't see the recipient's containers ([ADR 0040](0040-item-instance-read-visibility.md)).

## Consequences

- A gift can leave the giver's inventory completely, stacks included, and the recipient's board shows it where they'd expect it.
- A stack can no longer lose its count by leaving a container.
- "In no container" has two representations: no containment row (a single item, as before), or a row pointing at the owner. The owned-by listing hides the difference. A client reading `container_entity_id` itself has to treat "contained by its owner" as loose.
