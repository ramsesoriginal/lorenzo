# RFC: `apps/account-hub` — pictures, notification awareness, cross-tenant overview, and membership safety

Status: proposed

## Context

A backlog review of `apps/account-hub` after RFC 0017 landed turned up five gaps, spanning GM/player/tenant-admin personas plus general navigation. As with every account-hub RFC before it, most of this is already-built, already-authorized `apps/api` surface - checked against the current routers/schemas below, not assumed:

- Tenant and campaign profile pictures (`PUT`/`DELETE /tenants/{id}/picture`, `.../campaigns/{id}/picture`) have existed since [ADR 0056](../adr/0056-profile-pictures.md); account-hub only ever built the UI for the caller's own picture (`/me/picture`, `src/lib/profile.ts`).
- `GET /me/notifications` already accepts `unread_only=true` and returns a paginated `Page[NotificationOut]` whose `total` is a cheap unread count on its own - no new endpoint needed for a nav badge.
- `GET /me` (`MeOut`) already returns `memberships[]`, `players[]` (each carrying its own campaign context), and `campaign_gm_grants[]` in one call - everything a cross-tenant/cross-campaign overview needs already comes back from a single request account-hub already makes; it's just never been aggregated into one screen.
- `DELETE /tenants/{id}/memberships/{user_id}` already exists (tenant OWNER, or removing your own membership), already writes an audit-log entry (`membership.deleted`, [ADR 0063](../adr/0063-tenant-activity-log.md)), and is already wired into account-hub's `membershipAdminUi.ts` ([ADR 0082](../adr/0082-account-hub-tenant-creation-and-membership-admin.md)). What's actually missing is notifying the removed person - checked directly against `feat/api-tenant-accountability-docs` (unmerged as of this writing), which already has a drafted ADR 0084 for exactly this: `membership.deleted` gains a `detail` (`"removed"` vs `"left"`, plus role), and removal always fires a `scope="tenant"`, `type="tenant_membership_removed"` notification to the removed user, in the same transaction as the delete.
- **Correction, checked against ADR 0084's current revision**: an earlier draft of that ADR called the activity-log read gate a breaking narrowing to OWNER/ORGA-only; it isn't. `GET /tenants/{id}/activity-log` (and `GET /tenants/{id}/memberships`, the roster read) are both gated by `get_tenant_context`, which requires a real `Membership` row - and `MembershipRole` only has `OWNER`/`ORGA`. No third, "plain member" role exists, so this gate has *always* been administrators-only; ADR 0084 documents that fact rather than changing it. Checking this surfaced a real, **pre-existing, independent bug** in account-hub's own already-shipped code: `tenants.astro`'s `renderTenant` calls `listTenantRoster`/`renderActivityLog` unconditionally for every tenant `listMyTenants()` returns, including ones where the caller has only campaign-level standing (a `Player`/`CampaignGm` row, no tenant-wide `Membership`) - such a caller already gets a 404 from both endpoints today, uncaught, which fails `/tenants`'s entire `load()` for them. Unrelated to whether ADR 0084 merges; fixed separately (see below).
- Self-serve tenant-data export: checked directly against `feat/api-tenant-accountability-docs`'s own drafted ADR (tenant-data-export-audit-and-runbook, unmerged) - there is no plan for a single "export my tenant" archive endpoint. Instead: three small new read endpoints (`GET /tenants/{id}/stat-groups`, `.../stat-definitions`, and an OWNER/ORGA-only, ids-only `.../knowledge`) close the last real discoverability gaps, and a documented runbook (`docs/operations/exporting-your-tenant.md`) walks an owner through every existing (plus these new) read endpoint by hand. No bundling/archive/async-job mechanism is planned on the `apps/api` side.

## Decision

Five sub-slices, ordered least-blocked first. The two items waiting on parallel `apps/api` work are named and scoped here so they aren't lost, not designed in detail - guessing at an API shape someone else is actively deciding would only need redoing.

### 1. Tenant and campaign picture upload/display

The same `PUT`/`DELETE .../picture` pattern RFC 0013's profile slice already built for `/me/picture`, reusing the same generic `apiUpload`/`apiDelete` helpers already in `src/lib/api.ts` - new thin wrappers in `src/lib/tenants.ts` (`uploadTenantPicture`/`deleteTenantPicture`, `uploadCampaignPicture`/`deleteCampaignPicture`), not a shared cross-scope picture module, matching this app's established one-wrapper-per-endpoint convention. Shown on `/tenants`: a tenant's own picture gated `owner`/`orga` (same as the rest of that page's tenant-admin actions); a campaign's picture gated by the same `can_manage_campaign` check the GM/invite panel already uses for that campaign row.

