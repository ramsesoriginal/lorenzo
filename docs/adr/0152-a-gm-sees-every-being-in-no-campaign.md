# 0152 - A GM sees every being in no campaign, unless the tenant hides them

Status: accepted, decided with the maintainer on 2026-10-03. Rewrites the version first proposed in #383, which had no setting; nothing was built from that one.

Follows [ADR 0151](0151-a-being-in-no-campaign-and-who-stands-in-for-its-gm.md), which gave the tenant's GMs and administrators standing over a being in no campaign, and amends it: that standing now follows the setting below.

## Context

ADR 0151 lets any GM of the tenant create items and packs for an NPC and take them back. What a GM may *read* is bounded by reach: [ADR 0035](0035-campaign-scoped-gm-visibility.md) roots it at the characters of the campaigns they GM, [ADR 0046](0046-gm-reachability-widens-to-surroundings.md) adds the scenes those characters stand in, and one walk of ownership and containment from those roots gives `gm_reachable_entity_ids`. An NPC in no campaign is only in that set while it stands in a scene a player character is in. So:

- a GM can give an NPC a pack and then can't open its board (`controlled-by`, `held-by`) or list what it owns, unless it is in the scene ([ADR 0040](0040-item-instance-read-visibility.md), [0123](0123-held-by-listing-and-the-equipped-column.md), [0130](0130-the-controlled-by-listing.md));
- GM-only information about the NPC and its things stays hidden from them the same way ([ADR 0028](0028-knowledge-and-group-membership.md), [0035](0035-campaign-scoped-gm-visibility.md)), including the notes on an NPC they have prepared but not yet met;
- only an `ORGA` sees it all, since `is_orga` is a blanket bypass.

Letting every GM see every such being fixes that, but it has costs, found in review of the first version of this ADR:

- **The default is fail-open.** A new NPC is "in no campaign", so it would be exposed to every GM the moment it exists.
- **A GM who plays elsewhere sees that table's secrets.** Someone who GMs A and plays in B, in one tenant, would read B's GM-only notes. The repo already treats this as a real problem: admins get a per-campaign opt-out so they can play without metagaming (`TenantAdminCampaignOptOut`).
- **It cuts across `secret` campaigns**, which exist so a table can be private within a tenant.

[ADR 0046](0046-gm-reachability-widens-to-surroundings.md) recorded that giving an NPC a real campaign would need a link the domain doesn't have, and the maintainer declined it then. This ADR keeps declining it and lets each tenant choose how open its NPCs are.

## Decision

### A tenant setting

`tenant.npcs_shared_with_gms`, a boolean, **on by default**. It is in `TenantOut` and `TenantUpdate`, so it is changed with `PATCH /tenants/{id}` by whoever may update the tenant today (a tenant administrator), and that is logged as `tenant.updated` with the field's name, as any tenant change is ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)). A new column with a server default of on needs no data change. A repository tenant has the column and no use for it: it holds no campaigns, so it has no GMs.

### Which beings

Those in no campaign, ADR 0151's definition: `campaign_ids_for_owner` is empty, so a bare being, a character with no player seat, or a group none of whose members has one. Anything with a campaign keeps its own GMs (ADR 0035, 0124).

### Who has standing, and sees them

Only a caller who holds a `CampaignGm` row in the tenant is a GM here. For such a caller, a being in no campaign is theirs to see and act for when:

- **the setting is on:** always;
- **the setting is off:** it was authored by them, or by a **co-GM**: someone who GMs at least one campaign they also GM. Authorship is `entity.created_by`, and the co-GM relation is worked out when asked, not stored.

Tenant administrators are as before: ADR 0151's standing for acting, `ORGA`'s blanket reading, and an `OWNER`'s information bypass ([ADR 0096](0096-owner-joins-orga-in-the-information-visibility-bypass.md)).

### Reading

The beings above are added to the roots of the caller's GM reach, so `gm_reachable_entity_ids` contains each of them and, by the walk that exists, whatever they own or contain at any depth. That opens:

