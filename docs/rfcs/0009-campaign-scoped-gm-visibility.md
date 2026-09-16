# RFC: Campaign-scoped GM visibility

Status: proposed — revises `information_visibility.py`'s only current blanket-visibility bypass ([ADR 0028](../adr/0028-knowledge-and-group-membership.md)); builds on [RFC 0004](0004-user-membership-player-character-gm-read-api.md)'s GM read surface

## Context

`InformationVisibility.can_see` ([information_visibility.py](../../apps/api/src/lorenzo_api/information_visibility.py)) has exactly one blanket "see everything" bypass today: `is_orga`, computed from tenant-wide `Membership.role == ORGA` ([campaign_access.is_tenant_orga](../../apps/api/src/lorenzo_api/campaign_access.py)). It never consults `CampaignGm` at all. That means a campaign's own GM — who may legitimately hold zero tenant-wide `Membership` rows, exactly the case [ADR 0022](../adr/0022-user-tenant-membership.md) names as valid, not a gap — currently sees only what their own characters/players would see, nothing more. Checked directly against [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1)'s scenario: Zorro (a `CampaignGm`, not necessarily tenant-orga) is supposed to see "cursed" — a GM-only secret, which per [ADR 0028](../adr/0028-knowledge-and-group-membership.md) is just the default (`is_public=false`, zero `Knowledge` rows), not a separate flag — and today's code shows him nothing beyond what an ordinary participant would see.

Clarified in discussion (not what was first assumed): GM sight is **per-campaign-grant, not tenant-wide** — a GM has no view outside their own campaign(s), and a user can hold `CampaignGm` on more than one campaign at once, each independently. Contrast this with character knowledge (`knower_entity_id`), which is deliberately **tenant-wide**, not campaign-scoped — a character's knowledge follows them across every campaign they're linked to in the tenant (the "book series" framing: campaigns are volumes, a character's knowledge of the world spans the whole series, time-scoping aside — out of scope for this slice). That half already works correctly (`information_visibility.py`'s own docstring already says so) and this RFC doesn't touch it.

`Entity`/`Information` carry no campaign linkage at all — deliberate, since `Tenant` is the shared world and campaigns don't own world content ([RFC 0002](0002-campaign-player-character-model.md)). So "is this entity part of Zorro's campaign" isn't a stored fact; it has to be computed by reachability from that campaign's own characters, the same graph this vertical slice already builds for inventory (`Ownership`/`Containment`). Confirmed in scope discussion: this is sufficient *for this slice* specifically because an item's presence in a campaign is, by construction, mediated through a character who owns or is near it — a broader "is this piece of world content even relevant to campaign X yet" question (an NPC no one's met, an undiscovered location, a rumor) is a different, harder problem, out of scope here — see [RFC 0001](0001-core-domain-data-model.md)'s open question #4 ("facts").

## Decision

### GM-reachable entity set, per campaign the caller GMs

For each `CampaignGm` row the caller holds in this tenant:

1. Start from every `Character` linked (via `CharacterPlayer`) to a `Player` of that campaign — the campaign's own roster of characters. These entities are GM-visible directly, not just their belongings. (`CharacterPlayer.character_entity_id` targets `Character.entity_id`, not `Being.entity_id`, since [RFC 0004](0004-user-membership-player-character-gm-read-api.md) layered a dedicated `character` table under `being` — terminology only, the actual entity-id set this walk produces is unaffected, since a `Character`'s `entity_id` still just *is* the same `entity.id` a bare `Being` would have had.)
2. Extend through `Ownership` — anything owned by one of those characters.
3. Extend through `Containment`, recursively — anything inside/on any entity reached so far (an item in a bag on a character; a bag in a chest that character owns) — using the same bounded, cycle-safe recursive-walk shape `routers/item_instances.py`'s `_recursive_descendants_cte`/`_MAX_CONTAINMENT_DEPTH` already establishes for exactly this kind of walk, since `Containment` is deliberately cycle-*tolerant* ([ADR 0016](../adr/0016-containment.md)).

