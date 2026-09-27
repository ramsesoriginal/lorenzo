# 0124 - Groups own things, and moving something isn't giving it away

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §4–5 decided two things about ownership.

**Groups can own things.** `ownership.owner_character_id` already references any entity ([ADR 0025](0025-character-being-and-ownership.md)), and no route checks what kind the owner is. So an item can already belong to a group (a bare entity named by `group_member` rows, [ADR 0028](0028-knowledge-and-group-membership.md)). Nothing else treats one as an owner:

- a member's player can't see what the group owns;
- a GM can't manage it, because `campaign_ids_for_character` finds no campaigns for a group;
- the change feed only counts characters as holders ([ADR 0099](0099-player-facing-change-feed.md)).

**Carrying isn't owning.** Self-service item writes ([RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md), [ADR 0032](0032-item-and-item-instance-crud-api.md)) are allowed for anything the caller's characters reach through ownership or containment, "uniformly regardless of what the write itself changes". So a player whose character carries Pia's sword in their backpack can give it to someone else, or delete it.

## Decision

### A player reaches through their characters' groups

A player's reach starts from their characters and from every group one of them is a member of: `entity_access.controlled_holder_entity_ids`. It's used everywhere a player's reach is:

- self-service writes (`can_self_manage_entity`);
- which items a read shows ([ADR 0040](0040-item-instance-read-visibility.md));
- whose board held-by answers for ([ADR 0123](0123-held-by-listing-and-the-equipped-column.md)).

So the members of a party see what the party owns, can move it, and can open the party's own board.

A GM's reach grows the same way. The walk from a campaign's characters ([ADR 0035](0035-campaign-scoped-gm-visibility.md), [ADR 0046](0046-gm-reachability-widens-to-surroundings.md)) also starts from their groups.

What a being *holds* doesn't change. Membership isn't holding, so a group's things stay on the group's board, not on every member's.

### Moving and giving are separate permissions

Writes to an item that has an owner split in two:

- **Where it is.** Setting or clearing its container, bulk moves, merging stacks, splitting a stack without naming a new owner, and editing the item itself (`PATCH`). Anyone who reaches it may, as before: a player who holds it, whether or not they own it.
- **Who owns it.** Setting or clearing its owner (with or without handing it over, [ADR 0115](0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md)), bulk-assign, splitting a stack to a different owner, and deleting it. Only whoever controls the owner may:
  - a player whose character is the owner, or is a member of the owning group;
  - a GM of a campaign the owner plays in. For a group, that's any campaign one of its members plays in (`campaign_access.campaign_ids_for_owner`).

A player who holds something they can't give away gets `403 item-not-yours-to-give` saying so: they can move it, but only its owner or a GM can give it away or destroy it. It's its own problem type, not the generic `item-instance-management-forbidden`, so a client can say it in its own words.

An item nobody owns keeps today's rule for both kinds: anyone who reaches it, or any GM in the tenant. Loot drops and claims ([ADR 0052](0052-loot-bot-loot-drop-and-claims.md)) only write ownerless items, so they're unaffected.

Creating an item owned by a group follows the same owner rule: its members' players, or their GMs.

### The change feed counts a group's members

A character also holds whatever a group it belongs to owns, and whatever sits inside it (ADR 0099's relation, extended by one step). So members hear when the party's things are given, moved, or split.

### inventory-web

- **Boards for groups.** "Your characters" lists the groups your characters belong to after the characters themselves. A GM's "Browse a being" search finds groups too. A group's board is its held-by listing. Its first column is named after the group, and dropping onto it takes a card out of every container, since an owned thing in no container is with its owner.
- **Giving to a group.** Every "give to" search also offers groups, marked "(group)".
- **"Remove from container"** puts the item into the board's being's hands, not its owner's. On your own board that's the same place. On a group's board it takes the item out of every container.

### loot-bot

- `/give`'s `to` also offers the tenant's groups, marked "(group)".
- `/inventory` adds one embed per group your characters belong to, after the characters, within Discord's ten-embed limit.
- A refusal to give shows the API's message.

## Not in scope

- Validating what kind of entity may own something. The schema allows any entity, and only beings and groups get support here (RFC 0030 §4).
- Binding for group-owned things. A group isn't a being, so nothing it owns binds (RFC 0030 §8).
- loot-bot commands that give *from* a group. A member moves the party's things on the web board, or a GM gives them away.

## Consequences

- A party's shared loot has an owner, a board, and a feed its members see.
- Players lose one power: giving away or deleting what they merely carry. It becomes the owner's or a GM's act, and the refusal says so.
- An item belonging to someone else in your backpack can still be moved, taken out, or handed back by hand. What changes is only who owns it.
- `reachable_entity_ids` itself doesn't change, so held-by, and everything else that walks from a single entity, keeps its meaning.
