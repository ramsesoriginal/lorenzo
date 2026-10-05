# RFC: Player self-service — a player making their own gear from the public catalog, switchable per campaign and per player

Status: proposed, Decision open. Given by the maintainer on 2026-10-05: the two switches (campaign default on, per-player override), a character in several campaigns resolving through any of the caller's own seats, public items only, owned and not carried, and the container exception. The rest of [Decision](#decision) is my proposal for review. What is still open is listed in [Open questions](#open-questions). Nothing is built; the first step is `apps/api` alone ([Slices](#slices)). Row "Player self-service (switchable per campaign or player)" of [v1.0](../../v1.0.md).

## Context

A player can already make an item instance for their own character: `POST .../item-instances` with `owner_character_id` set to one of the caller's characters needs no other standing ([RFC 0005](0005-item-and-item-instance-crud-api.md), [ADR 0032](../adr/0032-item-and-item-instance-crud-api.md), `_authorize_create_instance`). It was meant as "a player rolling their own gear is as ordinary as rolling their own PC", and [ADR 0094](../adr/0094-loot-bot-container-new.md) leans on it for a sack. But as built, it is not a feature anyone can switch, and it is wider than the sentence that justified it:

- **No switch.** A GM who wants players to receive loot only from them has no way to say so. The permission is on for every player of every campaign, always.
- **Any item.** The prototype is checked only to be a base item of the tenant. A player can make an instance of an item they cannot even see: the catalog is GM-curated and `item.in_public_catalog` ([ADR 0116](../adr/0116-players-read-catalog-items-and-a-public-catalog.md)) is what says a player may list it.
- **Anywhere.** `container_entity_id` and `quantity` are free, so a player can make a stack of a hundred inside any container the capacity check ([ADR 0128](../adr/0128-capacity-and-moving-anyway.md)) lets them.

So this RFC is as much a restriction as a feature: it gives self-service the three conditions it should always have had, and the switch a table needs.

Facts it builds on:

- **A player's seat is a `Player` row**, one per campaign and user, and a character is rostered to seats through `character_player` ([ADR 0025](../adr/0025-character-being-and-ownership.md)). The same character can sit in several campaigns, and its inventory is shared across them.
- **What a caller controls** is their own seats' characters, plus the groups those are in ([ADR 0124](../adr/0124-groups-own-things-and-moving-is-not-giving.md); `entity_access.controlled_holder_entity_ids`).
- **Managing is separate and stays as it is.** A GM, or a tenant `OWNER`/`ORGA`, makes instances for anyone in their campaigns through `can_manage_campaign` and `override` is theirs alone ([ADR 0128](../adr/0128-capacity-and-moving-anyway.md), [0129](../adr/0129-binding-and-lifting-it.md)).
- **Instances only carry a count in a container** ([ADR 0041](../adr/0041-containment-quantity-and-stacking.md), [0140](../adr/0140-a-stack-when-an-item-instance-is-created.md)), so something owned and in no container is a single, not carried ([RFC 0031](0031-equipped-carried-controlled-and-setting-things-down.md)).

## Decision

### 1. Two switches

- **`campaign.player_self_service`**, a boolean, not null, **default `true`**. The campaign's general setting.
- **`player.self_service`**, a nullable boolean, **default `null`**: no override, follow the campaign. `true` allows and `false` forbids that one player whatever the campaign says.

A seat is **enabled** when its own `self_service` is set and true, or when it is `null` and its campaign's setting is true. Existing campaigns and players get `true`/`null`, so nothing is switched off by the migration.

### 2. Who may change them

Whoever may manage the campaign (`can_manage_campaign`: a GM of it, or a tenant `OWNER`/`ORGA`), and only they. A player never sets their own.

