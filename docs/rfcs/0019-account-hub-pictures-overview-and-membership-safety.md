# RFC: `apps/account-hub` — pictures, notification awareness, cross-tenant overview, and membership safety

Status: proposed

## Context

A backlog review of `apps/account-hub` after RFC 0017 landed turned up five gaps, spanning GM/player/tenant-admin personas plus general navigation. As with every account-hub RFC before it, most of this is already-built, already-authorized `apps/api` surface - checked against the current routers/schemas below, not assumed:

- Tenant and campaign profile pictures (`PUT`/`DELETE /tenants/{id}/picture`, `.../campaigns/{id}/picture`) have existed since [ADR 0056](../adr/0056-profile-pictures.md); account-hub only ever built the UI for the caller's own picture (`/me/picture`, `src/lib/profile.ts`).
- `GET /me/notifications` already accepts `unread_only=true` and returns a paginated `Page[NotificationOut]` whose `total` is a cheap unread count on its own - no new endpoint needed for a nav badge.
- `GET /me` (`MeOut`) already returns `memberships[]`, `players[]` (each carrying its own campaign context), and `campaign_gm_grants[]` in one call - everything a cross-tenant/cross-campaign overview needs already comes back from a single request account-hub already makes; it's just never been aggregated into one screen.
- `DELETE /tenants/{id}/memberships/{user_id}` already exists (tenant OWNER, or removing your own membership), already writes an audit-log entry (`membership.deleted`, [ADR 0063](../adr/0063-tenant-activity-log.md)), and is already wired into account-hub's `membershipAdminUi.ts` ([ADR 0082](../adr/0082-account-hub-tenant-creation-and-membership-admin.md)). What's actually missing is notifying the removed person - checked directly against `feat/api-tenant-accountability-docs` (unmerged as of this writing), which already has a drafted ADR 0084 for exactly this: `membership.deleted` gains a `detail` (`"removed"` vs `"left"`, plus role), and removal always fires a `scope="tenant"`, `type="tenant_membership_removed"` notification to the removed user, in the same transaction as the delete.
- That same drafted ADR 0084 also narrows `GET /tenants/{id}/activity-log` from "any tenant-wide member" to **OWNER/ORGA only** - a breaking change for account-hub's existing activity-log panel (ADR 0083), which was built on the old, wider gate. ADR 0084's own text says this client-side fix "lands with the implementation... in the account-hub client," which may mean that branch intends to touch this app's code directly - flagged to the user below rather than assumed either way, since two sessions independently patching the same account-hub file is worth avoiding.
- Self-serve tenant-data export has no `apps/api` surface at all yet, and no evidence of it in any branch checked so far - also deferred, not something to guess the shape of here.

## Decision

Five sub-slices, ordered least-blocked first. The two items waiting on parallel `apps/api` work are named and scoped here so they aren't lost, not designed in detail - guessing at an API shape someone else is actively deciding would only need redoing.

### 1. Tenant and campaign picture upload/display

The same `PUT`/`DELETE .../picture` pattern RFC 0013's profile slice already built for `/me/picture`, reusing the same generic `apiUpload`/`apiDelete` helpers already in `src/lib/api.ts` - new thin wrappers in `src/lib/tenants.ts` (`uploadTenantPicture`/`deleteTenantPicture`, `uploadCampaignPicture`/`deleteCampaignPicture`), not a shared cross-scope picture module, matching this app's established one-wrapper-per-endpoint convention. Shown on `/tenants`: a tenant's own picture gated `owner`/`orga` (same as the rest of that page's tenant-admin actions); a campaign's picture gated by the same `can_manage_campaign` check the GM/invite panel already uses for that campaign row.

### 2. Unread-notification indicator outside the inbox

A small badge in the shared nav (`layouts/Base.astro`), polled on the same cadence `/notifications` already polls at (RFC 0013's existing freshness loop - one shared timer, not a second one). Backed by `GET /me/notifications?unread_only=true&size=1`, reading `Page.total` - no new `apps/api` surface, and no full-list fetch just to produce a count.

### 3. Cross-tenant/cross-campaign access overview

A new read-only view listing every campaign the caller owns, GMs, or plays in, across every tenant, on one screen - sourced entirely from `GET /me`'s existing `memberships[]`/`players[]`/`campaign_gm_grants[]`, the same data `/tenants` and `/characters` already each aggregate their own slice of, just not combined into one cross-tenant list before now. Deliberately scoped to **roles and membership state only** - no campaign content, no roster detail beyond what `/tenants`'s own per-tenant view already shows - this is a navigation aid, not a new data surface. Exact placement (a new `/overview` page vs. a section on an existing one) is left to the implementing ADR.

### 4. Membership removal: notify the removed person, and handle the tightened activity-log gate (blocked on `apps/api`)

The UI (remove button, confirmation step) and the audit trail already exist (ADR 0082/0063) - this slice does not redo either. Per the drafted (unmerged) ADR 0084, the notification fires automatically inside `delete_membership` itself, the same way `tenant_invite` already does - so once that lands, this app's own inbox rendering (already generic over `type`/`title`/`body`) needs no change at all for the notification itself. What this app *does* need once ADR 0084 merges: the activity-log panel (ADR 0083) must handle a `403` gracefully (hide the panel for a non-owner/orga viewer, rather than an unhandled error) now that the read gate narrows to OWNER/ORGA. Confirm at merge time whether the other branch already made that client-side change itself, before duplicating it.

### 5. Self-serve tenant-data export (blocked on `apps/api`)

No `apps/api` surface exists yet. Entirely deferred; this RFC only records that account-hub wants a page for it once one exists. The page's own shape - a single synchronous download vs. an async job plus a "your export is ready" notification, given the notification infrastructure already exists - is an open question for whoever designs the `apps/api` side, not pre-guessed here.

## Consequences

- Sub-slices 1-3 have no `apps/api` dependency and can be built and merged independently of the parallel work in progress - each gets its own ADR as it's actually built, smallest first, same cadence as RFC 0013/0014/0017.
- Sub-slices 4-5 stay explicitly parked - named so they aren't lost, not designed further - until the parallel `apps/api` work they depend on is reviewable.
- No `apps/api` change is requested by this RFC: sub-slices 1-3 need only surface that already exists and is already correctly authorized; sub-slices 4-5 depend on `apps/api` work already owned and in progress elsewhere, not proposed here.
