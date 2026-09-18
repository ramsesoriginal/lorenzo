# 0035 - Campaign-scoped GM visibility

Status: accepted

## Context

`InformationVisibility.can_see` ([information_visibility.py](../../apps/api/src/lorenzo_api/information_visibility.py)) had exactly one blanket "see everything" bypass: `is_orga`. It never consulted `CampaignGm` at all, so a campaign's own GM - who may legitimately hold zero tenant-wide `Membership` rows ([ADR 0022](0022-user-tenant-membership.md)) - saw only what their own characters/players would see, nothing more. This is a real, currently-shipping gap: GitHub milestone #1's own scenario has Zorro, GM of "The Ashen Crown" with no tenant Membership, seeing that a sword is cursed - a GM-only secret, which per [ADR 0028](0028-knowledge-and-group-membership.md) is just the default (`is_public=false`, zero `Knowledge` rows). Today's code shows him nothing beyond an ordinary participant would see. This ADR accepts [RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md), close to verbatim.

GM sight is per-campaign-grant, not tenant-wide - a GM has no view outside their own campaign(s), and a user can hold `CampaignGm` on more than one campaign at once, each independently. This is the opposite shape from character knowledge (`knower_entity_id`), which is deliberately tenant-wide (a character's knowledge follows them across every campaign they're linked to, ADR 0028) - that half is unchanged by this ADR.

## Decision

### GM-reachable entity set, reusing ADR 0032's `entity_access.reachable_entity_ids`

For every `CampaignGm` row the caller holds in this tenant: resolve that campaign's own roster of `Character`s (via `CharacterPlayer` -> `Player.campaign_id`), union the rosters across every campaign GM'd, then call `entity_access.reachable_entity_ids` **once** with that combined root set. That function - root set, plus everything `Ownership`-owned by it, plus everything reachable via `Containment` recursively - is exactly this RFC's own three-step walk, built in [ADR 0032](0032-item-and-item-instance-crud-api.md) *anticipating this exact use*; this ADR calls it, it does not reimplement it. A GM's own campaign characters are included directly (they're the walk's root set), not just their inventories - easy to miss, since it reads at first like an inventory-only walk.

Deliberately not extended through `entity_prototype`: a prototype is shared catalog content, not campaign-scoped, and `reachable_entity_ids` never walks prototypes in the first place - this falls out for free.

GMing campaign A never leaks into unrelated campaign C in the same tenant, even for a user who GMs both - each campaign's roster only reaches what's actually reachable from *that* campaign's own characters; the union is of reachable sets, not of blanket campaign access.

### `InformationVisibility` gains a second, differently-shaped bypass

`is_orga` is a single blanket bit; GM-derived visibility is a set: `gm_reachable_entity_ids: frozenset[uuid.UUID]`, computed once per request in `resolve_information_visibility` alongside the existing `player_ids`/`knower_entity_ids` queries (three more short-circuiting queries: `CampaignGm.campaign_id` for the caller, then the roster via a `CharacterPlayer` join to `Player`, then one `reachable_entity_ids` call - skipped entirely once either input set is empty, matching this function's existing short-circuiting style). `can_see` gains one more condition, between the blanket bypass and the knowledge check:

```python
def can_see(self, info: Information) -> bool:
    if self.is_orga or info.is_public:
        return True
    if info.entity_id in self.gm_reachable_entity_ids:
        return True
    return any(...)  # unchanged
```

`Information.entity_id` is already a plain, always-loaded column - no new eager-load chain needed for this check, unlike `knowledge_links`.

### No route-parameter change

`resolve_information_visibility`'s signature (`user_id`, `tenant_id`) is unchanged - no `campaign_id` query parameter added to any `GET` route. Same treatment character-knowledge resolution already gets: union across every relevant campaign, not "as GM of which campaign."

### Tenant `OWNER` visibility unchanged

Still no bypass, still ORGA-only for `is_orga`. [ADR 0028](0028-knowledge-and-group-membership.md)'s "administrative access != automatic character knowledge" principle extends here unmodified: an owner's tenant-administrative role must not imply GM omniscience either, matching how `is_orga` already excludes `OWNER`.

## Not in scope

"Facts": campaign-relevance for world content not yet attached to any character (an undiscovered NPC, an unvisited location, a circulating rumor) - reachability-from-a-character isn't a meaningful test for something no character has ever touched. Recorded as [RFC 0001](../rfcs/0001-core-domain-data-model.md)'s open question #4.

## Consequences

- No schema change - `CharacterPlayer`, `Ownership`, `Containment`, `CampaignGm` all already exist exactly as this needs them.
- `entity_access.reachable_entity_ids` ([ADR 0032](0032-item-and-item-instance-crud-api.md)) is now consumed by a second caller, exactly as that ADR's own Consequences section anticipated - one shared walk, not two independent copies.
- Fixes the milestone's own visibility gap: a campaign's own GM, holding no tenant-wide `Membership`, now sees what the milestone's scenario requires.
- `information_visibility.py`'s test suite gains its first cases proving GM-only information becomes visible to a `CampaignGm` who is not tenant-orga, including that the bypass stays bounded to the GM's own campaign(s) and that a character's own `Information` is covered directly, not just its inventory.
- Performance of the recursive reachability walk at request time is unexamined beyond this domain's expected scale (a campaign's roster and inventories are not large graphs) - revisit with caching/materialization only if that stops being true.
