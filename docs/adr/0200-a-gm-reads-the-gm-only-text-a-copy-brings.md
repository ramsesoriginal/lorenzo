# 0200 - A GM reads the GM-only text a copy brings

Status: accepted, decided with the maintainer on 2026-10-07. Slice A4 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #510. Extends [ADR 0152](0152-a-gm-sees-every-being-in-no-campaign.md) from the beings and groups in no campaign to every entry no campaign owns, and closes assumption A9 of [RFC 0024](../rfcs/0024-repositories.md).

## Context

A copy brings a repository's GM-only text into the library ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)): the notes on a catalog item, on a place, on a being. Who reads GM-only text is set by reach ([ADR 0035](0035-campaign-scoped-gm-visibility.md), [0046](0046-gm-reachability-widens-to-surroundings.md), [0124](0124-groups-own-things-and-moving-is-not-giving.md), [0152](0152-a-gm-sees-every-being-in-no-campaign.md)): a GM's reach starts at the characters of the campaigns they GM, the entries that contain those characters, the groups the characters belong to, and (ADR 0152) the beings and groups in no campaign; one walk of ownership and containment from those roots gives `gm_reachable_entity_ids`. A tenant Owner or Organizer reads everything ([ADR 0096](0096-owner-joins-orga-in-the-information-visibility-bypass.md)).

A copied catalog item is an entity that is neither a being nor a group, and nobody's character reaches it. So its GM-only text is read by the library's Owners and Organizers and by no GM. [RFC 0024](../rfcs/0024-repositories.md) A9 accepted that as a known gap, and the maintainer has now decided that the text a copy brings is readable by the library's GMs. A GM who builds a campaign out of a copied repository would otherwise read its descriptions but never the notes meant for them.

The decision about who may read is easy; where to stop is not. Widening the reach to "everything in the library" would hand a GM of one campaign the GM-only text of what another campaign's characters own and carry, which is the leak [ADR 0152](0152-a-gm-sees-every-being-in-no-campaign.md) exists to avoid, and which a plain `entity` table cannot tell apart without a definition of ownership.

## Decision

### An entry no campaign owns

A **seat** is a `character_player` row: a character played by a player in a campaign. Over the whole library, whatever the caller GMs:

- the **campaign roots** are every seated character, every entry that transitively contains one (the room a player character stands in, the building around it: ADR 0046), and every group one of them belongs to (ADR 0124);
- the **campaign reach** is those roots, everything they own, and everything contained in any of those, at any depth: the same walk of ownership and containment as everywhere else (`entity_access.reachable_entity_ids`), started from every seat in the library at once instead of from one campaign's;
- an entry is **owned by a campaign** when it is in the campaign reach, and **owned by no campaign** otherwise.

Nothing about a campaign is stored or added: the definition is the one reach the module already walks, taken over all campaigns together. Anything a player character owns, carries, or stands in is therefore a campaign's, whichever campaign the character is in.

### What a GM reads

For a caller who holds a `CampaignGm` row in the library, and only for such a caller, the roots of their GM reach gain every entry of the library that is owned by no campaign, of any kind (catalog item, inventory item, place, being, group, anything else) and the walk of ownership and containment from them, **minus the campaign reach**:

- **the setting on** (`tenant.npcs_shared_with_gms`, the default): every such entry;
- **the setting off:** only the entries authored (`entity.created_by`) by the caller or by a co-GM, as ADR 0152 defines both; what they own and what is contained in them comes along, as it does for a being. A copy credits whoever ran it (ADR 0152), so a copy an Owner ran stays unread by GMs while the setting is off, and the Owner may switch it on or author the entries they want shared.

What this reads is what ADR 0152 already reads for beings: GM-only information on those entries (`InformationVisibility.can_see`, `visible_information_clause`), and, because `gm_reachable_entity_ids` is the one set every reader of a GM's reach shares, the owned inventory items and the beings listing ([ADR 0173](0173-a-gm-lists-the-beings-they-can-see.md)) with the same reach. What a seated character, a campaign's scene, and ADR 0152's beings and groups reach is unchanged: the new roots are added to the old ones, and nothing is taken from them.

The subtraction is what keeps a campaign's holdings its own. An inventory item owned by a character seated in a campaign the caller does not GM, an item carried in that character's backpack, a pack in a chest it owns, a room it stands in with everything in the room, and anything reachable only through such a character, is in the campaign reach, so it is outside the caller's gain however the walk from the new roots arrives at it. The roots are checked against the campaign reach too, so an entry is never a root and a campaign's at once. What a GM of campaign X gains is only entries no campaign's characters hold; nothing about what campaign Y's characters own.

