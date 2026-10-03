# 0152 - A GM sees every being in no campaign, and what it holds

Status: proposed

Follows [ADR 0151](0151-a-being-in-no-campaign-and-who-stands-in-for-its-gm.md), which gave the tenant's GMs and administrators the standing to give to, and manage, a being in no campaign. That left reading behind, which this ADR closes. One judgment call, the cross-campaign boundary, is the thing to decide in review (see Consequences).

## Context

ADR 0151 lets any GM of the tenant create items and packs for an NPC and take them back. But what a GM may *read* is bounded by reach: [ADR 0035](0035-campaign-scoped-gm-visibility.md) roots it at the characters of the campaigns they GM, [ADR 0046](0046-gm-reachability-widens-to-surroundings.md) adds the scenes those characters stand in, and one walk of ownership and containment from those roots gives `gm_reachable_entity_ids`. An NPC that is in no campaign is only in that set while it happens to stand in a scene a player character is in. So:

- a GM can give an NPC a pack, and then can't open the NPC's board (`controlled-by`, `held-by`) or list what it owns, unless it is in the scene ([ADR 0040](0040-item-instance-read-visibility.md), [0123](0123-held-by-listing-and-the-equipped-column.md), [0130](0130-the-controlled-by-listing.md) all gate on this reach);
- GM-only information about the NPC and its things stays hidden from them the same way ([ADR 0028](0028-knowledge-and-group-membership.md), [0035](0035-campaign-scoped-gm-visibility.md));
- only an `ORGA` sees it all, since `is_orga` is a blanket bypass ([ADR 0040](0040-item-instance-read-visibility.md)).

The maintainer wants a GM to see every NPC's holdings. [ADR 0046](0046-gm-reachability-widens-to-surroundings.md) recorded that doing this for a being no scene reaches "would require a real campaign-to-entity link the domain doesn't have", and the maintainer declined that heavier option then. ADR 0151 now gives a definition of "in no campaign" that doesn't need one.

## Decision

A caller who holds a `CampaignGm` row in the tenant has every **being or group in no campaign** added to the roots of their GM reach, so `gm_reachable_entity_ids` also contains each of them and, by the walk that already exists, whatever they own or contain at any depth.

"In no campaign" is exactly ADR 0151's definition: `campaign_ids_for_owner` is empty, so a bare being, a character with no player seat, or a group none of whose members has one. One function, `campaign_access.campaignless_holder_ids(session, tenant_id)`, returns them as a set, and ADR 0151's per-owner check and this one are tested to agree on every owner.

What that opens, with no new route and no schema change:

- **GM-only information** about those beings and what they hold, through `InformationVisibility.can_see` and `visible_information_clause`.
- **Item instances they own** in the item-instance reads, `owned-by`, and the `held-by` and `controlled-by` boards for them (`_caller_reach` unions this set in).

It does not change:

- **Writes.** ADR 0151 already decided who may act for these owners; this is reading only.
- **Roots for the scene.** The upward walk of ADR 0046 is still only from characters in the GM's campaigns. An NPC's own containers aren't added.
- **A being or group with a campaign**, which stays bounded by that campaign's GMs (ADR 0035). Linking an NPC to a campaign later takes it out of this set and into that campaign's.
- **Players.** What a player reaches is still their own characters and groups.
- **`OWNER`s who are not `ORGA`.** ADR 0040's inventory tier stays `ORGA`-only (ADR 0096 widened the information bypass, not that one). An `OWNER` may, since ADR 0151, give an NPC a pack without being able to browse what it holds, until they are a GM or `ORGA`.

## Alternatives considered

- **Link an NPC to a campaign** (a table or a column naming the campaign it belongs to). The clean model: it keeps ADR 0035's per-campaign boundary for NPCs too. It was declined in ADR 0046, needs a place to set the link and a screen to do it, and nothing here prevents it later: ADR 0151 and this ADR both key on "in no campaign", so a linked NPC moves to its campaign's GMs on its own.
- **Leave it as it is.** A GM can give to an NPC they then can't see. Rejected: the maintainer asked for the opposite.
- **Every participant sees them.** Rejected: GM-only information is GM-only.

## Not in scope

- **Which campaign an NPC belongs to**, as above.
- **What a player's character knows** about an NPC ([ADR 0028](0028-knowledge-and-group-membership.md)); `visible_to_characters` stays as it is.
- **An `OWNER`'s inventory reads**, as above.
- **A faster walk.** See Consequences.

## Consequences

- **The cross-campaign boundary doesn't hold for these beings.** ADR 0035's rule that GMing campaign A never leaks into campaign C stops at an NPC that is in no campaign: a GM of A sees its GM-only information and its belongings, though the story it belongs to may be C's. This is the cost of not linking NPCs to campaigns, and it is what ADR 0151 already accepted for acting on them. A tenant that runs several campaigns with secrets about shared NPCs gets no separation until those NPCs are linked.
- A GM who gives a pack to an NPC can now open it and see it, which closes the gap ADR 0151 left.
- The set is rebuilt on each request by a caller who is a GM, with every campaign-less being and group of the tenant as roots to one walk. That is fine at a campaign's expected size, and `visible_information_clause` puts the set in a SQL `IN`, which will not stay fine for a tenant with thousands of NPCs. A cheaper predicate, or caching, is the follow-up if that day comes; ADR 0035 flagged the same.
- A caller with no `CampaignGm` row sees nothing more than before, whether or not they are an administrator.
