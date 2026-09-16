# 0045 - Read-only groups API

Status: accepted

## Context

`GroupMember` ([ADR 0028](0028-knowledge-and-group-membership.md)) already exists as a concept - it links a character entity to a group entity, letting an author grant knowledge to a whole group at once - but has zero HTTP exposure, not even read-only. A client wanting to let a user pick an existing group as a visibility target for a note (the concrete use case that prompted this) has no way to list what groups exist or who's in them.

The domain model shape matters here: per ADR 0028, "a group is a bare `entity` with no dedicated concrete table" - there is no `Group` row anywhere to `SELECT * FROM` the way there is for, say, `Character`. A group is defined purely by having at least one `GroupMember` row naming it as `group_entity_id`.

## Decision

`GET /tenants/{tenant_id}/groups` → `Page[EntitySummary]`: every distinct `group_entity_id` in `group_member` for this tenant, joined to `Entity` for its name. This is the read the data model actually supports - **an intentionally-created-but-still-empty group (zero members so far) is not enumerable this way**, a direct, accepted consequence of groups having no dedicated table to register one in ahead of its first member, not a new gap this ADR introduces.

`GET /tenants/{tenant_id}/groups/{group_entity_id}/members` → `list[EntitySummary]`, not paginated - bounded by one group's membership, mirroring `GET .../item-instances/owned-by/{owner_entity_id}`'s identical "one bounded collection" precedent ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)). `404` (via `get_entity_or_404`, existing) if `group_entity_id` isn't a real entity in this tenant at all; an empty list (not a 404) if it is one but currently has no `GroupMember` rows - unlike [ADR 0040](0040-item-instance-read-visibility.md)'s item-instance precedent of collapsing "exists but hidden" into "not found," a group's bare existence isn't a secret the way another character's inventory is, so there's no reason to hide the distinction here.

`GET /tenants/{tenant_id}/characters/{character_id}/groups` → `list[EntitySummary]` - the reverse direction (nice-to-have from the original brief), added alongside the other two since it's a near-free reverse query once they exist: which groups a specific character belongs to, sparing a client from fetching every tenant group and cross-referencing membership client-side just to answer "which of these are mine."

Gated by `is_tenant_participant` (the two new routes on `routers/groups.py`) - matching `routers/item_instances.py`'s own precedent, not the stricter Membership-only gate `routers/items.py`/`routers/characters.py`'s pre-existing routes use - a plain player composing a knowledge grant needs to browse groups without holding a tenant-wide Membership row. The characters-router addition keeps that router's own existing, stricter `_require_tenant_member` gate instead, for consistency with its neighboring routes rather than with `groups.py`.

No write/management endpoints - creating groups and managing membership stays out of scope, as it was going in; only reading is added.

## Not in scope

Any write surface for `GroupMember` (creating a group, adding/removing a member) - explicitly out of scope, per the original brief. A dedicated `Group` concept/table - the bare-entity model stands; this ADR only adds reads over what already exists.

## Consequences

- New `routers/groups.py` (`list_groups`, `list_group_members`), registered in `main.py`. One addition to `routers/characters.py` (`list_character_groups`).
- No schema/model/migration changes - this is a pure read surface over the existing `group_member`/`entity` tables.
- A client can now browse a tenant's groups and their membership (and a character's own groups) well enough to offer "pick an existing group" in a UI, closing the concrete gap that prompted this ADR.
