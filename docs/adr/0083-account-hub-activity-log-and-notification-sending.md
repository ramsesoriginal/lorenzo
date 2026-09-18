# 0083 - account-hub: tenant activity log, notification sending, sent notifications

Status: accepted

## Context

Sub-slices (f)/(g)/(h) of [RFC 0017](../rfcs/0017-account-hub-roster-tenant-admin-and-notifications.md) - the remaining tenant-visibility and communication features, all already fully scoped by the RFC.

## Decision

### (f) Tenant activity log

New `src/lib/activityLogUi.ts` (`renderActivityLog`), fetching `GET /tenants/{id}/activity-log` (`AuditLogEntryOut`) and rendered per tenant on `/tenants`, gated the same as `list_tenant_roster` itself - any tenant-wide member, not owner-only. `actor_id`/`target_id` are shown as raw UUIDs, not enriched against the roster or anything else: an actor may no longer be in the roster, and a target may be a campaign/membership row rather than a user, so a join isn't always meaningful. Named explicitly in RFC 0017 as a real possible follow-up, not designed here.

### (g) Notification sending

New `src/lib/notificationComposerUi.ts` (`renderNotificationComposer`), parameterized over a `send` callback so the same composer serves both `POST /tenants/{id}/notifications` (tenant scope, shown per tenant to any tenant-wide member) and `POST /tenants/{id}/campaigns/{id}/notifications` (campaign scope, shown per campaign to a tenant admin or that campaign's own GM - the same `can_manage_campaign` gate RFC 0014 already established for GM/invite management). The ADR 0074 picker is an *optional* recipient resolver: the composer defaults to "broadcasting to everyone in this scope" and a "pick a specific recipient instead" button swaps in the picker; clearing it goes back to broadcast. This matches `NotificationCreate`'s own documented behavior (an omitted `recipient_user_id` broadcasts) rather than forcing a recipient. Character-scope and group-scope sending are not offered, per RFC 0017's own explicit exclusion - this app has no character/group management surface for a GM to pick a sensible target from yet.

### (h) Sent notifications

`/notifications` gained a "Show notifications I've sent" toggle revealing a second list, fetched from `GET /me/notifications/sent` (`listSentNotifications`, `src/lib/notifications.ts`) and grouped client-side by `batch_id` - every row a single send fanned out to shares one. Each batch card shows the shared title/body/type once, an `N/M read` summary, and a per-recipient breakdown (`user_id` plus `read_at` or "unread"). Fetched on demand (button click), not polled alongside the existing unread-inbox refresh loop - a sender checking read receipts is a deliberate, occasional look, not something that needs the same 30s cadence as an inbox.

## Consequences

- `src/lib/types.ts` gains `AuditLogEntryOut`, `NotificationCreate`, checked against the live schema.
- `src/lib/tenants.ts` gains `listActivityLog`, `createTenantNotification`, `createCampaignNotification`.
- `src/lib/notifications.ts` gains `listSentNotifications(batchId?)`.
- This completes all eight of RFC 0017's sub-slices ((a) through (h)).