### 2. Unread-notification indicator outside the inbox

A small badge in the shared nav (`layouts/Base.astro`), polled on the same cadence `/notifications` already polls at (RFC 0013's existing freshness loop - one shared timer, not a second one). Backed by `GET /me/notifications?unread_only=true&size=1`, reading `Page.total` - no new `apps/api` surface, and no full-list fetch just to produce a count.

### 3. Cross-tenant/cross-campaign access overview

A new read-only view listing every campaign the caller owns, GMs, or plays in, across every tenant, on one screen - sourced entirely from `GET /me`'s existing `memberships[]`/`players[]`/`campaign_gm_grants[]`, the same data `/tenants` and `/characters` already each aggregate their own slice of, just not combined into one cross-tenant list before now. Deliberately scoped to **roles and membership state only** - no campaign content, no roster detail beyond what `/tenants`'s own per-tenant view already shows - this is a navigation aid, not a new data surface. Exact placement (a new `/overview` page vs. a section on an existing one) is left to the implementing ADR.

### 4. Membership removal: notify the removed person (blocked on `apps/api`; a real, unrelated bug fixed alongside)

The UI (remove button, confirmation step) and the audit trail already exist (ADR 0082/0063) - this slice does not redo either. Per the drafted (unmerged) ADR 0084, the notification fires automatically inside `delete_membership` itself, the same way `tenant_invite` already does - once that lands, this app's own inbox rendering (already generic over `type`/`title`/`body`) needs **no client change at all** for the notification itself; there is no gate change to react to either (see the corrected Context above). The one real, actionable item here is independent of ADR 0084 merging: `tenants.astro` must stop calling `listTenantRoster`/`renderActivityLog` for a tenant the caller only has campaign-level standing in, since both already 404 for that caller today - fixed as its own small bugfix, not gated on the parallel work landing.

### 5. Self-serve tenant-data export (blocked on `apps/api`)

Per the drafted (unmerged) ADR on `feat/api-tenant-accountability-docs`, there will be no single download endpoint to call - the design is a handful of small new read endpoints plus a human-readable runbook describing how to walk every tenant-scoped read to reconstruct a full export.

**Decided (2026-09-20): documentation-only for now.** A page (or a section of an existing one) that simply links to/renders the runbook, telling an owner how to export their own data via API calls (e.g. with `curl`/a script) - no new client code beyond a static page, matching this app's established minimalism. The client-assisted alternative (a page that actually walks the documented reads itself and offers a downloadable JSON bundle) is explicitly deferred, not rejected - real, buildable client work once there's a concrete need for it, not designed here.

Left open for the user to pick once the `apps/api` side is actually reviewable; recorded here so the choice isn't made silently mid-implementation.

## Consequences

- Sub-slices 1-3 have no `apps/api` dependency and can be built and merged independently of the parallel work in progress - each gets its own ADR as it's actually built, smallest first, same cadence as RFC 0013/0014/0017.
- Sub-slices 4-5 stay explicitly parked - named so they aren't lost, not designed further - until the parallel `apps/api` work they depend on is reviewable, except for the one real bugfix named in sub-slice 4.
- No `apps/api` change is requested by this RFC: sub-slices 1-3 need only surface that already exists and is already correctly authorized; sub-slices 4-5 depend on `apps/api` work already owned and in progress elsewhere, not proposed here.
- **Number collision, found and partly resolved while writing this note**: `feat/api-tenant-accountability-docs` ([PR #113](https://github.com/ramsesoriginal/lorenzo/pull/113)) independently claimed both this RFC's number (its own `docs/rfcs/0019-shareable-campaign-invite-links.md`, unrelated topic) and this RFC's implementing ADR's number (its own `docs/adr/0085-tenant-data-export-audit-and-runbook.md`) while both were in flight. By commit timestamp, this RFC's own `0019` was claimed first (2026-09-19 16:39 UTC+2 vs. their 22:22) and keeps its number; their ADR `0085` was claimed first (22:22 vs. this RFC's implementing ADR at 22:48), so this RFC's own ADR renumbered to **ADR 0087** rather than waiting for a merge-time collision, per this project's own established precedent (ADR 0050/0054/0068/0069). `feat/api-tenant-accountability-docs`'s own RFC `0019` still needs the same treatment on its side - not done here, since that branch isn't this session's to edit.
