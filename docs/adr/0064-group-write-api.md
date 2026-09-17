# 0064 - Group write API: create/rename/delete, membership, bulk add, duplicate

Status: accepted

## Context

`GroupMember` ([ADR 0028](0028-knowledge-and-group-membership.md)) links a character entity to a group entity - a group itself is a bare `entity` with no dedicated concrete table, "defined purely by having at least one `GroupMember` row naming it as `group_entity_id`" ([ADR 0045](0045-read-only-groups-api.md)). ADR 0045 built a read-only surface (`GET .../groups`, `GET .../groups/{id}/members`, `GET .../characters/{id}/groups`) and explicitly deferred any write surface: "creating groups and managing membership stays out of scope, as it was going in."

That gap is real now: a GM organizing an NPC faction, or a table wanting a player-run "The Party" group to target with knowledge grants ([ADR 0028](0028-knowledge-and-group-membership.md)) or group-scoped notifications ([ADR 0059](0059-group-scoped-notifications.md)), has no way to create one, add or remove members, rename it, retire it, or copy an existing group's roster into a new one - only ever manageable today by hand-editing the database.

## Decision

### Authorization: reuse `_require_can_manage_group`, add `can_manage_character` where a specific new member is at stake

`routers/groups.py` already has `_require_can_manage_group` (built for ADR 0059's group-scoped notifications): fail-closed, the caller must be able to `campaign_access.can_manage_character` every *current* member of the group, an empty group trivially passing. Every write below reuses it as-is for "does the caller have standing over this group at all" - renaming, deleting, removing a member (removing member X is already covered by "manage every current member," X included), and duplicating (copying a roster you can already manage in full needs no separate per-member check on the copy).

Adding a *new* member is the one case `_require_can_manage_group` alone doesn't cover, since the candidate isn't a current member yet: the create/add-member/bulk-add routes below additionally require `can_manage_character` on each character being added, individually. This mirrors [ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)'s `merge` needing both sides authorized, not just the source.

Creating a *group entity itself* (before any members exist) is gated only by `require_tenant_participant` - the same low bar `GET /tenants/{tenant_id}/groups` already uses (ADR 0045/RFC 0005 precedent: browsing/creating a group doesn't imply a tenant-wide Membership row). A brand-new, still-empty group is exactly as costly to create as it is to enumerate later, and a plain player forming their own player-run group is a legitimate, unprivileged use case.

### `POST /tenants/{tenant_id}/groups` - create a group entity

Body: `GroupCreate{name: str, member_character_ids: list[uuid.UUID] = []}`. Creates a new bare `Entity` (server-generated id, never accepted from the client, matching `create_campaign`'s own precedent), then one `GroupMember` row per id in `member_character_ids`, each individually validated: must resolve to a real `Character` in this tenant (`422 InvalidCharacterError`, mirroring `InvalidUserError`'s existing shape, otherwise a raw `GroupMember.character_entity_id` FK violation would surface as a bare 500) and must not equal the freshly-created group's own id (structurally impossible here, since the id is server-generated after the request body is already parsed) and must pass `can_manage_character`. `201` + `Location` (a new `GET .../groups/{group_entity_id}` route, below) + `EntitySummary` of the created entity.

A group created with zero initial members has the same "not enumerable via `GET /groups` until it has a member" property ADR 0045 already named and accepted - not a new gap, and directly reachable anyway via the `Location` header this route returns.

### `GET /tenants/{tenant_id}/groups/{group_entity_id}` - single-group lookup

New route, `EntitySummary`, gated by `require_tenant_participant` + `get_entity_or_404` - the same two checks `list_group_members` already runs. Needed as the `Location` target for create/duplicate below and as the PATCH/DELETE response shape; deliberately not the heavier `GET /entities/{id}`/`EntityDetailOut` (seven eager-loaded relationships, ADR 0038) - this router's own existing shape is `EntitySummary` everywhere, and a group's identity is exactly "an entity with a name," nothing more. `ETag` header set from the entity's own `updated_at`, same as every other single-resource GET in this codebase.

### `PATCH /tenants/{tenant_id}/groups/{group_entity_id}` - rename

Body: `GroupUpdate{name: str | None = None}`, `exclude_unset` like every other PATCH here. Only `Entity.name` is mutable - a group has nothing else of its own to update. Gated by `_require_can_manage_group`; `If-Match` optional, checked against the entity's own `updated_at` (the only concurrency token available - there is no dedicated `Group` row to carry one).

### `DELETE /tenants/{tenant_id}/groups/{group_entity_id}` - retire a group

Deletes every `GroupMember` row naming this `group_entity_id` - it stops being a group - but **does not delete the underlying `Entity`**. Nothing guarantees the entity was created only to serve as a group (RFC 0001: "nothing stops the same `entity_id` from having rows in both `item` and `being` at once," and the same is true of an entity also used as a group); deleting it out from under a caller who happened to reuse an existing entity as a group would destroy something wider than "this group." `204`, gated by `_require_can_manage_group`, `If-Match` optional against the entity's `updated_at`. Idempotent - a group with zero members already is a no-op.

This does mean an entity created purely through `POST /groups` and later fully deleted this way becomes a permanently orphaned bare entity with no members and no other role - a real, accepted gap, matching this codebase's practice of naming rather than silently absorbing this kind of asymmetry (e.g. ADR 0041's own residual-gap section). Not solved here: reclaiming a truly-orphaned entity would need to prove it has no other role across every concrete table, which is more machinery than this slice's brief asked for.

### `PUT`/`DELETE /tenants/{tenant_id}/groups/{group_entity_id}/members/{character_entity_id}` - single membership

`PUT`: idempotent add, mirroring `grant_campaign_gm`'s exact shape - a re-`PUT` of an existing membership is a no-op, not a 409. Requires `character_entity_id` to resolve to a real `Character` in this tenant (`422 InvalidCharacterError`, same "a path/body id references something that isn't there" shape `grant_campaign_gm` already uses for its own `user_id` path parameter via `InvalidUserError` - not a `404`, since `character_entity_id` here names a sub-resource *value* to attach, not a resource being addressed directly), the self-loop guard below, `_require_can_manage_group` (existing members) and `can_manage_character` on `character_entity_id` itself. `DELETE`: idempotent remove - already covered by `_require_can_manage_group` alone, since the member being removed is by definition a *current* member. Both return `200` + `list[EntitySummary]`, the full updated member list (`list_group_members`'s own query, called directly) - more immediately useful than a bare parent reference, and the caller already knows the shape from `GET .../members`.

Self-loop guard (`422 InvalidGroupMemberError`): `character_entity_id == group_entity_id`, pre-checked in the application rather than left to surface as a raw `group_member_no_self_loop` `CHECK` violation (a real, reachable case per that constraint's own ADR 0028 rationale - an entity can independently acquire both a group role and a `Character` row).

### `POST /tenants/{tenant_id}/groups/{group_entity_id}/members/bulk` - bulk add

Body: bare `list[uuid.UUID]` (character entity ids), matching `bulk_assign_item_instances`/`bulk_create_memberships`'s own bare-list body convention. `_require_can_manage_group` is checked **once**, up front - it doesn't vary per item, the same reasoning [ADR 0062](0062-bulk-invite-to-tenant.md) gives for its own single up-front `_require_owner` check. `can_manage_character`, the character-exists check, and the self-loop guard **do** vary per item, so each runs inside its own `session.begin_nested()` (a SQL `SAVEPOINT`) exactly like `bulk_assign_item_instances`/`bulk_create_memberships` - never all-or-nothing, a caught `fastapi_problem.error.Problem` becomes that item's own `"error"` entry via its `.marshal()` shape, every other item's already-applied change proceeds to the one shared commit. Response: always-`200` `list[GroupMemberResultItem{character_entity_id, status: "ok" | "error", problem: ProblemOut | None}]`.

### `POST /tenants/{tenant_id}/groups/{group_entity_id}/duplicate` - copy a group's roster

Body: `DuplicateGroupRequest{name: str | None = None}` - defaults to the source's own name when omitted. `_require_can_manage_group` against the **source** only; since that already proves the caller can manage every one of its current members, no separate per-member check is needed on the copy - a real, load-bearing simplification, not a shortcut. Creates a new `Entity` plus one new `GroupMember` row per member the source currently has (same `character_entity_id` set, new `group_entity_id`). `201` + `Location` (`get_group`) + `EntitySummary` of the new group. An empty source produces an empty duplicate, not an error - not asked to be otherwise.

## Not in scope

Marking an entity as "is a group" persistently, or any other schema/migration change - the bare-entity, `GroupMember`-defines-membership model stands unchanged; every write here is ordinary `Entity`/`GroupMember` CRUD. Reclaiming an orphaned, fully-emptied group entity (see the `DELETE` section above). A finer per-operation authorization model than "manage every current/every-being-added member" - deliberately the same fail-closed shape ADR 0059 already established, not revisited here. Renaming/deleting a group's *members* (that's `PATCH`/`DELETE /characters/{id}`, unrelated to this ADR).

## Consequences

- New `schemas/groups.py`: `GroupCreate`, `GroupUpdate`, `DuplicateGroupRequest`, `GroupMemberResultItem`.
- New typed problems: `InvalidCharacterError` (422), `InvalidGroupMemberError` (422).
- `routers/groups.py` gains `get_group`, `create_group`, `update_group`, `delete_group`, `add_group_member`, `remove_group_member`, `bulk_add_group_members`, `duplicate_group`. `list_group_members`'s own query is factored into a small helper both it and the two membership-mutating routes call, so the member-list response shape can't drift between them.
- No migration - every write is against `entity`/`group_member`, both already existing (ADR 0012/0028).
- A GM or player can now create, rename, retire, and populate a group (one at a time or in bulk) and clone an existing one's roster entirely over the REST API, closing the write-side gap ADR 0045 deliberately left open.
