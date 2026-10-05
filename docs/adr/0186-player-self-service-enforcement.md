# 0186 - Player self-service: what a player may make, and loot-bot's Sack

Status: accepted, decided with the maintainer on 2026-10-05.

Slice 2 of [RFC 0034](../rfcs/0034-player-self-service.md). [ADR 0185](0185-player-self-service-the-switches.md) stored the two switches; this one reads them. It tightens what a player could already do, so it is a contract change for existing callers, and it changes loot-bot in the one place it depended on the old width.

## Context

Until now `POST .../item-instances` accepted an owner that was one of the caller's characters, or a group one of them is in, and nothing else was asked: any item, any container, no switch ([ADR 0032](0032-item-and-item-instance-crud-api.md), `_authorize_create_instance`). RFC 0034 §4 says what self-service should be. `POST .../item-instances/from-pack` ([ADR 0149](0149-giving-a-pack-from-the-api.md)) shares that gate.

## Decision

### Who stands how

`_authorize_create_instance` now returns whether the caller has standing **only through self-service**.

1. **A manager comes first** (`can_manage_campaign` on any campaign the owner plays in; for an ownerless instance on any campaign of the tenant) and is judged by the manager rules and nothing else, as before. A GM who also plays is a manager.
2. **Otherwise self-service**, through `campaign_access.self_service_standing`: the owner must be a character the caller plays through one of their own seats, and at least one of those seats must be enabled (its `Player.self_service`, else its campaign's `player_self_service`). It answers `None` (no seat of the caller's plays the character: the same `403` as ever), `True`, or `False`. Another player's seat on the same character grants nothing, and a seat that says no does not veto one that says yes.
3. **`False` is `403 self-service-disabled`**, a problem type of its own, so a client can say "your GM has switched this off".

**A group is no longer an owner a player can create for.** Members could, since [ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md); only a manager can now. A party's loot comes from its GM, and the RFC says so.

### What self-service may make

When the caller has standing only through self-service, `create_item_instance` also requires:

- **A public prototype** (`item.in_public_catalog`, [ADR 0116](0116-players-read-catalog-items-and-a-public-catalog.md)). Any other is answered `422 invalid-item-prototype` with the words for an unknown id, so the call doesn't say which items exist.
- **No `slug`** (`403`): a slug is a tenant-wide name `[[links]]` resolve through, so a player doesn't claim one. A `name` stays allowed.
- **No container, or one the character holds**: `container_entity_id` must be something reachable from the owner by ownership and containment (`reachable_entity_ids`), and not the owner itself, which is its hands. So the default is owned and not carried, and `quantity` is 1, which has always needed a container ([ADR 0140](0140-a-stack-when-an-item-instance-is-created.md)). Capacity applies as ever.
- `override` is a GM's, as ever.

### Packs

`from-pack` runs the same gate. Under self-service (owner a character the caller plays, switch on) `hand_out` takes `public_only`: the pack and **every item its list names** must be public, and one that isn't is answered as an item of no such kind (`422`), whole call refused. What a pack makes is unchanged, so a being's top-level things are **Equipped**, in its hands: the one place self-service makes something carried, accepted by the maintainer, under capacity as ever.

### `GET /me`

`players[]` gains `self_service_effective`, for each of the caller's own seats: the seat's own override if set, else its campaign's. It is a new `MePlayerOut`, **not** on `PlayerContextOut`, which a character's roster shares and which lists other players' seats. A client asking "may I make my own items for this character" checks whether *any* of its seats is on, as the API does.

### loot-bot's Sack

`/container-new` makes a sack for a player's character from a catalog item called "Sack" that it creates itself, which was not public, so it would be refused. The bot, not the API, learns the rule (no name is hard-coded into the API):

- `createItem` creates the Sack in the public catalog.
- `resolveSackPrototype`, finding a "Sack" that isn't public, puts it there with the same catalog access the lookup already needs.
- When a *stored* prototype is answered `422` (deleted, or not public), `/container-new` forgets it and looks again once: whoever has catalog access finds the Sack, repairs it and sets it up for everybody; anyone else is told whom to ask, as for a new tenant.

### Deploying it

Order matters, and the first step is a manual one for a tenant that already has a Sack:

1. Deploy loot-bot first. 2. Deploy the API. 3. Until a Sack is public, a player's `/container-new` says it needs setting up and a GM or admin with library access runs `/container-new` once, which repairs it; or marks the item "Sack" `in_public_catalog` by hand. Nothing else in loot-bot makes an instance as a player (`/award` is a GM's).

## Not in scope

- Any client other than loot-bot's Sack: account-hub's toggles and a "make one from the public catalog" action in inventory-web.
- A limit on how many a player may make, and a way to exempt the Sack from the switch.

## Consequences

- **A contract tightening**, for callers who were players: no non-public prototype, no group owner, no slug, no container the character doesn't hold, and nothing at all where every seat is off. No OpenAPI schema field is removed; the change is in behaviour, and the API changelog says so.
- A GM can now say "loot comes from me", per campaign or per player, and a player who is also a GM is unaffected by it.
- A GM switching a campaign off also stops its players' sacks: the Sack is ordinary self-service.
- loot-bot's code changes after all, by a few lines in two places, to keep its one self-service path working without anyone setting it up by hand.
