# 0031 - Character table, and the user/membership/player/GM read REST API

Status: accepted

## Context

The access/role graph - who is a tenant owner/orga, who plays which campaign as which character, who GMs which campaign - is fully built ([ADR 0022](0022-user-tenant-membership.md)/[ADR 0024](0024-campaign-and-player.md)/[ADR 0025](0025-character-being-and-ownership.md)/[ADR 0026](0026-campaign-gm-orga-and-access-rule.md)) but almost entirely unreadable over HTTP. The one exception, `GET /me`, exists "purely to prove the whole pipeline end-to-end... not the start of a fuller `/users` API" and returns only tenant-wide `Membership` rows.

Revising this also surfaced a real gap: there was no dedicated `character` table, only `being` ([ADR 0025](0025-character-being-and-ownership.md)), which covers every sentient entity - PC or background NPC - identically, with nowhere to add character-specific richness later without bloating that one table for everything sentient, tracked or not. This ADR accepts [RFC 0004](../rfcs/0004-user-membership-player-character-gm-read-api.md), close to verbatim - see it for the full reasoning trail.

## Decision

### Schema addition: the `character` table

`character(entity_id, tenant_id, owner_player_id, created_by, updated_by)` - layered directly under `being`, not a sibling extending `entity` the way `item`/`item_instance` are: `character.entity_id` is PK **and** FK to `being.entity_id` (`ON DELETE CASCADE`), not to `entity.id` directly - the first three-level class-table-inheritance chain in this schema (`entity` → `being` → `character`). Modeled the same way every other CTI extension in this schema is (a plain `Base` subclass with its own explicit `being` relationship), **not** SQLAlchemy's own joined-table-inheritance mechanism (Python subclassing + `polymorphic_identity`) - nothing else here uses that either, and introducing it for just this one case would be a surprising, unexplained exception. A bare `being` with no `character` row is still perfectly valid - an unnamed monster stub, background NPC, or anything not worth individual tracking.

`owner_player_id` moves here from `being`, keeping its exact existing shape (nullable, `FK → player.id`, `ON DELETE SET NULL`). `created_by`/`updated_by` land here too, per [ADR 0029](0029-attribution-created-by-updated-by.md)'s phased table - `character.created_by` records who *promoted* this being, a different, also-meaningful fact from `entity.created_by` (who made the being exist at all).

**`character_player.character_entity_id` and `group_member.character_entity_id` both retarget from `being.entity_id` to `character.entity_id`.** A `being` now has to be "promoted" to a `character` row before it can be rostered to a player or added to a knowledge group - a real behavior change from [ADR 0025](0025-character-being-and-ownership.md)/[ADR 0028](0028-knowledge-and-group-membership.md)'s original design, accepted here as the correct tightening. Confirmed zero rows existed in `being`/`character_player`/`group_member` before this migration (checked directly, not assumed), so no data reconciliation was needed.

No new columns beyond the `owner_player_id` move - "we might add custom fields to `character` later" is the reason this table exists, but none are designed yet.

### `v_character`

