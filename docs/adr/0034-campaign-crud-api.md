# 0034 - Campaign CRUD API

Status: accepted

## Context

`campaign` has had a REST surface since [ADR 0030](0030-tenant-campaign-read-api.md), but read-only; `campaign_gm`/`tenant_admin_campaign_opt_out` have never had one at all - [ADR 0026](0026-campaign-gm-orga-and-access-rule.md) built both tables and the access rule itself but explicitly deferred any route. This ADR accepts [RFC 0006](../rfcs/0006-campaign-crud-api.md), close to verbatim - see it for the full reasoning trail. It owns the `campaign` resource itself (name, game system, ...) and who's authorized to run it (`campaign_gm` grants, `tenant_admin_campaign_opt_out`) - not the player roster or characters, which is [RFC 0007](../rfcs/0007-user-player-character-crud-api.md)'s.

`campaign_access.can_manage_campaign` (a `CampaignGm` row, or tenant-wide `OWNER`/`ORGA`, regardless of any opt-out) already exists - [ADR 0032](0032-item-and-item-instance-crud-api.md) pulled it forward, alongside `can_manage_any_campaign_in_tenant`/`campaign_ids_for_character`/`can_manage_any_of_campaigns`, since item-instance authorization needed it first. This ADR *consumes* that predicate for its own mutations; it does not define it.

## Decision

### Endpoints, all in `routers/campaigns.py`

`POST /tenants/{tenant_id}/campaigns` (`get_tenant_context`, `CampaignCreate{name, game_system, slug, description, secret=false}` -> `201 CampaignOut`), `PATCH .../campaigns/{id}` (`get_campaign_context` + `can_manage_campaign`, `CampaignUpdate` with every field `| None = None` -> `200`), `DELETE .../campaigns/{id}` (`get_tenant_context`, `?force=` -> `204`), `PUT`/`DELETE .../campaigns/{id}/gms/{user_id}` (`get_campaign_context` + `can_manage_campaign`, `DELETE` also allows self-removal -> `200 CampaignOut`), `PUT`/`DELETE .../campaigns/{id}/admin-opt-out` (`get_campaign_context`, self-only -> `200 CampaignOut`).

**`POST`** never accepts `entity_id` - the campaign's dedicated `Entity` ([ADR 0030](0030-tenant-campaign-read-api.md)) is created server-side, same transaction, both stamped `created_by`/`updated_by` = the caller. Gated by plain `get_tenant_context`, not `can_manage_campaign`: there's no campaign yet to manage.

**`PATCH`** applies `model_dump(exclude_unset=True)` over `name`/`game_system`/`slug`/`description`/`secret`, stamping `campaign.updated_by` when anything actually changed. Changing `game_system` retroactively changes which prototype variants every entity in the campaign resolves through - flagged, not blocked (detecting whether it currently matters would mean walking every entity's resolved prototype chain, not clearly worth it yet).

**`DELETE`** is gated by `get_tenant_context` specifically, deliberately *not* `get_campaign_context`: `can_access_campaign`'s own `TenantAdminCampaignOptOut` bypass-suppression must not be able to lock its holder out of deleting a campaign they otherwise administer - `can_manage_campaign` already treats management as "regardless of opt-out," and gating deletion on `get_campaign_context` would silently contradict that. A GM can rename their own campaign but can't unilaterally destroy it. Guarded: `409 CampaignNotEmptyError` if any `Player` or `CampaignGm` row still references the campaign, unless `?force=true`, in which case the existing cascade runs (every `Player`/`CharacterPlayer`/`CampaignGm`/`TenantAdminCampaignOptOut` for it; any `Being` whose *primary* owner was a deleted player loses that link via `SET NULL`, becoming an NPC, but is not itself deleted - roster reuse). The campaign's dedicated `Entity` needs *unconditional*, explicit cleanup regardless of `?force=`: `campaign.entity_id` is `ON DELETE RESTRICT`, so the campaign row is deleted first, then its now-unreferenced `Entity` as a second statement in the same transaction - the reverse order fails outright.

**GM grants**: `PUT` is idempotent (an existing grant is a no-op, not `409`); `created_by` is the granter (the caller), never touched again on re-grant. `DELETE` additionally allows self-removal, mirroring how a collaborator can always leave. No last-GM guard - unlike `Membership`'s structurally-single-point-of-tenant-administration shape, a campaign with zero GMs stays fully administrable by any tenant-wide member.

**Tenant-admin opt-out**: self-service only, no `user_id` in the path. `PUT` requires the caller currently hold tenant-wide `OWNER`/`ORGA` - `422 CampaignAdminOptOutRequiresAdminError`, not a silent no-op, since opting out of a bypass you don't hold is meaningless. `DELETE` has no such precondition (deleting a row that doesn't exist is already a no-op).

### Reused, not reinvented

Every cross-cutting convention comes from [ADR 0032](0032-item-and-item-instance-crud-api.md): `201`/`Location`/canonical-`GET` shape on `POST`, `200`/canonical shape on `PATCH` and the GM/opt-out actions, `204` on `DELETE`; `If-Match`/`check_if_match`/`etag_for` (unmodified - `campaign.updated_at` is a real column, so this just works); `set_tenant_rls_context` re-called after every commit that's followed by a read (every write route here needs it, since every one of them re-reads its own row to build the response); the 404-then-403 two-tier shape (`get_campaign_context` for existence+read-access, `can_manage_campaign`/a dedicated typed error for the write-specific check).

`campaign_gm`/`tenant_admin_campaign_opt_out` gain `created_by` (nullable, `ON DELETE SET NULL`, indexed) and a bare `created_at` - no `updated_by`/`updated_at`, since a grant or opt-out row is only ever made or revoked, never edited in place (nothing for "updated" to mean). New typed problems: `CampaignNotEmptyError` (409, `ConflictProblem`), `CampaignManagementForbiddenError` (403, `ForbiddenProblem`), `CampaignAdminOptOutRequiresAdminError` (422, `UnprocessableProblem`).

## Not in scope

Player and character mutation ([RFC 0007](../rfcs/0007-user-player-character-crud-api.md)). Campaign archiving as a softer alternative to hard delete - named as a direction, not designed.

## Consequences

- One migration: `campaign_gm`/`tenant_admin_campaign_opt_out` gain `created_by`/`created_at`, completing the row in [ADR 0029](0029-attribution-created-by-updated-by.md)'s phased-implementation table (the last two entries in it).
- `can_manage_campaign` and its siblings (`can_manage_any_campaign_in_tenant`, `campaign_ids_for_character`, `can_manage_any_of_campaigns`) are consumed here exactly as [ADR 0032](0032-item-and-item-instance-crud-api.md) left them - this ADR adds no new predicate to `campaign_access.py`.
- The `?force=true` guarded-cascade-delete pattern, already named in [ADR 0032](0032-item-and-item-instance-crud-api.md) as reusable, is now used a second time.
- A tenant admin who opts out of a campaign they have no other standing in (no `Player`/`CampaignGm` row) loses `get_campaign_context` access to it entirely - including, notably, to the `PUT`/`DELETE .../admin-opt-out` routes themselves, since both sit behind `get_campaign_context`. Opting back in via the API is then not possible for that specific edge case (a direct DB fix, or first acquiring a `Player`/`CampaignGm` row, would be the way out). RFC 0006's own endpoint table specifies `get_campaign_context` for both opt-out routes without calling this out; implemented as specified rather than deviated from unasked, but flagged here since it's a real, if narrow, self-lockout path.
