# 0125 - Giving a container with what's inside it, and giving everything inside

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §9 decided that giving a container should be able to give what's inside it too, at any depth, and that there should be a way to give everything in a container without the container itself. Today a give changes one item's owner ([ADR 0051](0051-loot-bot-give-command.md)), and bulk-assign changes several, each named ([ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)).

Giving a backpack changes who owns the backpack, not the rope, the rations, and Pia's potion inside it. So a player who wants to give it all has to find and give each thing, and a client only sees what it lists.

[ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md) set who may give what. A container's contents can belong to several people, so giving "everything inside" can only ever give part of it.

## Decision

### Giving a container with what's inside it

A `bulk-assign` entry gains `with_contents` (default `false`). When set, the entry's item is given as before. Then everything inside it, at any depth, gets the same new owner, except:

- what's already the recipient's, which is left alone and not reported;
- what the caller may not give, by ADR 0124's rule: something that isn't theirs, their group's, or unowned, unless they're a GM. It keeps its owner and is reported as kept, with the refusal;
- a being inside it, such as a familiar in a backpack or a passenger in a carriage, and everything the being carries. That's the being's, not the container's, so it isn't considered or reported.

Whether the caller may give something inside is judged as things stood before the give. Handing the container over doesn't first put what's inside out of their reach.

Nothing moves. Contents stay where they are, only their owner changes, unless the entry also hands the container over (`move_to_owner`, [ADR 0115](0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md)). Then its contents go with it physically, because they're inside it.

`with_contents` with a `quantity` is refused (`422`): splitting off part of a stack gives nothing inside it.

Each result gains `contents`, one entry per thing inside that was considered:

- `entity_id` and `title`;
- `status`, either `ok` or `kept`;
- `owner`: who owns it afterwards, as a summary, so a client can say whose a kept thing stays;
- `problem`, for a kept one.

`PUT .../owner` stays a single-item give. A client giving with contents uses a one-entry bulk-assign, whose result can say what stayed.

### Giving everything inside, but not the container

`POST /tenants/{tenant_id}/item-instances/{entity_id}/give-contents`, with body `{ owner_character_id, recursive }` (`recursive` defaults to `true`), gives everything inside the container to the new owner, by the same rules. It answers with the same per-thing entries as `contents` above. It never fails as a whole ([ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)): each thing is given or kept on its own.

The caller must be able to move the container itself (ADR 0124's "where it is" rule). A container they can't reach isn't one whose contents they may look into.

### Dry runs

Both take `?dry_run=true`. Everything is done and checked, then rolled back, the way a repository copy's dry run is ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)). It's a query parameter here because bulk-assign's body is a list.

So a client can ask before it acts, and both clients word the question from the same answer: "Give the Backpack and 3 things inside it to Brisk? 1 belongs to Pia and stays hers."

### Recording

- **Change feed.** Every thing given along is recorded as its own give ([ADR 0099](0099-player-facing-change-feed.md)), so everyone who held it is told.
- **Activity log.** Bulk-assign's one entry counts what was given along as well ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)). `give-contents` records one `item_instance.contents_given` entry, counts only.
- **Dry runs** record nothing.

### inventory-web

- **"Also give what's inside"** is a checkbox in a container's Give to…, shown when the board shows something inside it. With it ticked, picking a recipient first asks with a dry run's answer, then gives.
- **"Give what's inside…"** in a container's actions gives its contents, not itself, asking the same way.
- **No Undo** after either. An Undo would only give the container back, not what came with it.

### loot-bot

- **`/give` of a container** that holds something asks with a dry run's answer. It offers "Give" (just the container), "Give with what's inside", and "Cancel".
- **`/give-contents`** (`container`, `to`) gives what's inside one of your containers, after the same kind of question.

## Not in scope

- Giving everything a being carries in one go. Its Equipped isn't an item.
- Binding. A bound thing inside will be kept too, by slice 7's rule, when there is one.
- Undoing a give with contents.

## Consequences

- Handing over a packed backpack is one action, and what can't go with it is named before anything moves.
- A container's contents can end up with several owners. That's the point: what belonged to someone else stays theirs.
- `PUT .../owner` and bulk-assign without `with_contents` behave exactly as before.
