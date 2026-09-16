# 0030 - Tenant and campaign read REST API

Status: accepted

## Context

`tenant` and `campaign` exist ([ADR 0013](0013-tenant-table-bootstrap.md)/[ADR 0022](0022-user-tenant-membership.md)/[ADR 0024](0024-campaign-and-player.md)) but neither is complete enough to back a real REST surface, and neither had any REST surface at all. `tenant` was just `{id, name}` - no URL-friendly identifier for frontend clients to link to, no description. `campaign` was `{id, tenant_id, name, game_system}` - same two gaps, plus no way to mark a campaign as secret (hidden from casual browsing) and no attachment point for richer information (GM notes, images) beyond its own bare columns.

Access needed a real answer too. `get_tenant_context` requires tenant-wide `Membership`, which ordinary players/GMs legitimately never have ([ADR 0022](0022-user-tenant-membership.md)). An ordinary tenant participant should be able to browse the tenant's campaign catalog, just with secret campaigns filtered out unless they're that campaign's own GM or a tenant admin. Separately, [`campaign_access.can_access_campaign`](../../apps/api/src/lorenzo_api/campaign_access.py) ([ADR 0026](0026-campaign-gm-orga-and-access-rule.md)) special-cased only `ORGA`, not `OWNER` - resolved here in favor of `OWNER` getting the same bypass.

This ADR accepts [RFC 0003](../rfcs/0003-tenant-campaign-read-api.md), close to verbatim - see it for the full reasoning trail.

## Decision

### Schema additions

All new columns/relations on tables that already exist - no new concrete type, no change to the entity/component core itself.

- **`tenant.slug`** - `TEXT NOT NULL`, globally `UNIQUE`. URL-safe, for frontend routing, instead of a bare UUID. **Gets a server-side default** (`gen_random_uuid()::text`), extending [ADR 0022](0022-user-tenant-membership.md)'s `tenant.name` reasoning to a case that RFC didn't spell out for slug specifically: ~50 existing bare `Tenant()` fixture calls make the retrofit cost identical to `name`'s own. A random default is a placeholder, not a real one - real tenant-creation code (RFC 0012, not built yet) always supplies a derived slug explicitly.
- **`tenant.description`** - `TEXT NOT NULL`, server-defaulted to `''`, same reasoning as `name`/`slug`.
- **`campaign.slug`** - `TEXT NOT NULL`, `UNIQUE(tenant_id, slug)` - scoped to the tenant, matching `stat_group`/`stat_definition`'s existing `UNIQUE(tenant_id, name)` precedent, not globally unique.
- **`campaign.description`** - `TEXT NOT NULL`, no server default - unlike `tenant`, a shared literal default here isn't even safe (some existing tests create more than one campaign per tenant, and slug's uniqueness would collide). Test fixtures use the new `make_campaign()` conftest helper instead of a column default.
- **`campaign.secret`** - `BOOLEAN NOT NULL DEFAULT false`. Defaults to visible: the exceptional case is hiding a campaign from the tenant's general roster, not the reverse. Governs the *list* endpoint's filtering only - it is not an access-control flag and doesn't change what `get_campaign_context` admits.
- **`campaign.entity_id`** - `UUID NOT NULL`, `UNIQUE`, FK to `entity.id`, `ON DELETE RESTRICT`. A dedicated `Entity` row created in the same transaction as the campaign itself - **not** a class-table-inheritance PK+FK the way `item`/`being` extend `entity`; `campaign` keeps its own surrogate `id`. `UNIQUE` wasn't asked for explicitly by the RFC but follows directly from "a *dedicated* Entity row" and costs nothing to enforce. Purpose: attaching `Information`/`Knowledge` to a campaign the same generic way any other entity gets richer content, without inventing a campaign-specific mechanism. `ON DELETE RESTRICT` covers only the unusual case of someone deleting the anchor `Entity` directly, out of band - deleting the *campaign* itself must explicitly delete its linked `Entity` too (RFC 0006, not built yet).
- **`campaign.created_by`/`updated_by`** - [ADR 0029](0029-attribution-created-by-updated-by.md)'s pair, landing here per that ADR's phased table.

### Access-gating rule (governs this ADR and every later REST slice)

Two tiers, not one:

- **Bare tenant-level collections** (`/tenants/{tenant_id}/<resource>`, not further nested under a specific `campaign_id`) stay gated by the existing `get_tenant_context` - unchanged, tenant-wide `Membership` (owner/orga) required.
- **Campaign-nested resources** (`/tenants/{tenant_id}/campaigns/{campaign_id}/...`) are gated by a **new** `get_campaign_context` dependency instead, wrapping the already-built `campaign_access.can_access_campaign` (RFC 0002's rule: a `player` row, a `campaign_gm` row, or tenant-admin without an opt-out). An ordinary player has zero `Membership` rows and must still reach their own campaign.

The campaign *list* endpoint is a deliberate exception to the first bullet - see below.

### `get_tenant_or_404` and `get_campaign_context` (`dependencies.py`)

`get_tenant_or_404`: existence-only, no `Membership` check - still sets `app.tenant_id` (scoping, not authorization). `get_campaign_context`: depends on `get_tenant_or_404` directly (not just calling it), so FastAPI's per-request dependency caching means a route that also depends on `get_tenant_or_404` at the router level doesn't pay for a second query; confirms the campaign exists and belongs to that tenant (query-level `WHERE`, per [ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)'s explicit-filtering rule, not a `session.get()` plus a Python-level check); then `can_access_campaign(...)`. All three failure modes raise the *same* `CampaignNotFoundError`, extending `get_tenant_context`'s existing "can't distinguish doesn't-exist from not-a-member" rule ([ADR 0023](0023-authgear-token-verification.md)) from two cases to three.

### `campaign_access.can_access_campaign` now admits `OWNER`, via a new `is_tenant_admin`

Revises [ADR 0026](0026-campaign-gm-orga-and-access-rule.md)/[ADR 0028](0028-knowledge-and-group-membership.md): `can_access_campaign` checked `is_tenant_orga` (role `== ORGA` specifically) for its blanket-bypass branch; it now checks a new `is_tenant_admin(session, *, tenant_id, user_id) -> bool` (role `in (OWNER, ORGA)`) instead. **Deliberately narrower in effect than it sounds** - it only widens *campaign-resource reachability*, not *information visibility*: [`information_visibility.py`](../../apps/api/src/lorenzo_api/information_visibility.py)'s `is_orga` keeps checking `is_tenant_orga` (`ORGA` only) unchanged, per [RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md)'s "administrative access != automatic character/GM knowledge" principle.

The opt-out mechanism widens symmetrically: `orga_campaign_opt_out` is **renamed** `tenant_admin_campaign_opt_out` (same shape) and now applies to whichever of `OWNER`/`ORGA` the caller holds.

New `is_tenant_participant(session, *, tenant_id, user_id) -> bool`: a `Membership` row (any role), **or** any `Player` row, **or** any `CampaignGm` row, anywhere in the tenant - the same three-short-circuiting-existence-checks shape as `can_access_campaign` itself, tenant-wide rather than campaign-scoped. Gates the campaign list endpoint below.

### Endpoints

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants` | `CurrentUser` only (unscoped, like `/me`) | `Page[TenantSummaryOut]` |
| GET | `/tenants/{tenant_id}` | `get_tenant_context` | `TenantOut` |
| GET | `/tenants/{tenant_id}/campaigns` | `get_tenant_or_404` + `is_tenant_participant` | `Page[CampaignSummaryOut]`, filtered by secrecy |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}` | `get_campaign_context` | `CampaignOut` |

**`GET /tenants`** answers "every tenant I belong to in *any* capacity." Filtered directly in SQL via `EXISTS` against `Membership`/`Player`/`CampaignGm` (not combined in Python the way `information_visibility.resolve_information_visibility` does it) so real pagination works over an arbitrarily large tenant list. `TenantSummaryOut` carries `id`, `slug`, `name`, and a derived `role: Literal["owner", "orga", "participant"]` - `"participant"` covers the case where the only relationship is a `Player`/`CampaignGm` row and no `Membership` exists at all, which [ADR 0022](0022-user-tenant-membership.md) already established as valid, not a gap.

**`GET /tenants/{tenant_id}/campaigns`** is gated by `is_tenant_participant`, not tenant-wide `Membership` alone. The returned page is then filtered per row: included if `not campaign.secret`, **or** the caller holds a `CampaignGm` row for that specific campaign, **or** the caller is `is_tenant_admin`. A plain `Player` of a secret campaign, who isn't also its GM, doesn't see it in this general listing either (see Open questions).

**`GET /tenants/{tenant_id}/campaigns/{campaign_id}` is unaffected by `secret`** - `get_campaign_context` already only admits a player, a GM, or a tenant admin of that specific campaign; `secret` governs whether a campaign appears in the general browse-all list, not whether someone who already has a legitimate way to reach it can open it (same shape as a private GitHub repo).

### Schemas

`schemas/tenants.py`: `TenantSummaryOut(id, slug, name, role)`, `TenantOut(id, slug, name, description)`.
`schemas/campaigns.py`: `CampaignSummaryOut(id, slug, name, game_system, secret)`, `CampaignOut(id, tenant_id, slug, name, description, game_system, secret, created_by, updated_by, created_at, updated_at)`. Neither exposes `entity_id` - it's an internal attachment point, not something a client addresses directly yet.

## Not in scope

**Tenant creation, update, or deletion** - [RFC 0012](../rfcs/0012-tenant-creation-and-update-api.md), not built yet.

**Campaign mutation** (including setting `secret`/`slug`/`description`, or managing the campaign's attached entity's information) - [RFC 0006](../rfcs/0006-campaign-crud-api.md), not built yet.

**Cross-tenant repositories** - still undesigned, unaffected by anything here.

## Open questions

**Should a plain `Player` of a secret campaign (not its GM) see it in the general campaign list too?** As specified above, no - they already know about it directly (it's in their own `/me` response, once [RFC 0004](../rfcs/0004-user-membership-player-character-gm-read-api.md) lands) and can reach its detail directly regardless. Flagged in case that turns out to be surprising in practice; easy to widen later, not assumed now.

**Slug format and collision handling.** Not designed: whether slugs are user-chosen or auto-generated from `name`, whether renaming regenerates it, and what happens on a collision, are real product decisions deferred to [RFC 0012](../rfcs/0012-tenant-creation-and-update-api.md).

## Consequences

- `tenant`/`campaign` gain the columns above; `campaign_access.py` gains `is_tenant_admin`/`is_tenant_participant` and revises `can_access_campaign`'s bypass; `orga_campaign_opt_out` is renamed `tenant_admin_campaign_opt_out`.
- [ADR 0024](0024-campaign-and-player.md) (campaign's original columns), [ADR 0026](0026-campaign-gm-orga-and-access-rule.md) (the opt-out table's original name/scope, `can_access_campaign`'s original ORGA-only bypass), and [ADR 0028](0028-knowledge-and-group-membership.md) (the same ORGA-only bypass, referenced there for `information_visibility.py`'s *unchanged* counterpart) are all superseded in part by this ADR - see the note added to each.
- `docs/architecture/diagrams/domain-model-er.md` updated: new columns on `TENANT`/`CAMPAIGN`, a new `CAMPAIGN ||--|| ENTITY` relation, and the table rename.
- [RFC 0006](../rfcs/0006-campaign-crud-api.md)'s `CampaignCreate`/`CampaignUpdate` will need the four new fields added, and its campaign-delete section will need the explicit-entity-cleanup note above, once it's picked up.

## Addendum: `player`/`campaign_gm` RLS needed the same self-access relaxation `membership` already had

Found empirically while building `GET /tenants`, not anticipated in the RFC: this endpoint unions `Membership`/`Player`/`CampaignGm` with no single tenant in scope, exactly like `GET /me` already needed for `Membership` alone ([ADR 0023](0023-authgear-token-verification.md)'s `8d9ec377f48a` migration). `Player` and `CampaignGm` still had the strict, single-argument `current_setting('app.tenant_id')::uuid` policy - querying either with no `app.tenant_id` set raised (or, on a pooled connection previously used for a real tenant-scoped request, failed a `uuid` cast on `''` rather than `NULL` - the same `NULLIF` gotcha `membership`'s own fix already named).

Fixed identically: `ALTER POLICY tenant_isolation` on both tables to `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid` - the exact same shape, same reasoning, extended to the two tables that turned out to need it too. `campaign` itself keeps the strict policy unchanged (it has no `user_id` column to grant self-access through, and nothing needs cross-tenant campaign access without going through `Player`/`CampaignGm`/`Membership` first).