- GM-only information about them and what they hold (`InformationVisibility.can_see`, `visible_information_clause`);
- the item instances they own, in the item-instance reads, `owned-by`, and the `held-by` and `controlled-by` boards for them (`_caller_reach` unions this set in).

With the setting off, reading is **also** what it was before (a scene a player character stands in, [ADR 0046](0046-gm-reachability-widens-to-surroundings.md)), so turning the setting off removes only what the setting added.

### Acting

ADR 0151's standing for acting on such an owner (creating for it, `override`, `lift_binding`, giving away, taking back, deleting) is the same rule: any GM or administrator with the setting on; with it off, an administrator, or a GM who authored it or is a co-GM of its author. A scene alone does not give a GM standing to act, only to read.

One function, `campaign_access.campaignless_holders_for(session, user_id, tenant_id)`, returns the set for a caller, and both reading and acting use it, with a test that they agree for every being.

### What authorship means

- **An account that is deleted** leaves `created_by` null, so the being is unauthored: with the setting off it is visible to administrators and by scene only.
- **A repository copy** credits whoever ran the copy, and **an import or the API** credits whoever's token made the call. An NPC an administrator imported is therefore hidden from GMs when the setting is off, which is the safe direction.
- **A co-GM relation lasts as long as the campaigns do:** a GM removed from a campaign stops being a co-GM of its other GMs' NPCs.
- **Authorship alone is not standing.** A caller who authored a being but holds no GM role in the tenant sees nothing more.

## What it does not change

- **Players.** What a player reaches is their own characters and groups.
- **The upward scene walk** and a being or group with a campaign.
- **`OWNER`s who are not `ORGA`**: ADR 0040's inventory tier stays `ORGA`-only, so they can give an NPC a pack without browsing what it holds.
- **What a character knows** about an NPC (ADR 0028); `visible_to_characters` stays as it is.

## Alternatives considered

- **No setting; every GM sees all** (the first version of this ADR). Smaller, but fail-open with no remedy for a tenant that runs several tables.
- **Link an NPC to a campaign.** The clean model: fail-closed, and it would cover places and factions too. Declined in ADR 0046, it needs a table and a screen, and nothing here prevents it later: a linked being is no longer "in no campaign", so it leaves this set for its campaign's GMs.
- **Authors and co-GMs only, no setting.** Safe, but a tenant that shares its NPCs freely has to author them all, and an imported NPC is nobody's.
- **Leave it.** A GM can give to an NPC they then can't see.

## Not in scope

- **Which campaign an NPC belongs to.**
- **Places, factions and other entities** with no campaign link: their GM-only information is still reached only by scene.
- **A screen for the setting.** The API carries it; account-hub shows it later, and should surface it when a tenant's second campaign is created.
- **A cheaper walk.** See Consequences.

## Consequences

- **A tenant that never finds the setting stays shared**, so a multi-campaign tenant is exposed until an administrator turns it off. That is the price of the default; the screen should make the choice visible.
- **An author who GMs two campaigns joins them:** everyone in either sees that author's NPCs with the setting off, since a being can't be told apart by campaign.
- **A world NPC two unrelated GMs share** is visible, with the setting off, only to its author's co-GMs. Only a campaign link fixes that.
- **The setting is per tenant**, so one shared table and one private one in a tenant are served only by authorship.
- **An `OWNER` who is not `ORGA`** still can't read what an NPC they may give to holds.
- The set is rebuilt on each request by a caller who is a GM, with every being in no campaign (or each one authored by a co-GM) as roots to one walk. That is fine at a campaign's expected size, and `visible_information_clause` puts the set in a SQL `IN`, which will not stay fine for thousands of NPCs. A cheaper predicate or caching is the follow-up; ADR 0035 flagged the same.
- **Built in one slice:** the migration and column, `TenantOut`/`TenantUpdate`, `campaignless_holders_for`, the visibility and standing changes, tests for both modes and the agreement between reading and acting, regenerated clients.
