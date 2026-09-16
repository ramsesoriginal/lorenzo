# 0040 - Item-instance read visibility narrows to reachable owners

Status: accepted

## Context

[ADR 0032](0032-item-and-item-instance-crud-api.md) deliberately gated every item-instance read route (`GET /item-instances`, `.../owned-by/{owner_entity_id}`, `.../{id}`) on `is_tenant_participant` alone - broad on purpose, so a plain `Player`/`CampaignGm` (neither implies tenant-wide `Membership`, ADR 0022) could browse at all. Raised in conversation, not by a milestone requirement: that same coarseness means **any** participant can call `owned-by/{alice_entity_id}` and see Alice's entire inventory - every instance she owns, its resolved stats, its container - regardless of whether they control Alice, GM her campaign, or have any standing over her at all. Narrative content (descriptions/secrets) is already gated per-viewer via `information_visibility.py` ([ADR 0028](0028-knowledge-and-group-membership.md)/[0035](0035-campaign-scoped-gm-visibility.md)) - this gap is one level up: the *existence and ownership* of an instance is currently public within the tenant even when its content isn't.

A broader fix - hide an instance unless the caller can see at least one piece of `Information` about it - was considered and rejected: `Ownership` and `Knowledge` are separate concepts in this model, so a player could lose sight of their *own* inventory if nothing about their own gear happened to be explicitly granted to them, and an instance with zero `Information` rows at all has no well-defined answer either way. This ADR narrows on `Ownership` instead - a single, always-present-or-absent column - which sidesteps both problems entirely.

## Decision

### The rule: ownerless stays open, owned narrows to whoever can reach the owner

An item instance with **no owner** (`VItemInstance.owner_entity_id IS NULL`) - loose loot, an unclaimed item sitting in the world - stays visible to any tenant participant, exactly as [ADR 0032](0032-item-and-item-instance-crud-api.md) already has it; nobody is hiding it behind a character. An item instance **with an owner** becomes visible only if the caller can reach that owner:

