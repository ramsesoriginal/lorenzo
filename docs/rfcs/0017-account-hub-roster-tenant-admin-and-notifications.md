# RFC: `apps/account-hub` — roster view, tenant admin, and notification sending

Status: proposed

## Context

A step-back review after RFC 0014 landed, from three angles (GM, player, tenant admin) plus an infrastructure pass (what's already built server-side but never surfaced), turned up eight real gaps. All eight are, once again, entirely `apps/api` surface that already exists and is already correctly authorized - this RFC is scoping account-hub's access to it, not proposing backend work.

One finding changes an earlier assumption: `GET /tenants/{id}/memberships` (`list_tenant_roster`, ADR 0031/RFC 0004) isn't membership-only despite its name - it's a **discriminated union** (`MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut`) covering every relationship a user has in a tenant, and unlike `GmOut`/`PlayerSummaryOut` (ADR 0076/0079's own bare-`user_id` limitation), every row carries real `nickname`/`display_name`/`user_color`. This is a materially better data source than what ADR 0076/0079 had available at the time.

## Decision

### (a) GM: campaign roster view

New read-only view: `GET /tenants/{id}/memberships`, filtered client-side to `kind === 'player' || kind === 'gm'` rows matching the campaign's id, rendered with real display names (`display_name ?? nickname ?? user_id`, the same fallback chain `/tenants` already uses for GM revoke lists) and each player's characters. Gated the same as the endpoint itself - `get_tenant_context`, any tenant-wide member, not GM-only - a player can see who else is playing too.

**While here**: the existing GM-revoke list (ADR 0076) and player list (ADR 0079's handoff picker) both currently show raw `user_id`s - a named, accepted limitation at the time, because `GmOut`/`PlayerSummaryOut` don't carry names. Now that this roster endpoint is already being fetched for (a), both are upgraded to resolve real names from it too, rather than shipping two data sources for overlapping information side by side.

### (b) GM: being search in the UI

`listBeings(tenantId, q)` already accepts `q` (added in ADR 0079) - `/beings` gains a plain text input wired to it, debounced, per tenant section. No new API surface at all; this is purely a missing input element.

### (c) Player: leave a campaign

`DELETE /tenants/{id}/campaigns/{id}/players/{player_id}` (already built, RFC 0007), called with the caller's own `PlayerContextOut.id`. Shown on `/characters` per campaign row the caller plays in, with a confirmation step (this removes every character link that player row grants, not just an inbox item - the existing `character_player` roster-reuse links to *other* players are unaffected, only this one).

### (d) Tenant-creator: create a tenant

`POST /tenants` (`TenantCreate`: `name` required, `slug`/`description` optional). Gated server-side by `require_tenant_creator_role` - a **platform-level Authgear role** with no client-visible signal anywhere in `MeOut` or any other response this app reads. Unlike every other gated action in this app (where a `TenantSummaryOut.role`/`campaignRoleFor` result decides whether to show a button), there is nothing to check here - the form is simply always shown on `/tenants`, and a 403 from the API is surfaced exactly like any other authorization failure. This is the same "never re-implement authorization" principle taken to its honest conclusion when there's no data to approximate it with at all.

### (e) Admin: tenant-level membership management + bulk invite

Distinct from (and in addition to) RFC 0014's *campaign*-level GM/player management: `POST`/`PATCH`/`DELETE /tenants/{id}/memberships/{user_id}` (tenant-wide `owner`/`orga` role grants) and `POST /tenants/{id}/memberships/bulk` (`MembershipCreate[]`, never-all-or-nothing per-item results, ADR 0062). Bulk invite is confirmed `_require_owner`-gated (not `orga`); the single-item actions are gated identically here for consistency rather than assumed looser - showing nothing to an `orga` who might technically have single-item rights is the safe direction of a wrong guess, a 403 shown to an `owner` who should have had access is not. Reuses the ADR 0074 user picker for both the single-invite and each row of the bulk form.

### (f) Admin: tenant activity log

`GET /tenants/{id}/activity-log` (ADR 0063, `AuditLogEntryOut`: `actor_id`/`action`/`target_type`/`target_id`/`detail`/`created_at`). Gated the same as `list_tenant_roster` - any tenant-wide member, not owner-only, matching the endpoint's own real gate. `actor_id`/`target_id` are raw UUIDs with no guaranteed cross-reference (an actor may no longer be in the roster, a target may be a campaign/membership row, not a user) - shown as-is, not enriched, rather than guessing at a join that isn't always meaningful.

### (g) GM/admin: notification sending

`POST /tenants/{id}/notifications` and `POST /tenants/{id}/campaigns/{id}/notifications` (`NotificationCreate`: `type`, `title`, `body`, optional `recipient_user_id` - omitted broadcasts to that scope's whole roster). A composer on `/tenants` per tenant (tenant-scope, any tenant-wide member per that route's own gate) and per campaign (campaign-scope), with the ADR 0074 picker as an *optional* recipient resolver - leaving it empty broadcasts, matching the API's own documented behavior rather than requiring a recipient. Character-scope and group-scope notification sending are explicitly **not** built now - `apps/account-hub` has no character/group management surface for GMs to pick a sensible target from yet, and forcing a bare UUID field for either would be worse than not offering them (named here so they aren't lost, not silently dropped).

### (h) GM/admin: sent notifications

`GET /me/notifications/sent` (ADR 0061), optional `?batch_id=` to see one broadcast's full recipient list and read state. A new view (own page or a tab on `/notifications`) listing the caller's own sent batches, each expandable to its per-recipient `read_at` state - the whole point of ADR 0061's `batch_id`/`user_id` fields, unused until now.

## Not in scope

- Character-scope and group-scope notification sending (see (g)).
- Enriching activity-log actor/target ids with resolved names (see (f)) - a real possible follow-up, not designed here.
- Any change to `apps/api` - every capability above already exists.

## Consequences

- `src/lib/tenants.ts` gains the roster-union fetch/filter helpers, `createTenant`, membership CRUD + bulk invite, activity log, and notification-sending wrappers - all checked against the live schema, not guessed, per this project's own established practice for this app.
- `src/lib/notifications.ts` gains `listSentNotifications(batchId?)`.
- The GM-revoke and player-handoff lists (ADR 0076/0079) both improve from raw `user_id`s to real display names as a direct byproduct of (a) - a genuine fix, not scope creep, since it reuses data this RFC already needs to fetch.
- Separately from this RFC (an engineering/cleanup decision, not new capability, tracked as its own ADR without a preceding RFC): shared DOM helpers to remove the real duplication between `characters.astro`/`beings.astro`, `tenants.astro` split into coherent chunks, and defined CSS classes for markup that currently has none.
