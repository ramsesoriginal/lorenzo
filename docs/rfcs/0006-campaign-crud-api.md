# RFC: Campaign CRUD API

Status: proposed — builds on [RFC 0003](0003-tenant-campaign-read-api.md)'s `get_campaign_context`, schema additions, and `is_tenant_admin`, plus [RFC 0005](0005-item-and-item-instance-crud-api.md)'s write-API conventions; no schema changes of this RFC's own, but depends on RFC 0003's migration having landed first

## Context

`campaign` has no REST surface at all yet ([RFC 0003](0003-tenant-campaign-read-api.md) adds read-only); `campaign_gm`/`orga_campaign_opt_out` have never had one either — [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md) built both tables and the access rule itself but says outright "no FastAPI dependency or campaign-scoped route exists yet... matching this vertical slice's own stated scope (data model + auth mechanism first, a fuller REST surface later)." This RFC is that fuller surface, for campaigns specifically.

**Revised after RFC 0003 grew `campaign`'s own schema and access rules.** `campaign` now also has `slug`/`description`/`secret`/`entity_id`, none of which existed when this RFC was first drafted — `CampaignCreate`/`CampaignUpdate` below need them. `can_access_campaign` now admits tenant `OWNER`, not just `ORGA` ([RFC 0003](0003-tenant-campaign-read-api.md)), and `orga_campaign_opt_out` is renamed `tenant_admin_campaign_opt_out` to match — this RFC's own opt-out endpoints and `can_manage_campaign`'s docstring need to follow that rename, below.

Scope boundary, stated up front: this RFC owns the `campaign` resource itself (name, game system) and *who's authorized to run it* (`campaign_gm` grants, `tenant_admin_campaign_opt_out`). It does **not** own the player roster or characters — that's [RFC 0007](0007-user-player-character-crud-api.md). The split mirrors a GitHub repo's own administration model: who can push (collaborators/roles) is a repo-administration concern even though the commits themselves are a separate axis.

## Decision

### `can_manage_campaign` (new, `campaign_access.py`)

```python
async def can_manage_campaign(
    session: AsyncSession, *, user_id: uuid.UUID, campaign_id: uuid.UUID, tenant_id: uuid.UUID
) -> bool:
    """A CampaignGm row, OR tenant-wide OWNER/ORGA - regardless of any
    TenantAdminCampaignOptOut for this campaign (renamed from
    OrgaCampaignOptOut by RFC 0003, once OWNER started sharing the same
    bypass). Deliberately does not reuse
    can_access_campaign wholesale: that predicate is about *play* visibility
    (a tenant admin's opt-out exists so they can play an ordinary character
    without their admin access bleeding in, RFC 0002/RFC 0003) - administrative capability
    over the campaign as an object is a different axis, tied to who can
    administer the tenant at all (ADR 0010: "ownership transfer is just
    changing which membership row has role=owner"), and an opt-out
    shouldn't strip that. A plain player is never a manager."""
```

Every mutation below checks `get_campaign_context` first (404 if the caller has no read access at all, matching the existing non-enumerable pattern), then `can_manage_campaign` for the specific write (`403 CampaignManagementForbiddenError` if read-but-not-manage) — the two-tier 404-then-403 shape [RFC 0005](0005-item-and-item-instance-crud-api.md) established.

### Endpoints

| Method | Path | Auth | Body | Response |
| --- | --- | --- | --- | --- |
| POST | `/tenants/{tenant_id}/campaigns` | `get_tenant_context` (tenant-wide) | `CampaignCreate` | `201 CampaignOut` |
| PATCH | `/tenants/{tenant_id}/campaigns/{campaign_id}` | `get_campaign_context` + `can_manage_campaign` | `CampaignUpdate` | `200 CampaignOut` |
| DELETE | `/tenants/{tenant_id}/campaigns/{campaign_id}` | `get_tenant_context` (tenant-wide only, not `get_campaign_context`) | — (`?force=` query flag) | `204` |
| PUT | `/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}` | `get_campaign_context` + `can_manage_campaign` | — | `200 CampaignOut` |
| DELETE | `/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}` | `get_campaign_context` + (`can_manage_campaign` or self) | — | `200 CampaignOut` |
| PUT | `/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out` | `get_campaign_context`, self only | — | `200 CampaignOut` |
| DELETE | `/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out` | `get_campaign_context`, self only | — | `200 CampaignOut` |