Steps 2-3 (ownership/containment reachability from a character) are the same walk [RFC 0005](0005-item-and-item-instance-crud-api.md) later reuses for its own self-or-managed item-instance authorization — meant to live in one shared `entity_access.py` both RFCs call, not two independent implementations of the identical traversal (see Consequences below for the extraction's own status).

The full GM-reachable set is the union of this walk across **every** campaign the caller GMs in the tenant — mirroring, one level up, the same "union across every campaign" shape character-knowledge resolution already uses for `CharacterPlayer`. A user GMing two campaigns sees the union of both, each still bounded to what's reachable from that specific campaign's own characters — GMing campaign A never leaks visibility into campaign C's unrelated content just because the same user holds both grants.

**Deliberately not extended through `entity_prototype`.** A prototype ("Sword," "Flaming Sword") is shared catalog content, not scoped to any one campaign — plausibly referenced by several campaigns in the tenant at once. Reachability stops at ownership/containment, the same boundary [RFC 0005](0005-item-and-item-instance-crud-api.md) already drew between "campaign-flavored instance" and "tenant-wide catalog."

### `InformationVisibility` gains a second, differently-shaped bypass

Unlike `is_orga` (a single blanket bit), GM-derived visibility is a set: `gm_reachable_entity_ids: frozenset[uuid.UUID]`, computed once per request in `resolve_information_visibility` alongside the existing `player_ids`/`knower_entity_ids` queries. `can_see` gains one more condition:

```python
def can_see(self, info: Information) -> bool:
    if self.is_orga or info.is_public:
        return True
    if info.entity_id in self.gm_reachable_entity_ids:
        return True
    return any(
        link.knower_player_id in self.player_ids
        or link.knower_entity_id in self.knower_entity_ids
        for link in info.knowledge_links
    )
```

`Information.entity_id` is already a plain, always-loaded column — this needs no new eager-load chain, unlike `knowledge_links`.

### No route-parameter change

Deliberately does not add a `campaign_id` parameter to `GET /tenants/{tenant_id}/entities/{id}` (or `items`/`item-instances`) to say "as GM of which campaign" — that would break the pattern character-knowledge already established (no campaign parameter needed, union across every relevant campaign instead). Same treatment here keeps `resolve_information_visibility`'s signature unchanged (`user_id`, `tenant_id`) and reuses [RFC 0004](0004-user-membership-player-character-gm-read-api.md)'s existing GM read surface (`User.campaign_gms`) as the source of which campaigns to walk.

## Not in scope

**"Facts": campaign-relevance for world content not yet attached to any character** (an undiscovered NPC, an unvisited location's contents, a circulating rumor) — genuinely harder, since reachability-from-a-character isn't a meaningful test for something no character has ever touched. Recorded as [RFC 0001](0001-core-domain-data-model.md)'s open question #4, not designed here.

**Tenant `OWNER` visibility** — unchanged, still no bypass. [ADR 0028](../adr/0028-knowledge-and-group-membership.md)'s existing "administrative access != automatic character knowledge" principle was confirmed still correct in discussion: an owner's tenant-administrative role must not accidentally imply either character knowledge or GM omniscience.

## Open questions

**Performance of the recursive reachability walk at request time.** Fine at this domain's scale (a campaign's character roster and their inventories are not large graphs) — revisit with caching/materialization if that stops being true, not designed preemptively.

**Should the GM-reachable set include a character's own `Information` rows (not just what they own/contain)?** Step 1 above already includes the `Character` entities themselves directly, so yes — flagging only because it's easy to misread the walk as inventory-only and forget the characters are the starting nodes, not an afterthought.

## Consequences

- No schema change — `CharacterPlayer`, `Ownership`, `Containment`, `CampaignGm` all already exist exactly as this needs them.
- Its ownership/containment reachability walk is meant to be shared with [RFC 0005](0005-item-and-item-instance-crud-api.md)'s item-instance write authorization via a common `entity_access.py`, not reimplemented — named here as this RFC's own consequence, but the actual extraction is RFC 0005's own flagged follow-up (its Consequences section), not yet done by either RFC: both are still proposals, and today this walk exists nowhere but in this document's own Decision section above.
- Fixes a real, currently-shipping gap: a campaign's own GM, holding no tenant-wide `Membership`, sees strictly less than the milestone's scenario requires today.
- `information_visibility.py`'s test suite gains its first case proving GM-only information becomes visible to a `CampaignGm` who is not tenant-orga — today only the orga path and the player/character-knowledge paths are covered.
