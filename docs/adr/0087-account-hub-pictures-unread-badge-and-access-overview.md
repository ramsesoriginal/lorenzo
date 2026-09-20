# 0087 - account-hub: tenant/campaign pictures, an unread-notification badge, and a cross-tenant access overview

Status: accepted

_Originally numbered 0085; renumbered before merge - `feat/api-tenant-accountability-docs` ([PR #113](https://github.com/ramsesoriginal/lorenzo/pull/113)) independently claimed 0085 first (by commit timestamp) for its own tenant-data-export ADR. Same precedent as ADR 0050/0054/0068/0069._

## Context

[RFC 0019](../rfcs/0019-account-hub-pictures-overview-and-membership-safety.md)'s three sub-slices with no `apps/api` dependency (1-3). Checked directly against this app's current source, not just against the RFC's own framing - two of its assumptions needed correcting once checked:

- **There is no shared nav.** `layouts/Base.astro` is just a header/logo shell; `src/pages/index.astro` is the actual navigation hub - a plain post-login list of links (`/profile`, `/notifications`, `/tenants`, `/characters`, `/beings`, `/debug/me`). RFC 0019's "a badge in the shared nav" means `index.astro`'s existing `<a href="/notifications">` link, not `Base.astro`.
- **`GET /me` alone is not enough for the access overview.** `MembershipOut` carries only `tenant_id`/`role` (no tenant name); `PlayerContextOut` carries only `tenant_id`/`campaign_id` (no campaign name); `campaign_gm_grants[]`'s `CampaignSummaryOut` has a campaign name but no `tenant_id` to group it by. `/tenants` itself doesn't get its display names from `GET /me` either - it calls `listMyTenants()` (`GET /tenants`, every tenant the caller reaches via Membership/Player/CampaignGm, per ADR 0030) plus `listTenantCampaigns(tenantId)` per tenant, then classifies each campaign's role client-side via `campaignRoleFor`. The overview page needs that same pair of calls, not a single `GET /me` read.
- `TenantSummaryOut`/`CampaignSummaryOut`/`CampaignOut` carry no `picture_url` field server-side, unlike `MeOut` (ADR 0056/0060) - the client must construct the picture URL itself from `API_BASE_URL`. `GET /tenants/{id}/picture` and `GET /tenants/{id}/campaigns/{id}/picture` have no Gravatar-style fallback (ADR 0056) - a 404 when nothing's uploaded, so display needs an `onerror` handler, not a bare `<img src>`.

## Decision

### 1. Tenant and campaign picture upload/display

New `src/lib/pictureUi.ts`, `renderPictureUpload(url, onUpload, onDelete)`: builds an `<img>` (pointed at the constructed picture URL, `onerror` hides it rather than showing a broken-image icon), a file input, and a remove button, wired to the two passed callbacks - one small widget, reused by both new call sites below rather than written twice (`userPicker.ts`, ADR 0074, is this app's precedent for a shared `lib/*.ts` DOM-building module).

`src/lib/tenants.ts` gains `uploadTenantPicture`/`deleteTenantPicture`/`uploadCampaignPicture`/`deleteCampaignPicture` - thin `apiUpload`/`apiDelete` wrappers against `PUT`/`DELETE /tenants/{id}/picture` and `.../campaigns/{id}/picture`, mirroring `profile.ts`'s existing `/me/picture` pair exactly.

`tenants.astro`: `renderTenant` shows the tenant's own picture widget next to the existing role badge, gated `owner`/`orga` (`isTenantAdmin`, the same gate `upload_tenant_picture` itself enforces). `renderCampaign` shows a campaign's own picture widget gated by the same `admin || role === 'gm'` check already used on that row for invite-player/notification-composer (`can_manage_campaign`, matching `upload_campaign_picture`'s real gate).

`/me/picture` (`profile.astro`) is untouched - it already works off `MeOut.picture_url`, a different (simpler) shape than the two new call sites need, and refactoring working code isn't this slice's job.

### 2. Unread-notification indicator, on `index.astro`'s existing link

`src/lib/notifications.ts` gains `getUnreadCount(): Promise<number>`, calling `GET /me/notifications?unread_only=true&page=1&size=1` and reading `Page.total` - `size=1` only to read the pagination envelope's own count, not to inspect an item, so this stays cheap regardless of inbox size (no reuse of `listNotifications`'s `PAGE_SIZE=50`, and no client-side `countUnread` over a full fetched page).

`index.astro`'s existing `<a href="/notifications">Notifications</a>` gains a live count suffix (e.g. "Notifications (3)"), fetched once alongside the page's existing sign-in check, then polled every `30_000`ms - the same `POLL_INTERVAL_MS` `notifications.astro` already uses - paused on `visibilitychange` the same way that page already does. Each page owns its own independent polling loop, as already established; no cross-page shared timer is introduced.

### 3. Cross-tenant/cross-campaign access overview

New `src/pages/overview.astro` - a stand-alone page, not a `/tenants` section (keeps that already-large page from growing further; this view's audience - "where do I stand, everywhere" - doesn't overlap with `/tenants`'s per-tenant admin actions). `index.astro` gains a new link alongside the existing five.

Fetch: `getMe()` (for `campaignRoleFor` classification) plus the exact aggregation `/tenants` already does - `listMyTenants()`, then `listTenantCampaigns(tenantId)` per tenant. Rendered as one row per tenant (name, `TenantSummaryOut.role`) with its campaigns nested underneath, each campaign's own row showing `campaignRoleFor(campaign.id, me)`, filtered to exclude `'visible'` (a campaign the caller merely has visibility into but doesn't play or GM isn't "their access" in the sense this page is for). Deliberately **roles and membership state only** - no roster, no picture, no activity log; this is a navigation aid over `/tenants`'s own richer per-tenant view, not a second copy of it.

## Consequences

- No `apps/api` change - all three sub-slices are pure client additions against already-existing, already-authorized routes.
- `pictureUi.ts` is this app's second cross-page-reused `lib/*.ts` DOM-building module (after `userPicker.ts`, ADR 0074) - same established shape, not a new kind of file.
- `overview.astro` re-fetches `listMyTenants()`/`listTenantCampaigns()` independently of `/tenants` (no shared cache exists in this app) - an accepted, small amount of duplicate network traffic between the two pages, consistent with how `/characters`/`/beings` already each re-fetch their own view of the same underlying data rather than sharing a client-side store.
- Each of these three ships and is tested end to end as its own commit/slice before the next, per this project's established cadence - grouped into one ADR because, like ADR 0081, RFC 0019 already fully scoped each with no design debate left beyond confirming what's actually built (and, here, correcting two assumptions the RFC got wrong about this app's current shape).