**`POST /campaigns`** — `CampaignCreate{name, game_system, slug, description, secret: bool = false}`. `name`/`game_system` required with no default, matching [ADR 0024](../adr/0024-campaign-and-player.md)'s own reasoning; `slug`/`description` required too, per [RFC 0003](0003-tenant-campaign-read-api.md)'s own no-default choice for `campaign` (no existing fixture call sites to spare, unlike `tenant`); `secret` defaults to `false`, matching that same RFC's column default. **Does not accept `entity_id`** — the campaign's attached `Entity` ([RFC 0003](0003-tenant-campaign-read-api.md)) is created server-side, in the same transaction as the campaign row itself, not supplied by the caller; there's nothing meaningful a client could set on a brand-new, still-empty entity at creation time anyway. Gated by plain `get_tenant_context`, not `can_manage_campaign` — there's no campaign to manage yet, so creating one is squarely the bare-tenant-collection tier from [RFC 0003](0003-tenant-campaign-read-api.md)'s access-gating rule.

**`PATCH /campaigns/{id}`** — `CampaignUpdate{name, game_system, slug, description, secret: bool | None = None}`, all `| None = None`. Changing `game_system` mid-campaign is a real consequence worth naming, not blocking: [ADR 0024](../adr/0024-campaign-and-player.md) makes `game_system` "the natural home for RFC 0001's... which prototype variant a campaign's entities resolve through" — changing it retroactively changes which prototype variants every entity in the campaign resolves through on next read. This RFC doesn't add a confirmation step for that; flagged here so it isn't a silent surprise. Changing `secret` is otherwise unremarkable — it only affects the campaign list's filtering ([RFC 0003](0003-tenant-campaign-read-api.md)), never `get_campaign_context`'s own access decision.

**`DELETE /campaigns/{id}`** requires *more* than `can_manage_campaign` — it's gated by `get_tenant_context` specifically (tenant-wide membership), not `can_manage_campaign`'s broader GM-or-admin set, and deliberately **not** layered under `get_campaign_context` either (an earlier draft's endpoint table wrongly listed both — fixed here). `get_campaign_context` wraps `can_access_campaign`, which a tenant `OWNER`/`ORGA` can suppress for a specific campaign via their own `TenantAdminCampaignOptOut` — exactly so they can play an ordinary character there without spoilers, [RFC 0003](0003-tenant-campaign-read-api.md). Requiring it here would let that same opt-out silently lock its holder out of deleting the campaign, contradicting `can_manage_campaign`'s own explicit "regardless of any `TenantAdminCampaignOptOut`" design a few paragraphs up — deletion is tenant-admin-wide by construction, opt-out or not. The route still loads the `Campaign` row scoped to `tenant_id` to 404 on a nonexistent or foreign `campaign_id` (existence-only, the same non-enumerable shape `get_tenant_or_404` already establishes) — it just doesn't run `can_access_campaign` against it. A GM can rename their own campaign but can't unilaterally destroy it; deletion is a tenant-admin decision. Guarded: `409 CampaignNotEmptyError` if any `Player` or `CampaignGm` row still references this campaign, unless the caller passes `?force=true`, in which case the existing `ON DELETE CASCADE` chain runs as designed. What actually cascades, stated plainly (this is exactly the moment [ADR 0018](../adr/0018-sqlalchemy-modeling-conventions.md)'s own consequences section flagged as needing a revisit — "no tenant-deletion API exists yet... revisit before any real deletion endpoint ships"): every `Player` row for this campaign (cascade), every `CharacterPlayer` link through those players (cascade), every `CampaignGm`/`TenantAdminCampaignOptOut` grant for it (cascade). Any `Being` whose *primary* owner (`owner_player_id`) was one of the deleted players loses that link (`SET NULL`, becomes an NPC per [ADR 0025](../adr/0025-character-being-and-ownership.md)'s existing design) but is **not itself deleted** — roster reuse means it may still be linked into other campaigns via other `character_player` rows, and even if not, a character outliving the campaign it was created in is the correct, existing cascade shape, not a new decision this RFC makes.

**The campaign's attached `Entity` ([RFC 0003](0003-tenant-campaign-read-api.md)) needs explicit cleanup, unconditionally, regardless of `?force=`.** `campaign.entity_id` is `ON DELETE RESTRICT`, so the database won't cascade this for us — and the FK only governs what happens to `campaign` if the *entity* disappears, not the reverse. The correct order is: delete the `campaign` row first (running whichever of the two paths above just cleared it to delete), *then* explicitly delete its now-unreferenced `Entity` row as a second statement in the same transaction — which cascades away any `Information`/`Knowledge` attached to it the same way deleting any other entity does. Getting this order backwards (deleting the entity first) would hit `RESTRICT` and fail outright, since `campaign.entity_id` would still be pointing at it.

**GM grants** — `PUT .../gms/{user_id}` is idempotent (creating a `CampaignGm` row that already exists is a no-op, not a `409`). `DELETE .../gms/{user_id}` allows self-removal in addition to `can_manage_campaign`, mirroring how a collaborator can always leave something they were granted access to. **No last-GM guard**, deliberately contrasted with [RFC 0007](0007-user-player-character-crud-api.md)'s last-owner guard on tenant `Membership`: a campaign with zero GMs is still fully administrable by any tenant-wide member (`Membership` is the only *structurally* single point of tenant administration; campaign GM-ing isn't), so there's no lockout risk to guard against.

