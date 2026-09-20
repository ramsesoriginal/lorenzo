# 0086 - `GET /me/managed` and a `since` filter on `GET /me/notifications`

Status: accepted

## Context

Two small additions a client needs and this API doesn't offer.

**Managed scope.** A user who runs things - owns or administers a tenant, or GMs campaigns - has no single read answering "what do I run?". `GET /me` returns memberships and players, but a GM's campaigns (`CampaignGm` rows) and the campaigns inside a tenant they administer need one request per tenant to assemble, since campaign reads are tenant-scoped ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)). A cross-tenant overview screen would otherwise fan out N requests on load.

**Notification polling.** `GET /me/notifications` returns every notification, newest first ([ADR 0058](0058-notifications.md)). A client that polls for new ones has to re-fetch and diff whole pages, or ask only for `unread_only`, which conflates "unread" with "new since I last looked".

## Decision

### `GET /me/managed`

Returns, for the caller only:

```
{ "tenants":   [ { tenant_id, name, slug, role, campaigns: [ { campaign_id, name, is_gm } ] } ] }
```

Included: every tenant where the caller's membership role is **OWNER or ORGA** (tenant-wide administrators, `is_tenant_admin`, [ADR 0030](0030-tenant-campaign-read-api.md)), each with **all** its campaigns; plus every tenant where the caller has a `CampaignGm` row, with just the campaigns they GM (`is_gm: true`). A campaign appears once, with `is_gm` true if they hold a GM row. `role` is the caller's tenant membership role, or `null` when they only GM.

- Not paginated, like `GET /me`: bounded by the caller's own memberships and GM rows.
- Not folded into `GET /me`, which stays cheap and is called on every page load by every client.
- Authenticated but not tenant-scoped, like `/me` ([ADR 0023](0023-authgear-token-verification.md)): it needs the same cross-tenant RLS handling `_me_out` already does - `membership` and `campaign_gm` admit the caller's own rows by `app.user_id`, but `campaign` names are tenant-scoped, so the implementation resolves them per tenant with `set_tenant_rls_context` rather than weakening any policy.
- Read-only, no attribution or audit entry.

Deliberately **not** included: players (a player who is neither admin nor GM manages nothing), and counts or roster details - this is an index to navigate from, not a dashboard.

### `since` on `GET /me/notifications`

`?since=<ISO 8601 datetime>` returns only rows with `created_at >= since`. Timezone-aware input required (`422` for a naive datetime, matching how the rest of this API treats timestamps). Composes with `unread_only`; ordering and pagination unchanged.

- **Inclusive (`>=`), not `>`.** A client stores the newest `created_at` it has seen and sends it back; with `>` it would silently miss a second row sharing that exact timestamp. With `>=` it may see the boundary row again and dedupes by `id`, which is trivial. A duplicate is a cosmetic cost; a lost notification is a bug.
- A plain timestamp, not an opaque cursor: no cursor state to invent, and the existing `Page` pagination already bounds each response.
- Known limitation, stated rather than hidden: a row written by a transaction that began before, but committed after, the client's last poll can carry an earlier `created_at` and be skipped. Notifications are created in short single transactions, so this is narrow; a monotonic server-side sequence is the real fix if it ever matters.
- Applies to `/me/notifications` only. `/me/notifications/sent` ([ADR 0061](0061-notification-sender-read-receipts.md)) is unchanged.

## Not in scope

- A cursor/keyset scheme, an unread-count endpoint, or push. (ADR 0058's "not in scope" list stands.)
- Any write behavior.
- Including players' or ordinary members' campaigns in the managed scope.

## Consequences

- One new route and schema (`ManagedScopeOut`), one new optional query parameter, tests for both including a caller with no memberships (empty list, not `404`).
- `GET /me/managed` adds a cross-tenant read path; it must be exercised with a real verified token (`raw_client`), not only the fake-user fixture, for the same reason [ADR 0038](0038-information-payload-knowledge-crud-api.md) found the hard way.
- No migration.