- `PATCH /campaigns/{id}` takes `player_self_service`, with the route's existing `If-Match`.
- A new `PATCH .../campaigns/{id}/players/{player_id}` takes `self_service`, where an explicit `null` clears the override. `Player` has `updated_at`, so it takes `If-Match` the same way.
- Both are **recorded in the activity log** ([ADR 0084](../adr/0084-activity-log-coverage-and-member-removal-notice.md): it changes who can do what), with the ids and the field's name, never more.
- `CampaignOut` gains `player_self_service`. A roster row (`PlayerSummaryOut`) gains `self_service` (the override) and `self_service_effective` (what applies, so a client needn't repeat the rule), behind the gate that already admits that read.

### 3. A character in several campaigns

The right belongs to the character in the tenant, because that is where its inventory lives, so one campaign saying yes is enough:

> A caller may self-serve for a character they control when **any of the caller's own seats that rosters that character is enabled**.

- Only the **caller's** seats count. Another player's enabled seat on the same character does not grant a co-pilot anything, and a seat's `false` does not veto another seat of the same caller's `true`.
- A character a caller controls through no seat does not exist (control *is* a seat), so there is no "no campaign" case for a player. NPCs and groups are a GM's to equip.

### 4. What self-service may create

When the caller has standing **only** through self-service (they don't also manage the owner), a create is accepted only if all of:

1. **The owner is a character they control**, not a group, not an NPC.
2. **The switch is on** for them under §3.
3. **The prototype is public**: `item.in_public_catalog` is true. Anything else is answered exactly as an unknown prototype (`422`), so the call doesn't tell a player which items exist.
4. **It is owned and not carried**: no `container_entity_id`, so `quantity` is 1 (more than one has always needed a container, ADR 0140). The exception, decided with the maintainer, is a container the character already controls: an item in the character's own inventory (the sack of [ADR 0094](../adr/0094-loot-bot-container-new.md)), under the capacity check as ever.
5. **`override` is refused** as ever, and `slug` is refused (see Open questions).

A refusal for 2 is its own problem type (`403`, `self-service-disabled`) so a client can say "your GM has switched this off" rather than "not authorized".

A caller who manages the owner is judged by the manager rules and none of the above, as today. A GM who also plays is a manager first.

### 5. Nothing else moves

An instance made this way is an ordinary instance: the same activity entry and change-feed row ([ADR 0099](../adr/0099-player-facing-change-feed.md)), the same ownership, and the player can give it away or set it down by the rules that already apply. Switching self-service off later removes nothing a player already made.

## Slices

1. **The switches** (`apps/api`): the migration (two columns, no new table, so no new RLS and nothing for `repository_access`), the model, `PATCH /campaigns/{id}`, `PATCH .../players/{id}`, the output fields, the activity log. Nothing is enforced yet, so it changes no behaviour. An ADR when it lands.
2. **The enforcement** (`apps/api`): the §3 resolution as one function in `campaign_access`, `_authorize_create_instance` using it, the §4 conditions, the problem type. A **contract tightening** for existing callers, recorded as such in its ADR and the API's changelog.
3. **Clients** (later, not scoped): account-hub's two toggles, a "make one from the public catalog" action in inventory-web and loot-bot, and loot-bot's sack prototype made public. Out of scope until asked for.

## Open questions

- **`POST .../item-instances/from-pack`** ([ADR 0149](../adr/0149-giving-a-pack-from-the-api.md)) uses the same gate today, so a player can give themselves a pack. A pack puts things in the being's hands (Equipped, which *is* carried) and names many items. Recommended: self-service does **not** cover it; packs stay with GMs until a later slice says what a player's pack may be. This is a second tightening.
- **`slug` for a player.** A slug is a tenant-wide name that `[[links]]` resolve through ([ADR 0107](../adr/0107-entity-slugs-and-batch-resolve.md)), so a player could claim `[[Excalibur]]`. Recommended: a self-service create takes none. A `name` stays allowed, as for any create.
- **Volume.** Nothing limits how many a player may make. The activity log records each. Recommended: none now; a per-player limit is a later, separate switch if a table needs one.
- **Telling a client it may.** A client needs to know whether to show the action. Recommended: `GET /me`'s `players[]` entries carry `self_service_effective` (additive), rather than a tenant-wide flag, since §3 depends on the character.
- **The container exception** goes beyond "owned and not carried". It keeps `/container-new` working, but its sack prototype is not public today, so §4.3 breaks it until that prototype is made public (slice 3). Say if the exception should be dropped, or if the sack should be exempt from public-ness instead.

## Consequences

- A table can say "loot comes from the GM" with one switch, and "except Alice" with another.
- Players who could make anything now make only what the GM published, which is the point, and a tightening existing loot-bot users will notice (`/container-new`, `/award` is a GM's and unaffected).
- No new table, so [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)'s RLS and [ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md)'s same-tenant keys are untouched.
