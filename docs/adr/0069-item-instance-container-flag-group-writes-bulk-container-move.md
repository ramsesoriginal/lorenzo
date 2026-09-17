# 0069 - apps/api additions requested by loot-bot: container flag, group-membership writes, bulk container move

Status: superseded by [ADR 0064](0064-group-write-api.md), [ADR 0065](0065-bulk-item-instance-container-move.md), and [ADR 0066](0066-is-container-computed-field.md)

Numbered 0065 originally; renumbered to 0069 on merge into `main` alongside this file's own [ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md) - `main` had independently claimed 0064-0067 for the very additions requested below, in the meantime. Kept in place per this repo's own "superseded ADRs stay, pointing at the replacement" convention ([docs/adr/README.md](README.md)), not deleted, since it's a real record of what was asked for and why.

All three requests landed for real, shaped somewhat differently than guessed here - see each linked ADR for the actual, adopted design (notably: group creation accepts initial members in one call and the write surface is much larger than the two primitives sketched below; the bulk-move endpoint is `POST .../item-instances/bulk-move` with a from-container-or-explicit-list choice, not `bulk-set-container`; `is_container` is a computed read-only field with a structural fallback, not a migrated, PATCH-able column). [ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)'s own Addendum covers how loot-bot actually consumed them.

## Context

Three loot-bot-requested features need real `apps/api` additions that either don't exist at all or were explicitly scoped out by an earlier ADR. Per the user's own direction, `apps/api` isn't touched in [ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)'s branch - this ADR exists so the decision doesn't get re-made or re-litigated once someone picks it up (mirroring [ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md)'s own "accepted, implementation deferred" precedent), and so loot-bot's own side can be built immediately once each one lands.

## Decision

### 1. `is_container: bool` on `ItemInstance`

Lets a player/GM mark which of their items are actually usable as a destination container, closing a gap `move.ts`'s own existing docstring already names: "nothing in the real API flags which owned items are actually container-capable."

- New nullable boolean column, same shape as the existing `is_magical`/`is_cursed` precedent (`apps/api/src/lorenzo_api/models/v_item_instance.py:41-42` and whichever concrete table backs them) - default `false`, one Alembic migration.
- Exposed through `_common_item_fields` (`apps/api/src/lorenzo_api/schemas/items.py`) onto both `ItemOut` and `ItemInstanceOut`, identically to how `is_magical`/`is_cursed` already are.
- Writable through the **existing** `PATCH /tenants/{tenant_id}/item-instances/{entity_id}` route - add `is_container: bool | None` to `ItemInstanceUpdate`. No new endpoint, no new authorization rule: the route's current self-or-managed check already covers "toggle a flag on your own stuff."

Once shipped: `mise run generate-client` in `apps/loot-bot`, then `move.ts`'s and `set-current.ts`'s container autocomplete narrow to `is_container === true` instead of "everything you own," and `/inventory search`/a new `/mark-container` command becomes buildable.

### 2. Group-membership write endpoints

[ADR 0045](0045-read-only-groups-api.md) added group reads and explicitly deferred writes ("No write/management endpoints... explicitly out of scope"). Two new routes needed on `apps/api/src/lorenzo_api/routers/groups.py`:

- **`POST /tenants/{tenant_id}/groups`**, body `{name: str}` → find-by-name-or-create the underlying bare `Entity` (a group has no dedicated table per ADR 0028/0045 - it's defined purely by having `GroupMember` rows, so "creating" one ahead of its first member is a new capability, not a variant of an existing one). Returns `EntitySummary`. Satisfies "create it, if not yet present" without a caller needing to pre-resolve an id.
- **`PUT /tenants/{tenant_id}/groups/{group_entity_id}/members/{character_entity_id}`** → inserts one `GroupMember` row (idempotent - already-a-member is a no-op, not an error). Authorization: reuse `campaign_access.can_manage_character` against the character *being added* - the same helper `routers/groups.py`'s own existing `_require_can_manage_group` already calls per-member, just applied to the new member instead of the group's current roster. Self, that character's GM, or tenant orga/owner.

Both requested loot-bot commands ("GM adds character X to group Y" and "GM adds every recently-active character in this channel to group Y") compose from just these two primitives client-side - no bespoke bulk-membership endpoint needed.

### 3. Bulk container move

`POST /tenants/{tenant_id}/item-instances/bulk-set-container`, body `list[{entity_id, container_entity_id, if_match?}]`. Mirrors `bulk-assign`'s own existing contract exactly (`BulkAssignResultItem`-shaped response, never all-or-nothing - one result per input entry regardless of outcome, same per-item `_authorize_instance_write`). `bulk-assign` only ever reassigns *owner*; there is no bulk equivalent for *container* today, confirmed by reading `routers/item_instances.py` in full - this is a genuine gap, not a duplicate of something that already exists.

## Consequences

- Three independent, additive changes - none require touching the other two, and none change any existing endpoint's default behavior (all either add a new optional field, a new route, or a wholly new endpoint).
- Each needs an Alembic migration (#1) or is migration-free (#2, #3 - no new tables, `group_member` already exists per ADR 0028).
- loot-bot's own consuming code is fully specified in [ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md) and this file's own per-section notes, so picking any one of these up doesn't require re-deriving the client-side design.