- **Self**: the owner is in `entity_access.reachable_entity_ids`, rooted at `entity_access.controlled_character_entity_ids` (the caller's own characters) - the exact same reachable-set shape [RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md)'s self-or-managed *write* authorization already uses. Deliberately the same set, not a narrower read-only variant: an item placed inside a container you own is already something you can manage today regardless of who owns it, so it staying visible to you under the identical rule is consistency, not a new leak.
- **GM**: the owner is in `InformationVisibility.gm_reachable_entity_ids` ([ADR 0035](0035-campaign-scoped-gm-visibility.md)) - already resolved once per request by every one of these three routes for `descriptions` filtering, reused here rather than recomputed.
- **Admin**: `InformationVisibility.is_orga` - **not** `campaign_access.is_tenant_admin`. This is the one real judgment call this ADR makes: whether "can this admin see that Bob owns a hidden dagger" is an administrative-capability question or a narrative-knowledge question. Read as the latter, deliberately mirroring [RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md)'s own "administrative access != automatic character/GM knowledge" principle - a tenant `OWNER` who is *also* just playing in a campaign shouldn't metagame their players' hidden inventories any more than they should see GM-only secrets, and `is_orga` already carries the correct per-tenant `TenantAdminCampaignOptOut` suppression for exactly this reason. A tenant `OWNER` with no `ORGA` role, and no opt-out considerations either way, gets no special inventory visibility beyond what their own characters/GM grants reach - same as any other participant.

### Applied uniformly to every `VItemInstance`-selecting statement in the router

One predicate (`_visible_owner_predicate`), built once per request from `visible_entity_ids = self_reachable | visibility.gm_reachable_entity_ids` and `visibility.is_orga`: `true()` when `is_orga` (skip building the reachable sets at all rather than expressing "always true" as a SQL literal), else `VItemInstance.owner_entity_id.is_(None) | VItemInstance.entity_id.in_(visible_entity_ids)`. Applied as a `.where(...)` clause - before pagination, not a post-fetch Python filter - to `list_item_instances`'s plain and container-filtered statements alike, `list_item_instances_owned_by`, and `get_item_instance`'s own fetch.

**Deliberately *not* applied to `_get_v_item_instance_or_404`'s default (no-predicate) path**, which `_item_instance_out` still uses to build the canonical response after a successful `PATCH`/owner/container write. `_authorize_instance_write`'s `can_manage_campaign` check is not a subset of this read predicate - a plain tenant `OWNER` (no `ORGA`) managing another character's item via `can_manage_any_of_campaigns`'s `OWNER`-always-qualifies branch would otherwise 404 on the very write they just made, since that same `OWNER` gets no bonus read-reach here. `_get_v_item_instance_or_404` instead grows an optional `extra_predicate` parameter, passed only by `get_item_instance`'s own fetch, so both call sites still share one query shape without the write-response path picking up a filter it was never meant to have.

**`get_item_instance` 404s** for an instance that fails this predicate, via the same "no row matched" path an unknown or cross-tenant id already takes - consistent with this codebase's existing "404 hides existence" convention, not a redacted `200`. A caller in exactly this position (write access without matching read-reach) will see their own `PATCH` succeed with the correct body, then get a `404` on an independent follow-up `GET` for the same id - a real, deliberate asymmetry, not a bug: this ADR narrows *read* visibility only, and does not touch write authorization at all.

**`owned-by/{owner_entity_id}` needs no separate check at all.** Applying the predicate at the list level means an owner the caller can't reach simply contributes zero rows - the response comes back as an empty `groups: []`, identical in shape to "this character owns nothing." A caller can't distinguish "character doesn't exist," "exists but empty," and "exists but hidden from you" from the response alone - no existence leak, and no new code path needed beyond the shared predicate.

### Catalog reads (`GET /items`) are unaffected

`Item` rows have no `owner_entity_id` at all - "ownerless stays visible" already covers 100% of the catalog. Nothing about this ADR touches `routers/items.py`.

## Not in scope

The broader, information-visibility-based version considered in Context (hide an instance unless the caller can see some `Information` about it) - rejected here, not merely deferred, for the reasons above; revisit only if ownership-based narrowing turns out to be insufficient in practice. Group-based inventory visibility (a `Knowledge`/`GroupMember` grant extending to *item* visibility, not just information content) - out of scope, this ADR only reasons about character/GM/admin reachability. Any change to write authorization - self-or-managed already governs `PATCH`/`DELETE`/owner/container mutations correctly and is untouched here; this ADR is read-only in scope, matching its own name.

## Consequences

- A real, if narrow, behavior change to [ADR 0032](0032-item-and-item-instance-crud-api.md): item-instance reads are no longer "any participant sees every instance in the tenant," but "any participant sees every ownerless instance, plus whichever owned instances their own characters/GM grants/ORGA role reach."
- The exact same reachable-set that already governs self-or-managed *write* authorization now also governs *read* visibility for owned instances - one mental model for "is this my stuff" across both, not two subtly different ones.
- No migration, no schema change - `Ownership`/`entity_access.reachable_entity_ids`/`InformationVisibility.gm_reachable_entity_ids`/`is_orga` all already exist exactly as this needs them.
- This is an application-level read filter, not a security boundary - RLS/tenant isolation is unrelated and unaffected; every row this predicate excludes was already tenant-scoped and reachable by the DB role, just not meant to be shown to this particular caller.
- One pre-existing test (`test_owned_by_groups_multiple_owners_multiple_containers_and_uncontained`) needed updating, not just re-verifying: it used bare `Entity` rows as owners under a plain tenant `OWNER` Membership to test the owned-by grouping mechanism itself, which this ADR's rule now correctly denies read access to - switched to `ORGA` so it keeps testing grouping/pagination rather than accidentally re-asserting the old, now-superseded visibility rule.