Mirrors `v_item`/`v_item_instance` ([ADR 0019](0019-item-and-v-item.md)): `entity_id`, `tenant_id`, `owner_player_id` (the one column genuinely specific to this view), `description_id`/`title` (from the entity's `description`-typed `Information`), `container_entity_id` (from `containment`). Deliberately no RPG-flavored stat columns - which stats matter enough for a dedicated column here is a product call this ADR doesn't make; anything else stays reachable through the shared stat-group properties below. `security_invoker = true`, excluded from Alembic autogenerate (`migrations/env.py`'s `_VIEW_TABLE_NAMES`), same as `v_item`/`v_item_instance`.

**`ItemViewMixin` renamed `EntityViewMixin`**, shared by `VItem`/`VItemInstance`/`VCharacter`. Every property was already generic (built on `Entity`'s own relationships, nothing item-specific) - sharing it avoids a second, drifting copy of the identical logic.

### `GET /me`, extended

`MeOut` gains `players: list[PlayerSummaryOut]` (every `Player` row this user holds, across every tenant/campaign, each with its own `characters` resolved through `character_player`) and `campaign_gm_grants: list[CampaignSummaryOut]` (every campaign this user GMs). `PlayerSummaryOut` carries its own `tenant_id`/`campaign_id` explicitly - unlike the campaign-nested `PlayerOut`, `/me` spans every tenant, so there's no URL scoping to infer them from.

### Tenant-wide roster: `GET /tenants/{tenant_id}/memberships`

Broadened from a pure membership list to the tenant's full roster - every user with *any* standing in the tenant, not just its tenant-wide admins. A discriminated union (`TenantRosterEntryOut = MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut`, `Field(discriminator="kind")`), matching the `PayloadOut` precedent ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)) rather than one schema with sometimes-meaningful fields. One row per relationship, not per user. Still gated by `get_tenant_context`, unchanged - an ordinary player doesn't need this to find their own standing, `/me` already covers that. Combined in Python from three separate queries (mirroring `information_visibility.resolve_information_visibility`'s own precedent), not one SQL `UNION` - the three row shapes are genuinely heterogeneous, and this is tenant-admin-only, so the data is bounded by how many people administer one world, not by total tenant traffic; paginating the already-fetched list (`fastapi_pagination.paginate`, not `apaginate`) is a reasonable trade at that scale.

### Campaign roster: `GET .../campaigns/{id}/players[/{player_id}]`, `GET .../campaigns/{id}/gms`

Gated by `get_campaign_context` (ADR 0030), not `get_tenant_context` - an ordinary player or GM reaching their own campaign's roster has no tenant-wide `Membership` row to satisfy the stricter gate. `PlayerOut`/`PlayerDetailOut` are the same shape (`Player` has no columns the summary omits) - kept as two classes anyway, matching the RFC's own endpoint table and giving the detail route its own OpenAPI schema. `GmOut` is unpaginated, matching `OwnedByResponse`'s precedent for a collection inherently small and bounded by construction.

### Tenant-wide character roster: `GET /tenants/{tenant_id}/characters[/{character_id}]`

Specifically a roster of `Character` rows, not every `Being` - a bare, untracked being doesn't appear here. Deliberately bare-tenant-scoped, not campaign-nested: a character has no single fixed campaign (roster reuse, [ADR 0025](0025-character-being-and-ownership.md)). Gated by `get_tenant_context` - only tenant-wide members (who already see everything) reach it, so no `information_visibility`-style filtering is needed. `CharacterSummaryOut(entity_id, name, is_pc)`; `CharacterOut` adds `owner_player_id`, `players: list[PlayerSummaryOut]`, `created_by`/`updated_by`. Accepted minor redundancy: reusing `PlayerSummaryOut` means each returned player entry redundantly re-includes the very character being viewed.

### A genuine schema circularity, resolved

`PlayerSummaryOut.characters` needs `CharacterSummaryOut`; `CharacterOut.players` needs `PlayerSummaryOut` right back - a real two-way reference between `schemas/players.py` and `schemas/characters.py`, not an oversight. Resolved the standard way: `schemas/characters.py` only imports `PlayerSummaryOut` under `TYPE_CHECKING` (so it never really imports `players.py`, which itself really imports `characters.py` for `CharacterSummaryOut` - a real cycle either direction if both were real imports), and `CharacterOut.from_character` imports it locally, deferred until called. `routers/characters.py` - guaranteed to load once, at app startup, and needing both schemas anyway - calls `CharacterOut.model_rebuild(_types_namespace={"PlayerSummaryOut": PlayerSummaryOut})` at module level to make the forward reference resolvable, rather than relying on whichever module happens to import `schemas/players.py` first.

### Attribution fields deferred where the underlying column doesn't exist yet

RFC 0004's own schemas (`MembershipRosterEntryOut`, `PlayerRosterEntryOut`, `PlayerOut`) carry `created_by`/`updated_by`. Per [ADR 0029](0029-attribution-created-by-updated-by.md)'s phased table, `membership`/`player`'s attribution pair doesn't land until user/player/character CRUD (ADR 0036/RFC 0007) actually writes to those tables - exposing a column that doesn't exist would be building ahead of that slice. Left out of this ADR's schemas, to be added as a small, natural follow-up once ADR 0036 lands. Same reasoning applies to `GmRosterEntryOut.created_by` (`campaign_gm`'s attribution lands with campaign CRUD, ADR 0034/RFC 0006). `CharacterOut.created_by`/`updated_by` are unaffected - `character`'s own pair lands in this same ADR.

## Not in scope

**Any mutation** - creating/removing memberships, players, characters, or GM grants is [RFC 0007](../rfcs/0007-user-player-character-crud-api.md) (players/characters/membership) and [RFC 0006](../rfcs/0006-campaign-crud-api.md) (GM grants).

**Full character sheets** (stats, inventory, descriptions) - already served by the existing `entities`/`items` read API; `Being.entity_id` *is* an `entity.id`, so `GET /tenants/{id}/entities/{character_id}` already answers "what does this character know/have."

**Group knowers** (`group_member`) - no REST surface, nothing asked for one.

**Custom fields on `character`** - the whole reason this table exists is to have somewhere to add them later; none are added now.

## Open questions

Carried from RFC 0004, unresolved here:

- No dedicated `GET .../admin-opt-outs` endpoint - a caller's own opt-out state is implicit in whether they show up as a player/GM elsewhere.
- `PlayerOut.characters` doesn't flag that a character might also appear in a sibling campaign's roster (roster reuse) - the tenant-wide character endpoint is where a client discovers every campaign a character is linked to.
- No "list every background NPC" view - nothing asked for it.
- **Is retargeting `character_player`/`group_member` to require a `Character` row the right call?** A genuine reversal of ADR 0025/ADR 0028's original design (either could target any `being` before) - revisit if a GM wants to roster or group-link a plain NPC without first promoting it.

## Consequences

- [ADR 0025](0025-character-being-and-ownership.md) (`being`'s original shape including `owner_player_id`, `character_player`'s original target) and [ADR 0028](0028-knowledge-and-group-membership.md) (`group_member`'s original target) both need superseding notes - added to each.
- `docs/architecture/diagrams/domain-model-er.md` updated: a new `CHARACTER` box layered under `BEING`, `owner_player_id` moved boxes, `character_player`/`group_member`'s edges retargeted.
- [RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md)'s reachability walk ("every `Being` linked via `CharacterPlayer` to a `Player`") needs a terminology pass once picked up - the join target is now `Character`, though the entity-id set it produces is unaffected.
- `Player.owned_beings` renamed `Player.owned_characters`, following the column to `Character` - a plain `being` was never a valid target, so nothing meaningful is lost.
- `membership`/`player`/`campaign_gm` tables themselves are unaffected structurally by this ADR (only their eventual attribution columns are deferred, per above) - no migration need beyond `character`/`being`/`character_player`/`group_member`.
- New `tests/conftest.py` helpers `make_being`/`make_character`, matching `make_tenant`/`make_campaign`/`make_player`'s existing precedent - promoted immediately (not after independent duplication first) since this ADR's own migration forced every existing `being`/`character_player`/`group_member` test to be touched anyway.
