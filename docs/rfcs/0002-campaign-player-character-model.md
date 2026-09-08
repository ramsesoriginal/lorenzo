# RFC: Campaign, player, and character model

Status: proposed — revises [ADR 0010](../adr/0010-user-tenant-membership-model.md)'s tenant definition (patched alongside this RFC); builds on [RFC 0001](0001-core-domain-data-model.md) for the entity/being mechanics

## Context

An inventory vertical slice needs a real user/campaign/character model, not just the User/Tenant/Membership from [ADR 0010](../adr/0010-user-tenant-membership-model.md). Working through concrete scenarios exposed that ADR as conflating two different things under "tenant": a persistent shared world (multiple campaigns, possibly run by different GMs, sharing the same NPCs and lore) and a specific play-through of it. They need to be separate layers. Two other needs came out of the same discussion: item ownership has to be decoupled from physical location (a character can own something they aren't carrying), and a character reused across several campaigns in the same world needs its inventory to follow it by default, not fork per campaign.

## Decision

### Tenant is a world, not a campaign

ADR 0010 defined Tenant as "a GM's world/campaign." Splitting that: **Tenant is the world** — the persistent RLS boundary, shared NPCs/places/lore, the thing a GM or a team runs. **Campaign is new**, nested inside a tenant, and a tenant can hold more than one — a team running several LARPs in the same setting, or a homebrew world hosting both a long D&D campaign and an unrelated one-shot, are the same tenant with multiple campaigns. ADR 0010 is patched alongside this RFC to reflect the split; see that ADR for the parts unaffected by it (User staying global, Membership's ownership-as-a-role-value reasoning).

### Campaign

`campaign(id, tenant_id, name, game_system, ...)`. `game_system` is the natural home for [RFC 0001](0001-core-domain-data-model.md)'s open question about multi-game-system stats — which prototype variant (e.g. "Sword (D&D 5e)" vs. "Sword (Blades in the Dark)") a campaign's entities resolve through is a property of the campaign, not of the entity itself.

### Player

`player(id, user_id, campaign_id)` — the per-user, per-campaign instance, sitting between User and Character. Player-level game-mechanical resources (D&D inspiration, a Vampire player's out-of-character options) live here, not on any one character, since a single player can control more than one character at once (Vampire) and the resource is tracked once per player, not once per character.

### Character ownership and roster reuse

A character is a `being` (see [RFC 0001](0001-core-domain-data-model.md)) owned by a **player**, not directly by a user: `character.owner_player_id`. A character can be linked to several `player` rows via `character_player(character_id, player_id)` — this is the roster-reuse mechanism, letting a user's character appear across multiple campaigns in the same tenant. Because `ownership` and `containment` (below) reference the character directly rather than the campaign-link, a character's inventory is shared across every campaign it's linked to by default — a heist one-off, a Kill Team side-game with summoned minions, or an NPC who's secretly a PC in a later game, all keep the same inventory automatically. Where a genuinely independent, forked copy is wanted instead (different continuity, not just a different session), the answer is cloning a new character that inherits from the original as a prototype, not a flag on `character_player` — the same mechanism RFC 0001 already provides for reusable-with-overrides, applied here.

### Ownership vs. containment

`ownership(item_entity_id, owner_character_id)` — a new relation, orthogonal to `containment`, exactly the kind RFC 0001 anticipated adding later without touching the core. It decouples *whose* something is from *where it physically is*: a shovel owned by character X can sit in a bag of holding carried by character Y; a carriage owned by character Y can contain Y itself while having no container of its own. Ownership isn't restricted to characters at the schema level (a faction or place could plausibly own something later), but `owner_character_id` is all that's needed for the first slice.

### GM

`campaign_gm(user_id, campaign_id)` — fully separate from `player`, not a role value on the same table, since GMing and playing track different resources and needs. Not mutually exclusive with being a player in the same campaign: a user can hold both a `player` row and a `campaign_gm` row for the same campaign (rotating-GM formats, or a GM who also runs a PC).

### Orga and tenant-level access

Tenant-level `Membership.role` (from ADR 0010) now specifically means tenant-wide administrative access — "orga" — full visibility across every campaign in that tenant, independent of holding a `player` or `campaign_gm` row in any specific one. `orga_campaign_opt_out(user_id, campaign_id)` lets an orga suppress their own blanket visibility for one campaign, so they can participate as an ordinary character in it without their tenant-wide access bleeding in.

**Access rule**: a user can access a campaign if they hold a `player` row in it, a `campaign_gm` row in it, or are tenant-orga without an opt-out for it.

### Repositories are unaffected, and probably answer RFC 0001's open tenancy question

Repositories (ADR 0002, [docs/domain/repositories.md](../domain/repositories.md)) are cross-*tenant* shared content — an official setting, a homebrew world, a universal item list — usable by many campaigns across many unrelated tenants. This is a different axis from tenant/campaign nesting, not replaced by it. Worth naming here: repository content is almost certainly the mechanism that resolves RFC 0001's still-open question about prototypes wanting to live outside a single tenant — a prototype defined in a repository, referenced by whichever campaigns draw on it, rather than owned by one tenant. Not designed further in this RFC.

### Being, PC, and NPC — deferred, not decided here

Discussed alongside this but belongs to RFC 0001's territory: `being` stays the single concrete table for now (RFC 0001's example wording is patched from `npc` to `being` accordingly). Whether a being is a PC is a derived fact — does it have an owning `player` — not a stored type; splitting `pc`/`npc` into their own concrete tables is deferred until something needs a column neither can share.

## Scope for the first slice: items

Adds to RFC 0001's item slice: `campaign`, `player`, `character` (as a `being`), `character_player`, `ownership`. Deferred for now: `campaign_gm`, tenant-level orga/opt-out, and the repository link — a first slice can assume a single implicit GM and no cross-tenant content, without redesigning anything above to add them.

## Consequences

- Every ownership/containment query for "what does this character have" now also needs to resolve through `player`/`character_player` if a UI wants to show "which of my characters, in which campaign" — an extra join, not a redesign.
- Membership's role vocabulary shrinks in scope (tenant-wide administrative access only) now that GM/player moved to campaign-scoped relations — existing reasoning about ownership-as-a-role-value still holds, just for a narrower set of roles.
- No open questions block the first slice here; RFC 0001's knowledge/redaction and multi-game-system questions remain open but aren't this RFC's to resolve.