### Acting, players and administrators

- **Acting is unchanged.** `campaignless_holders_for` and `can_manage_owner` (ADR 0151, 0152) keep their definition: standing to give to, take from and delete for an owner stays with beings and groups in no campaign. This ADR is about reading.
- **Players never gain it.** The new roots are added only for a caller with a `CampaignGm` row; a player, a plain member, and an account with no role in the library reach nothing more.
- **Owners and Organizers are unchanged.** They bypass reach (ADR 0096), and their opt-out suppression is the same.
- **A repository has no GMs**, so a repository reads exactly as before.

### The setting keeps its name

`tenant.npcs_shared_with_gms` is not renamed and gets no sibling. A second switch would need a migration and give a library two questions with one answer (is this entry read by every GM or only by its author's table?), and a rename is a breaking change to the API and every client for a name nobody reads in a screen. What changes is the meaning, and so the words around it: the setting decides whether **every GM of the library reads the GM-only text of the entries no campaign owns** (the beings that are not in a campaign, and what a copy brought), or only the GMs who authored them or share a campaign with their author. The descriptions of `npcs_shared_with_gms` in `TenantOut` and `TenantUpdate` say so in the product's words (library, GM, entry), and the API reference regenerated from them follows. There is no migration.

### Nothing more than the reach changes

- **One definition, two forms.** `visible_information_clause` (SQL) and `can_see` (Python) stay one definition over the same resolved set ([ADR 0109](0109-player-knowers-knower-listing-and-information-list.md)). The parity test covers a caller whose reach comes from the new roots, next to the rows of a seated character's campaign and of another campaign.
- **A reach of a whole library is a long list.** A copy puts thousands of entries in the set, and a query that binds each id as its own parameter fails past the driver's limit. The shared reads that take the set (the information clause, the walk of ownership and containment, the item-instance and beings listings) pass it as one array instead; the result is the same.

## Alternatives considered

- **Everything in the library, minus nothing.** Simplest, and what "the GMs read what a copy brings" says on the surface. A GM of one campaign would then read the notes on another campaign's characters' items and the room those characters stand in, so a library running several tables could not keep them apart; rejected.
- **Only entries that came from a copy.** The copy records say where an entry came from ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)), and it would be the narrowest reading. But it leaves the library's own catalog and world, authored by its own people, in the old gap: a GM would read what was copied and not what an Owner wrote the same afternoon, and the rule would depend on how the entry got there instead of who holds it.
- **Link an entry to a campaign.** The model ADR 0152 declined: fail-closed and complete, but a table and a screen, and nothing here prevents it later; a linked entry is held by its campaign and leaves this set for that campaign's GMs.
- **A second setting.** One for beings and one for the rest; see above.
- **Leave the gap.** The maintainer decided otherwise.

## Not in scope

- **Which campaign an entry belongs to**, as in ADR 0152.
- **A GM writing to those entries.** Reading only; ADR 0151's standing for acting is unchanged, and authoring catalog entries stays with the library's administrators and the people the routes already name.
- **A screen for the setting.** The API carries it, and account-hub shows it later; the description is what such a screen would say.
- **Public repositories.** [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) copies GM-only text with the rest; this slice is what makes that readable by the copying library's GMs.

## Consequences

- **A copied repository's GM-only text is read by the library's GMs** with the setting on, which is the default, and by the GMs who authored the copy or share a campaign with whoever did when it is off.
- **A GM reads the GM-only text of every entry no campaign holds**, including the library's own catalog and places, not only what a copy brought. A catalog item is not held by a character that owns an inventory item made from it: what is held is the inventory item, and the catalog item's notes are the library's.
- **An unowned inventory item**, one no character owns and nothing carried by a character contains, is owned by no campaign, so a GM reads its GM-only text with the setting on.
- **A thing an NPC owns and a player character carries** stays reached through the NPC, as ADR 0152 has it, whichever campaign carries it; the subtraction applies only to what the new roots add.
- **The cost grows with the library.** The reach is rebuilt on each request by a caller who is a GM: one walk from every seat for the campaign reach, one list of the library's entries, one walk from the roots. It is one array and a handful of queries, and it stays bounded by the library; caching it is still the follow-up ADR 0035 and ADR 0152 named.
- **RFC 0024 A9 is closed by this ADR.** The note in that RFC already points here.
- **Built in one slice, no migration:** the reach of the new roots in `campaign_access` and `information_visibility`, the one-array form of the shared reads, the wording of the setting in `TenantOut`/`TenantUpdate`, tests for both directions and for the parity, regenerated API reference and clients.