**Tenant-admin opt-out** (`admin-opt-out` — renamed from `orga-opt-out` now that [RFC 0003](0003-tenant-campaign-read-api.md) lets `OWNER` share the same bypass, not just `ORGA`) is self-service only — no `user_id` in the path, always the caller. `PUT` requires the caller to currently hold tenant-wide `OWNER` or `ORGA` (`422` if neither — opting out of something that isn't bypassing your visibility in the first place is meaningless, not merely redundant, hence `422` over a silent no-op). `DELETE` (opting back in) has no such precondition; deleting a row that doesn't exist is already a no-op. An owner and an orga opting out of the same campaign are two independent rows (`TenantAdminCampaignOptOut(tenant_id, user_id, campaign_id)`, unchanged shape) — one role's opt-out has no bearing on the other's.

**Attribution ([RFC 0010](0010-created-by-updated-by-attribution.md)):** `POST /campaigns` sets `campaign.created_by`/`updated_by` to `CurrentUser.id`; `PATCH` updates `updated_by`. `PUT .../gms/{user_id}` sets `campaign_gm.created_by` to `CurrentUser.id` — the granter, not the grantee (`user_id` in the path is who's *becoming* GM; `created_by` is who made that happen, the caller) — `created_by` only, since `campaign_gm` has no `updated_by` at all (a grant is never edited, only made or revoked). `PUT .../admin-opt-out` sets `tenant_admin_campaign_opt_out.created_by`, always equal to the caller here, since opting out is inherently self-service — recorded anyway for the same "who, and when" reasoning as the GM grant, not because it could ever differ from the caller.

### Schemas

`schemas/campaigns.py` (already created by [RFC 0003](0003-tenant-campaign-read-api.md)) gains `CampaignCreate`, `CampaignUpdate`. `GmOut` (from [RFC 0004](0004-user-membership-player-character-gm-read-api.md)) is reused as-is for the GM-grant responses' implicit roster — the grant/revoke endpoints themselves return `CampaignOut`, not a GM list, since [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)'s own precedent is that a mutation returns the resource it acted on, and here that's unambiguously the campaign, not its GM roster.

## Not in scope

**Player and character mutation** — [RFC 0007](0007-user-player-character-crud-api.md).

**Campaign archiving as a softer alternative to hard delete.** A worthwhile idea (keep history without the destructive cascade above) but a genuinely new mechanism (a status column, filtering it out of default list views) beyond what's asked here — named as a direction, not designed.

## Open questions

**Should `game_system` changes be blocked, not just flagged, once a campaign has entities relying on system-specific prototypes?** Left as a documented consequence rather than a guard for now — detecting "does this actually matter yet" would need querying every entity's resolved prototype chain, real work not clearly justified until it's caused a real problem.

**Notifying an invited GM.** No notification mechanism exists anywhere in this codebase; granting GM access is silent from the invitee's perspective until they next call `GET /me` ([RFC 0004](0004-user-membership-player-character-gm-read-api.md)) and see it. Out of scope.

## Consequences

- No migration of this RFC's own — but it now depends on [RFC 0003](0003-tenant-campaign-read-api.md)'s migration having landed first (`campaign.slug`/`description`/`secret`/`entity_id`, the `orga_campaign_opt_out` → `tenant_admin_campaign_opt_out` rename) and [RFC 0010](0010-created-by-updated-by-attribution.md)'s (`campaign.created_by`/`updated_by`, `campaign_gm`/`tenant_admin_campaign_opt_out.created_by`), unlike this RFC's first draft, which depended on `campaign`/`campaign_gm`/`orga_campaign_opt_out` needing nothing further.
- `can_manage_campaign` sits alongside `can_access_campaign`/`is_tenant_admin`/`is_tenant_orga`/`is_tenant_participant` in `campaign_access.py` — five related but distinct predicates in one module now, matching [ADR 0028](../adr/0028-knowledge-and-group-membership.md)'s own precedent of extracting a shared `is_tenant_orga` helper rather than duplicating that check.
- `CampaignNotEmptyError`/`CampaignManagementForbiddenError` join `exceptions.py`'s roster, following [RFC 0005](0005-item-and-item-instance-crud-api.md)'s `ConflictProblem`/`ForbiddenProblem` subclassing convention.
- The `?force=true` cascade-confirmation pattern introduced here for campaign deletion is available for reuse anywhere else a guarded, non-trivial cascade delete shows up later (e.g. a future tenant-deletion endpoint, still explicitly out of scope everywhere in this codebase).
