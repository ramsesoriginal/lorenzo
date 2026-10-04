# 0151 - A being in no campaign: the tenant's GMs stand in for its GM

Status: accepted; amended by [ADR 0152](0152-a-gm-sees-every-being-in-no-campaign.md) (the standing described here follows a per-tenant setting)

Amends [ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md)'s standing over what an owner holds, found building [RFC 0032](../rfcs/0032-giving-a-pack-from-the-api.md) ([ADR 0149](0149-giving-a-pack-from-the-api.md)).

## Context

Who may act for an owner is worked out from the owner's campaigns: the caller plays the character (or is in the group), or is a GM of a campaign it plays in, a group's being its members' ([ADR 0032](0032-item-and-item-instance-crud-api.md), [0124](0124-groups-own-things-and-moving-is-not-giving.md); `campaign_access.campaign_ids_for_owner`). A bare being, an NPC or a monster, plays in no campaign, so for it that set is empty and nobody qualifies. In practice:

- no one could create an instance owned by an NPC, with `POST /item-instances` or `from-pack`;
- `override` and `lift_binding` ([ADR 0128](0128-capacity-and-moving-anyway.md), [0129](0129-binding-and-lifting-it.md)) were no one's for what an NPC holds;
- an existing item *could* be given to an NPC, since giving checks standing over the item and never over the recipient, but nobody who wasn't carrying it could then give it away, take it back or delete it.

An ownerless instance has the opposite rule: any GM of the tenant, or its administrators, may manage it ([RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md), `can_manage_any_campaign_in_tenant`). The maintainer asked that items and packs be givable to any being, not only characters and groups.

## Decision

An owner that is a **being or a group in no campaign** is managed by whoever may manage any campaign of the tenant: its administrators and any GM, as for an ownerless instance.

"In no campaign" is `campaign_ids_for_owner` coming back empty: a bare being, a character with no player seat, or a group none of whose members has one. An owner with a campaign keeps the rule it had, a GM of that campaign.

It applies wherever standing over an owner is asked:

- creating an instance for it (`POST /item-instances`, `from-pack`);
- `override` and `lift_binding`;
- giving away, taking back, or deleting what it owns (`_authorize_instance_write`).

It does not change:

- who may *play* for an owner: the caller's own characters and their groups;
- an owner that is neither a being nor a group. An item, a place or a faction still has nobody with standing, and `from-pack` still refuses it;
- giving an existing item to any entity, which never needed the recipient's standing.

## Not in scope

- **Reading what an NPC holds.** Who sees an owned instance is still ADR 0040's reach, so a GM sees an NPC's things when it stands in a scene a character is in, and an administrator always does. A GM who gives a pack to an NPC elsewhere gets the answer to the call, but can't browse it afterwards. That is a separate decision.
- A GM assigned to one NPC or to a group of them.

## Consequences

- An NPC can be handed items and packs by any GM or administrator of the tenant, and its holdings managed by them.
- Any GM of the tenant can do that to any NPC of it, across campaigns, as they can already to ownerless things. A tenant with several campaigns doesn't get a per-campaign boundary for NPCs.
- `POST /item-instances` for a bare being goes from `403` to `201` for those callers: a widening of what the endpoint accepts, not of any read.

## Amendment (ADR 0152)

[ADR 0152](0152-a-gm-sees-every-being-in-no-campaign.md) makes the standing above depend on a per-tenant setting, `npcs_shared_with_gms`, on by default. With it **on**, everything in this ADR holds as written: any GM or administrator of the tenant. With it **off**, a being or group in no campaign is acted for only by an administrator, or by a GM who authored it or shares a campaign with its author. The Consequences line "any GM of the tenant can do that to any NPC of it" is true only with the setting on.
