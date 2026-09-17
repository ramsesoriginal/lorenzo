# 0059 - Tenant activity log (first slice)

Status: accepted

## Context

`created_by`/`updated_by` (ADR 0029) exist on most tables, but there's no queryable timeline - a tenant OWNER wondering "who changed this, when" has no answer beyond looking at each row's own attribution one at a time. A genuinely exhaustive audit log (every mutation across every router) is a large undertaking; this is a deliberately narrow first slice, named as such rather than pretending to be complete.

## Decision

New `audit_log(id, tenant_id, actor_id, action, target_type, target_id, detail, created_at)`. `tenant_id` is **not nullable** for this slice - platform-scope events (e.g. account suspension, ADR 0053) are explicitly out of scope, not silently dropped (see below), so there's no NULL case to design around yet. `action`/`target_type` are free text (`"membership.created"`, `"campaign.deleted"`, ...) - the same `Information.type`/`Notification.type` precedent ADR 0017/0054 already established: caller-chosen categorization, not a fixed schema-level discriminant. `actor_id` is `ON DELETE SET NULL`, matching `created_by` everywhere else. RLS is the ordinary `tenant_id = current_setting('app.tenant_id')` shape (no self-access clause needed, unlike `notification` - this is inherently a per-tenant admin view, not a cross-tenant personal inbox).

`GET /tenants/{tenant_id}/activity-log` - `Page[AuditLogEntryOut]`, gated by `get_tenant_context` (any tenant-wide member, the same bar `list_tenant_roster` already uses), newest-first.

A small `record_activity(session, *, tenant_id, actor_id, action, target_type, target_id, detail)` helper (`lorenzo_api/activity_log.py`, core-mechanics-only, no commit - the same shape `lorenzo_api/notifications.py` already uses) is called from exactly these mutation points - chosen as the tenant-admin-relevant "who's allowed to do what" surface, not an attempt at exhaustive coverage:

- `create_membership`/bulk create (ADR 0058), `update_membership`, `delete_membership`
- `create_campaign`, `delete_campaign`
- `grant_campaign_gm`, `revoke_campaign_gm`

## Not in scope

Named explicitly, not hidden: platform-level events (suspend/unsuspend - no `tenant_id` to attach them to under this design); item/character/information mutations; picture uploads; notification sends. If platform-wide audit is wanted later, it needs a nullable `tenant_id` and a dedicated admin read-path (the same RLS-visibility problem ADR 0054 solved for `notification` with its self-access clause - this table doesn't need that complexity yet, since nothing in it is meant to be read cross-tenant).

## Consequences

- New migration + `models/audit_log.py`; `lorenzo_api/activity_log.py`; `schemas/activity_log.py` (`AuditLogEntryOut`); new `routers/activity_log.py` (or added to `routers/tenants.py`), registered in `main.py`; `record_activity` calls added at the seven listed mutation points.
