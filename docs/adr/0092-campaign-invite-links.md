# 0092 - Shareable, expiring campaign invite links

Status: accepted

## Context

Accepts [RFC 0019](../rfcs/0019-shareable-campaign-invite-links.md); read it for the reasoning trail. Today a GM can only add someone they can already identify (`POST .../players` takes a user id, [ADR 0036](0036-user-player-character-crud-api.md)), so a one-shot, a convention table, or an open LARP signup has no self-serve path. This adds one: a GM shares a link, and people join a campaign as players themselves.

Its RFC left four things open, decided with the maintainer:

1. **Abuse protection for the unauthenticated endpoints:** an edge rate rule as the real control, plus a small in-process backstop. Not a Postgres attempt counter (it turns every unauthenticated request into a DB write), not Redis ([ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md) stays deferred).
2. **Use cap:** *none required*. Expiry is still required. The RFC recommended a required cap; the maintainer chose to leave uses unbounded. That trades away one layer of leak containment, so every other layer below matters more, and it is called out again in Consequences.
3. **Redemption needs a login.** Joining creates a `player` row, which needs a user. Only the read-only preview is unauthenticated.
4. **Expiry maximum:** 30 days. This number was proposed in the RFC but not separately answered when its use-cap options were chosen - it is the one value here that is this ADR's assumption, and is a constant that is trivial to change.

## Decision

### Data

`campaign_invite(id, tenant_id, campaign_id, token_hash, created_by, created_at, expires_at, max_uses, use_count, revoked_at)`.

- The token is 256 random bits, URL-safe, shown **once**, when created. Only its SHA-256 is stored (`token_hash`, unique): a leaked table leaks no working links. No salt or slow KDF - the input is already unguessable.
- `expires_at` is **required**, at most 30 days after creation.
- `max_uses` is **optional** (`NULL` = unlimited). `use_count` always counts.
- Grants the **player** role in that one campaign only. Never GM, never orga, never tenant membership.
- Standard tenant RLS ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)), plus one extra clause for the lookup problem below.

### Management (authenticated, `can_manage_campaign`)

`POST .../campaigns/{id}/invites` returns the token once, `GET .../invites` lists metadata and counts (never tokens), `DELETE .../invites/{id}` sets `revoked_at`. Creation, revocation and every redemption are recorded in the activity log ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)); a redemption's actor is the redeemer.

### Redemption

- `GET /invites/{token}` - **unauthenticated**. A preview: the campaign's name and picture URL only. Nothing a holder of a leaked link couldn't already learn.
- `POST /invites/{token}/redeem` - **authenticated, not tenant-scoped**: any verified Authgear user (suspended accounts are already rejected centrally, [ADR 0057](0057-platform-operations.md)). Creates the `player` row through the same core mechanics `POST .../players` uses, in one transaction with the counter increment. **Idempotent** for someone already a player in that campaign: `200`, no second seat, no use consumed. Notifies the campaign's GMs ([ADR 0058](0058-notifications.md)). Whether an unverified email may redeem is Authgear's policy, not this API's: any valid verified token is accepted, and no extra check is added.

### The lookup problem (RLS)

The token identifies a tenant the caller doesn't know yet, so `app.tenant_id` can't be set first. Following `notification`'s precedent ([ADR 0058](0058-notifications.md)): an extra policy clause, `token_hash = current_setting('app.invite_token_hash', true)`, set only by the two routes above. Once resolved, they set `app.tenant_id` for everything afterwards. No `SECURITY DEFINER` function, no RLS bypass.

### Abuse protection

1. **Guessing.** 256-bit tokens; brute force is infeasible by construction.
2. **Enumeration.** An unknown, expired, revoked, or exhausted token is **indistinguishable**: same `404`, same problem type, same body, comparable timing (one indexed hash lookup, state checked after).
3. **Bounded, atomic use.** One `UPDATE ... SET use_count = use_count + 1 WHERE id = :id AND (max_uses IS NULL OR use_count < max_uses) AND expires_at > now() AND revoked_at IS NULL RETURNING ...`, never read-then-write, so concurrent redemptions cannot exceed a set `max_uses`.
4. **Flooding: an edge rule plus an in-process backstop.**
   - **The real control is an edge rate-limit rule** (Cloudflare or Cloud Armor) on `/invites/*`. That is infrastructure, not code; it is documented in `docs/operations/invite-link-rate-limiting.md` (a deliverable of this ADR), with the concrete rule to configure. Until that rule exists the endpoints must be treated as unprotected at the edge.
   - **The backstop is a per-instance token bucket** keyed by client address, in code, applied to both routes and returning `429` with `Retry-After`. It only limits each instance separately, which is exactly why it is a backstop and not the control. Its limits are settings (`INVITE_RATE_LIMIT_PER_MINUTE`, default 30). The client address is whatever uvicorn resolves; the deployment must forward the real client address (`--forwarded-allow-ips`), or every caller shares one bucket - checked in the implementation slice.
   - The preview does an indexed read and never writes; redeem writes only on success. Failed attempts are logged by `structlog` (reason class and source, **never the token**) so an operator can spot a probe and tighten the edge rule.
5. **Account farming.** Requiring a login means a seat costs an account, and Authgear handles signup abuse upstream. A GM who wants to vet joins uses a short expiry and revokes; an approval queue is a possible follow-up.
6. **Token leakage through logs.** The token is in the URL *path*. Access logs, OpenTelemetry spans (FastAPI instrumentation records paths) and `structlog` output must not contain it. This needs an explicit test that fails if a token appears in any of them, not a hope.
7. **Referrer leakage.** The web page that receives a link must send `Referrer-Policy: no-referrer` and remove the token from the address bar after reading it. This API can't enforce that; it is recorded here as a requirement on client apps.

## Not in scope

An approval queue; tenant-level (membership) invite links, a different and higher-privilege thing; choosing or creating a character on redeem (a separate, later step in account-hub); a use cap (deliberately absent); Redis or `fastapi-limiter`.

## Consequences

- One migration and model (`campaign_invite`), one router, config for the backstop, `docs/operations/invite-link-rate-limiting.md`, and the token-redaction test. The preview is this API's second unauthenticated resource route after picture serving ([ADR 0056](0056-profile-pictures.md)) and the first to read tenant-scoped data with no principal.
- **Unlimited uses are the weakest link.** With no cap, a leaked link admits accounts freely until it expires (at most 30 days), is revoked, or is throttled. Expiry, instant revoke, player-only scope, the edge rule and the backstop are the whole of the containment. `max_uses` remains an optional knob a GM can set. Every redemption also notifies the GMs, which on a busy open link will be noisy; deduplicating those is a reasonable follow-up, not built here.
- The edge rule is a real deployment step outside `apps/api`; this feature is not safe to expose publicly until it is in place.
- No client offers "share this campaign" until account-hub adds the management UI and a landing page - later slices against this API.
