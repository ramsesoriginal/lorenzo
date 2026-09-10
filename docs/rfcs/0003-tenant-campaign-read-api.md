# RFC: Tenant and campaign read REST API

Status: proposed — extends the domain model itself (new columns on `tenant`/`campaign`, a revised `campaign_access.can_access_campaign`), not just its REST surface; needs a migration and an ER diagram update, unlike this RFC's first draft

## Context

`tenant` and `campaign` exist ([ADR 0013](../adr/0013-tenant-table-bootstrap.md)/[ADR 0022](../adr/0022-user-tenant-membership.md)/[ADR 0024](../adr/0024-campaign-and-player.md)) but neither is complete enough to back a real REST surface, and neither has any REST surface at all yet. [docs/architecture/overview.md](../architecture/overview.md)'s own roadmap names the missing REST surface directly; revising this RFC found real schema gaps too. `tenant` is just `{id, name}` — no URL-friendly identifier for frontend clients to link to, no description. `campaign` is `{id, tenant_id, name, game_system}` — same two gaps, plus no way to mark a campaign as secret (hidden from casual browsing) and no attachment point for richer information (GM notes, images) beyond its own bare columns.

Access needed a real answer too, not just the read-only surface this RFC first scoped. `get_tenant_context` requires tenant-wide `Membership`, which ordinary players/GMs legitimately never have ([ADR 0022](../adr/0022-user-tenant-membership.md)) — this RFC's first draft used that to justify keeping the campaign list tenant-wide-admin-only, reasoning that an ordinary participant doesn't need to browse every campaign in the tenant. Revised: an ordinary tenant participant *should* be able to browse the tenant's campaign catalog, just with secret campaigns filtered out unless they're that campaign's own GM or a tenant admin. Separately, `campaign_access.can_access_campaign` ([ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)) special-cased only `ORGA`, not `OWNER` — this RFC's first draft left that asymmetry as an open question; it's resolved now, in favor of `OWNER` getting the same bypass.

## Decision

### Schema additions

All new columns/relations on tables that already exist — no new concrete type, no change to the entity/component core itself.

- **`tenant.slug`** — `TEXT NOT NULL`, globally `UNIQUE` (tenants aren't nested under anything, so nothing narrower to scope uniqueness by). URL-safe, for frontend routing (`/t/{slug}/...`-shaped links) instead of a bare UUID.
- **`tenant.description`** — `TEXT NOT NULL`, server-defaulted to `''` the same pragmatic way `tenant.name` got a server default in [ADR 0022](../adr/0022-user-tenant-membership.md) (no real tenant data predates this, but the same reasoning — don't force every existing fixture call site to supply a value it doesn't care about — still applies). A plain column, not an attached `Information` row: `Tenant` isn't gaining an entity attachment (that's `campaign`'s own addition, below, asked for specifically there), so it stays consistent with `name`'s existing plain-column shape rather than introducing a second mechanism just for tenant.
- **`campaign.slug`** — `TEXT NOT NULL`, `UNIQUE(tenant_id, slug)` — scoped to the tenant, matching `stat_group`/`stat_definition`'s existing `UNIQUE(tenant_id, name)` precedent, not globally unique: two unrelated tenants both running a campaign called "the-ashen-crown" isn't a conflict the way two tenants sharing a slug would be.
- **`campaign.description`** — `TEXT NOT NULL`, no server default. Unlike `tenant`, `campaign` has no existing fixture call sites to avoid retrofitting — every caller can and should supply one from the start, matching [ADR 0024](../adr/0024-campaign-and-player.md)'s own reasoning for why `campaign.game_system` has no default either.
- **`campaign.secret`** — `BOOLEAN NOT NULL DEFAULT false`. Defaults to visible: the exceptional case is hiding a campaign from the tenant's general roster (a surprise one-shot, a GM's parallel secret storyline), not the reverse — matching this domain's own framing of "a homebrew world hosting both a long campaign and an unrelated one-shot" as the normal, expected shape, where both are ordinarily just as visible. Governs the *list* endpoint's filtering only (below) — it is not an access-control flag and doesn't change what `get_campaign_context` admits.
- **`campaign.entity_id`** — `UUID NOT NULL`, FK to `entity.id`, `ON DELETE RESTRICT`. A dedicated `Entity` row created in the same transaction as the campaign itself — **not** a class-table-inheritance PK+FK the way `item`/`being` extend `entity`. `campaign` keeps its own existing surrogate `id`; this is a plain reference column instead, so `campaign_gm`/`player`/`orga_campaign_opt_out`/`character_player`'s existing FKs to `campaign.id` are entirely unaffected. Purpose: attaching `Information`/`Knowledge` to a campaign the same generic way any other entity gets richer content — GM notes about the campaign itself, images, whatever a future need asks for — without inventing a campaign-specific mechanism. `ON DELETE RESTRICT` covers only the unusual case of someone deleting the anchor `Entity` directly, out of band; deleting the *campaign* itself must explicitly delete its linked `Entity` too, since a FK's `ON DELETE` clause only governs the referencing row when the referenced row disappears, not the reverse. [RFC 0006](0006-campaign-crud-api.md)'s campaign-delete section needs a follow-up note once this lands.

