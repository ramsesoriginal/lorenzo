# RFC: Tenant and campaign read REST API

Status: proposed — read-only extension of the already-accepted domain model ([RFC 0001](0001-core-domain-data-model.md)/[RFC 0002](0002-campaign-player-character-model.md)); no schema changes

## Context

`tenant` and `campaign` have been fully built and migrated since [ADR 0022](../adr/0022-user-tenant-membership.md)/[ADR 0024](../adr/0024-campaign-and-player.md) — but neither has a single REST endpoint. The only routers that exist are `entities`, `items`, `item-instances`, `payloads` (all under `/tenants/{tenant_id}/...`, [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)) and `users` (bare `/me`, [ADR 0023](../adr/0023-authgear-token-verification.md)). [docs/architecture/overview.md](../architecture/overview.md)'s own roadmap names this gap directly: "campaign-scoped REST routes (the access rule itself is built — `campaign_access.can_access_campaign()` — just not wired to a route)."

That access rule is the crux of this RFC, not an afterthought. `get_tenant_context` ([dependencies.py](../../apps/api/src/lorenzo_api/dependencies.py)) — the dependency every existing router uses — requires the caller to hold a tenant-wide `Membership` row (owner/orga). [ADR 0022](../adr/0022-user-tenant-membership.md) says outright that this is deliberately narrow and *already known to be insufficient* the moment a campaign-scoped resource shows up: "a user can perfectly validly have zero `membership` rows and still legitimately access campaigns as an ordinary player... a future campaign-scoped equivalent will need to check the fuller rule once campaign-scoped routes exist — a different, additive check, not a replacement." This RFC is that additive check, and campaign is the first resource that needs it.

## Decision

### Access-gating rule (governs this RFC and every later one)

Two tiers, not one:

- **Bare tenant-level collections** (`/tenants/{tenant_id}/<resource>`, not further nested under a `campaign_id`) stay gated by the existing `get_tenant_context` — unchanged, tenant-wide `Membership` (owner/orga) required. This is the "administer/browse the whole world" tier, and every route built under [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md) already assumes it.
- **Campaign-nested resources** (`/tenants/{tenant_id}/campaigns/{campaign_id}/<resource>`) are gated by a **new** `get_campaign_context` dependency instead, wrapping the already-built [`campaign_access.can_access_campaign`](../../apps/api/src/lorenzo_api/campaign_access.py) (RFC 0002's rule: a `player` row, a `campaign_gm` row, or tenant-orga without an opt-out). An ordinary player has zero `Membership` rows and must still reach their own campaign — this is the fix ADR 0022 named.

This RFC's own two resources split cleanly along that line: the tenant/campaign *collections* (`GET /tenants`, `GET /tenants/{tenant_id}/campaigns`) stay tenant-wide-gated; a single *campaign's* detail is reachable by anyone with a stake in it. [RFC 0004](0004-user-membership-player-character-gm-read-api.md) and every campaign-nested resource in [RFC 0006](0006-campaign-crud-api.md)/[RFC 0007](0007-user-player-character-crud-api.md) reuse `get_campaign_context` rather than redefining it.

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

**Why this doesn't leak more than today**: a caller with no relationship to a tenant at all gets the identical 404 whether the tenant is real, the campaign is real-but-foreign, or the campaign is real-but-inaccessible to them — same class, same body, matching `get_tenant_context`'s own non-enumerable design. The bare tenant/campaign *list* endpoints below stay behind `get_tenant_context` specifically so a zero-access caller never gets a 200-with-empty-page (which would leak "the tenant exists" in a way a flat 404 doesn't) — only single-resource detail lookups use the more permissive `get_tenant_or_404`/`get_campaign_context` pair, where a 404 is already the right response shape for "not for you" regardless of cause.

### Endpoints

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants` | `CurrentUser` only (unscoped, like `/me`) | `Page[TenantSummaryOut]` |
| GET | `/tenants/{tenant_id}` | `get_tenant_context` | `TenantOut` |
| GET | `/tenants/{tenant_id}/campaigns` | `get_tenant_context` (router-level) | `Page[CampaignSummaryOut]`, `?game_system=` filter |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}` | `get_campaign_context` | `CampaignOut` |

**`GET /tenants`** answers "every tenant I belong to in *any* capacity," not just tenant-wide Membership — the same "additive, not narrower" principle as above, applied to discovery. It unions three small id-sets, mirroring `information_visibility.resolve_information_visibility`'s own precedent of several short-circuiting scalar-column queries combined in Python rather than one large SQL `UNION`: tenants with a `Membership` row, tenants with a `Player` row (`Player.tenant_id`, already denormalized per [ADR 0024](../adr/0024-campaign-and-player.md)), and tenants with a `CampaignGm` row (`CampaignGm.tenant_id`, same denormalization, [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)). `TenantSummaryOut` carries `id`, `name`, and a derived `role: Literal["owner", "orga", "participant"]` — `"participant"` covers the case where the only relationship is a `Player`/`CampaignGm` row and no `Membership` exists at all, which is exactly the case ADR 0022 says is valid, not a gap.

**`GET /tenants/{tenant_id}/campaigns`** stays tenant-wide-only, deliberately: browsing the *entire* roster of campaigns in a world (a homebrew setting hosting several unrelated one-shots) is the tenant-admin view this table's existing gate already models correctly. An ordinary player doesn't need this endpoint to find their own campaigns — [RFC 0004](0004-user-membership-player-character-gm-read-api.md)'s extended `/me` is the discovery path for that.

**`GET /tenants/{tenant_id}/campaigns/{campaign_id}`** is reachable by anyone `can_access_campaign` admits. `CampaignOut` is deliberately just `{id, tenant_id, name, game_system, created_at, updated_at}` — no player/GM roster inlined. That's [RFC 0004](0004-user-membership-player-character-gm-read-api.md)'s resource, not this one's; a detail response that changes shape depending on which other RFC happens to exist yet would be the anti-pattern [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md) already rejected once (the owned-by-grouped endpoint discussion) for a different reason but the same principle.

### Schemas

New modules, one per resource, matching the existing `schemas/` layout:

- `schemas/tenants.py`: `TenantSummaryOut(id, name, role)`, `TenantOut(id, name)`.
- `schemas/campaigns.py`: `CampaignSummaryOut(id, name, game_system)`, `CampaignOut(id, tenant_id, name, game_system, created_at, updated_at)`.

Both plain `ConfigDict(from_attributes=True)` mappings — neither needs a reshaping `from_x` classmethod, unlike `ItemOut`/`EntityDetailOut`, since `Tenant`/`Campaign` have no polymorphic or visibility-gated fields.

## Not in scope

**Tenant creation, update, or deletion.** The user's own request scopes CRUD to campaigns, items, and users/players/characters — tenant itself stays read-only here, consistent with [ADR 0022](../adr/0022-user-tenant-membership.md)'s own note that "no create-tenant REST flow exists in this slice" and [ADR 0010](../adr/0010-user-tenant-membership-model.md)'s still-open invitation-flow question. [RFC 0007](0007-user-player-character-crud-api.md) covers *membership* mutation (who's an owner/orga of an existing tenant); a tenant itself coming into existence at all remains undesigned.

**Campaign mutation** — see [RFC 0006](0006-campaign-crud-api.md).

**Cross-tenant repositories** ([docs/domain/repositories.md](../domain/repositories.md)) — still undesigned per both prior RFCs; nothing here assumes a campaign can read from anything outside its own tenant.

## Open questions

**Should tenant `OWNER` implicitly satisfy `can_access_campaign`?** Today's rule ([ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)/[ADR 0028](../adr/0028-knowledge-and-group-membership.md)) deliberately special-cases only `ORGA`, not `OWNER` — carried forward unchanged here, so an owner who is not also orga and holds no player/GM row in a given campaign gets the same 404 an outsider would. That's a real, slightly surprising consequence of reusing an existing, deliberately-scoped predicate rather than a bug this RFC introduces. Revisit if "locked out of a campaign in my own tenant" turns out to be a real usability complaint, not assumed here.

**Should the tenant-wide campaign list (`GET /tenants/{tenant_id}/campaigns`) ever be visible to non-tenant-wide members, filtered to just what they can access, rather than 404ing outright?** Rejected for now in favor of the simpler, single access-rule-per-tier split above; `/me` already covers "which campaigns am I in" without needing this endpoint to do double duty.

## Consequences

- No migration: every table this RFC reads (`tenant`, `campaign`) already exists with RLS in place ([ADR 0013](../adr/0013-tenant-table-bootstrap.md)/[ADR 0022](../adr/0022-user-tenant-membership.md)/[ADR 0024](../adr/0024-campaign-and-player.md)).
- `get_campaign_context` is the dependency [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md) anticipated ("wrapped by a thin `get_campaign_context` FastAPI dependency once a campaign-scoped route exists to need one") — this RFC is that route.
- Every list endpoint here follows the same `apaginate`/`Page[...]`/explicit-`tenant_id`-filter-alongside-RLS pattern as `entities.py`/`items.py` — no new pagination or filtering mechanism.
- `docs/architecture/diagrams/domain-model-er.md` needs no changes (no schema change); `overview.md`'s roadmap line about campaign-scoped routes "not yet built" becomes stale once this lands.