### Access-gating rule (governs this RFC and every later one)

Two tiers, not one:

- **Bare tenant-level collections** (`/tenants/{tenant_id}/<resource>`, not further nested under a specific `campaign_id`) stay gated by the existing `get_tenant_context` — unchanged, tenant-wide `Membership` (owner/orga) required. This is the "administer/browse the whole world" tier, and every route built under [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md) already assumes it.
- **Campaign-nested resources** (`/tenants/{tenant_id}/campaigns/{campaign_id}/...`) are gated by a **new** `get_campaign_context` dependency instead, wrapping the already-built [`campaign_access.can_access_campaign`](../../apps/api/src/lorenzo_api/campaign_access.py) (RFC 0002's rule: a `player` row, a `campaign_gm` row, or tenant-orga without an opt-out). An ordinary player has zero `Membership` rows and must still reach their own campaign — this is the fix ADR 0022 named.

The campaign *list* endpoint is a deliberate, documented exception to the first bullet — see below.

### `get_tenant_or_404` and `get_campaign_context` (new, `dependencies.py`)

```python
async def get_tenant_or_404(tenant_id: uuid.UUID, session: SessionDep) -> uuid.UUID:
    """Existence-only - no Membership check. Still sets app.tenant_id: which
    RLS partition a query runs against is a scoping decision, not an
    authorization one - that's get_campaign_context's job, layered on top."""

async def get_campaign_context(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> uuid.UUID:
    """Tenant must exist (get_tenant_or_404), campaign must exist and belong
    to that tenant, and can_access_campaign(...) must be true - all three
    failures raise the *same* CampaignNotFoundError, extending
    get_tenant_context's existing "can't distinguish doesn't-exist from
    not-a-member" rule (ADR 0023) from two cases to three. Returns just
    campaign_id, mirroring get_tenant_context's own return shape - routes
    needing the full Campaign row re-query with their own eager-load chain,
    the same division of labor entities.py's get_entity already uses
    relative to get_entity_or_404."""
```

`CampaignNotFoundError(NotFoundProblem)`, title "Campaign not found" — joins `exceptions.py`'s existing one-class-per-condition roster.

**Why this doesn't leak more than today**: a caller with no relationship to a tenant at all gets the identical 404 whether the tenant is real, the campaign is real-but-foreign, or the campaign is real-but-inaccessible to them — same class, same body, matching `get_tenant_context`'s own non-enumerable design.

### `campaign_access.can_access_campaign` now admits `OWNER`, via a new `is_tenant_admin`

Revises [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)/[ADR 0028](../adr/0028-knowledge-and-group-membership.md): `can_access_campaign` checked `is_tenant_orga` (role `== ORGA` specifically) for its blanket-bypass branch; it now checks a new `is_tenant_admin(session, *, tenant_id, user_id) -> bool` (role `in (OWNER, ORGA)`) instead. **This is deliberately narrower in effect than it sounds** — it only widens *campaign-resource reachability* (can this user `GET` this campaign at all), not *information visibility* (which secrets they see once inside it): [information_visibility.py](../../apps/api/src/lorenzo_api/information_visibility.py)'s `is_orga` keeps checking `is_tenant_orga` (`ORGA` only) unchanged, per [RFC 0009](0009-campaign-scoped-gm-visibility.md)'s just-confirmed "administrative access != automatic character/GM knowledge" principle. An `OWNER` can now reach a campaign's metadata and roster the same way `ORGA` already could; they still see no more of its GM-only secrets than a plain participant would, exactly as before.

The opt-out mechanism widens symmetrically: `orga_campaign_opt_out` is renamed `tenant_admin_campaign_opt_out` (same shape — `tenant_id, user_id, campaign_id`, a row's mere existence is the opt-out) and now applies to whichever of `OWNER`/`ORGA` the caller holds, not just `ORGA` — an owner who wants to just play an ordinary character in one campaign can suppress their own admin-bypass for it exactly the way an orga already could.

### Endpoints

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants` | `CurrentUser` only (unscoped, like `/me`) | `Page[TenantSummaryOut]` |
| GET | `/tenants/{tenant_id}` | `get_tenant_context` | `TenantOut` |
| GET | `/tenants/{tenant_id}/campaigns` | `get_tenant_or_404` + `is_tenant_participant` | `Page[CampaignSummaryOut]`, filtered by secrecy |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}` | `get_campaign_context` | `CampaignOut` |

**`GET /tenants`** answers "every tenant I belong to in *any* capacity," not just tenant-wide Membership. It unions three small id-sets, mirroring `information_visibility.resolve_information_visibility`'s own precedent of several short-circuiting scalar-column queries combined in Python rather than one large SQL `UNION`: tenants with a `Membership` row, tenants with a `Player` row (`Player.tenant_id`, already denormalized per [ADR 0024](../adr/0024-campaign-and-player.md)), and tenants with a `CampaignGm` row (`CampaignGm.tenant_id`, same denormalization, [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)). `TenantSummaryOut` carries `id`, `slug`, `name`, and a derived `role: Literal["owner", "orga", "participant"]` — `"participant"` covers the case where the only relationship is a `Player`/`CampaignGm` row and no `Membership` exists at all, which is exactly the case ADR 0022 says is valid, not a gap.

**`GET /tenants/{tenant_id}/campaigns`, revised — no longer tenant-wide-Membership-only.** Gated instead by a new `is_tenant_participant(session, *, tenant_id, user_id) -> bool`: a `Membership` row (any role), **or** any `Player` row, **or** any `CampaignGm` row, anywhere in the tenant (three short-circuiting existence checks, the same shape as `can_access_campaign` itself) — 404 (`TenantNotFoundError`, matching the non-enumerable pattern) for a caller with none of the three. This is the same concept [RFC 0005](0005-item-and-item-instance-crud-api.md) independently named for item-instance write authorization; that RFC should point back here once both land, rather than keep its own separate definition.

The returned page is then filtered per row, not just gated once for the whole call: a `Campaign` is included if `not campaign.secret`, **or** the caller holds a `CampaignGm` row for that specific campaign, **or** the caller is `is_tenant_admin` (`OWNER`/`ORGA`). Note precisely what this does *not* include: a plain `Player` of a secret campaign, who isn't also its GM, doesn't see it in this general listing either — see Open questions.

**`GET /tenants/{tenant_id}/campaigns/{campaign_id}` is unaffected by `secret`.** `get_campaign_context` already only admits a player, a GM, or a tenant admin of that specific campaign — `secret` governs whether a campaign appears in the general browse-all list, not whether someone who already has a legitimate way to reach it (a direct link, their own player/GM role) can open it. Same shape as a private GitHub repo: invisible when browsing, still reachable by anyone actually granted access.

### Schemas, revised

`schemas/tenants.py`: `TenantSummaryOut(id, slug, name, role)`, `TenantOut(id, slug, name, description)`.
`schemas/campaigns.py`: `CampaignSummaryOut(id, slug, name, game_system, secret)`, `CampaignOut(id, tenant_id, slug, name, description, game_system, secret, created_at, updated_at)`. Neither exposes `entity_id` — it's an internal attachment point for `Information`/`Knowledge`, not something a client addresses directly yet; a future RFC can expose "get a campaign's attached information" the same way `GET /entities/{id}` already does for any other entity, once there's an actual need for GM notes/images on a campaign specifically.

## Not in scope

**Tenant creation, update, or deletion.** A future create-tenant flow will need to populate `slug`/`description`/`name` and provision the initial `OWNER` `Membership` together; not designed here.

**Campaign mutation** (including setting `secret`/`slug`/`description`, or managing the campaign's attached entity's information) — [RFC 0006](0006-campaign-crud-api.md), which needs a follow-up pass now that `campaign` has four new columns plus an attached entity it didn't have when that RFC was written.

**Cross-tenant repositories** — still undesigned, unaffected by anything here.

## Open questions

**Should a plain `Player` of a secret campaign (not its GM) see it in the general campaign list too?** As specified above, no — they already know about it directly (it's in their own `/me` response, [RFC 0004](0004-user-membership-player-character-gm-read-api.md)) and can reach its detail directly regardless. Flagging this precisely in case that turns out to be surprising in practice; easy to widen later, not assumed now.

**Slug format and collision handling.** Not designed: whether slugs are user-chosen or auto-generated from `name`, whether renaming a tenant/campaign changes its slug (breaking old links) or leaves it pinned, and what happens on a collision (append a suffix? reject?) are all real product decisions this RFC doesn't make.

**Should a campaign's attached entity ever acquire stats/prototypes of its own** (the same mechanisms `item`/`being` use) — a campaign-level custom stat block, say? Nothing asks for this yet; the attachment exists for `Information`/`Knowledge` specifically, per the stated purpose above, not as a general invitation to treat `campaign` like `item`/`being`.

## Consequences

- **This RFC now needs a migration**, unlike its first draft: `tenant` gains `slug`/`description`; `campaign` gains `slug`/`description`/`secret`/`entity_id` (plus creating one new `Entity` row per existing campaign at migration time — trivial pre-release, since no real campaign data exists yet); `campaign_access.py` changes `can_access_campaign`'s bypass check and gains `is_tenant_admin`/`is_tenant_participant`; `orga_campaign_opt_out` is renamed `tenant_admin_campaign_opt_out`. [ADR 0024](../adr/0024-campaign-and-player.md) (campaign's original columns), [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md) (the opt-out table's original name/scope), and [ADR 0028](../adr/0028-knowledge-and-group-membership.md) (the `ORGA`-only bypass this revises) all need superseding notes once this becomes an ADR.
- **`docs/architecture/diagrams/domain-model-er.md` needs a real update**, not just a refresh — new columns on `TENANT`/`CAMPAIGN`, a new `CAMPAIGN ||--|| ENTITY` relation, and the `orga_campaign_opt_out` → `tenant_admin_campaign_opt_out` rename all need to show up there once this is built. Not done as part of this RFC — that's the ER-diagram step of the usual ADR → ER → migration → code+tests slice process, once this RFC is actually picked up for implementation.
- `is_tenant_participant` (new) and `is_tenant_admin` (new) join `campaign_access.py` alongside the already-existing `is_tenant_orga`/`can_access_campaign` — four related predicates in one module now, still consistent with that module's existing "plain, directly-testable, no HTTP concerns" convention.
- [RFC 0006](0006-campaign-crud-api.md)'s `CampaignCreate`/`CampaignUpdate` need the four new fields added, and its campaign-delete section needs the explicit-entity-cleanup note above — flagged, not fixed here, to keep this revision scoped to RFC 0003 itself.
