# RFC: Shareable, expiring campaign invite links

Status: proposed

## Context

Today, getting someone into a campaign means the GM already knows who they are: `POST .../campaigns/{id}/players` takes an identity ([ADR 0036](../adr/0036-user-player-character-crud-api.md)), and tenant membership takes a `user_id` ([ADR 0054](../adr/0054-user-identity-email-and-nickname.md)/[0055](../adr/0055-user-lookup-by-email-or-nickname.md) added exact-match lookup by email/nickname). There is no self-serve path. A one-shot, a convention table, or an open LARP signup all want the opposite: post a link, let people join themselves.

Two facts about the existing model shape everything below:

- Joining a campaign creates a `player` row, which needs a **user identity**. A visitor with no account cannot be a player. So "redeem" cannot be truly anonymous - it needs at least a verified login. What *can* be anonymous is a read-only preview ("You've been invited to *Zorro's Campaign*").
- A player does not need a tenant `Membership` ([ADR 0022](../adr/0022-user-tenant-membership.md)), so redemption can grant exactly a campaign seat and nothing broader.

## Proposal

### Data

`campaign_invite(id, tenant_id, campaign_id, token_hash, created_by, created_at, expires_at, max_uses, use_count, revoked_at)`.

- The token is 256 random bits, URL-safe, shown **once** at creation. Only its SHA-256 is stored (`token_hash`, unique) - a leaked table doesn't leak working links. (256-bit hashing needs no salt or slow KDF: the input is already unguessable.)
- `expires_at` is **required**, capped at a maximum (proposed: 30 days). No non-expiring links.
- `max_uses` is required too (proposed default 25, cap 500) - an open link must still be bounded.
- Grants role **player only**. Never GM, never orga, never tenant membership - an invite cannot escalate.
- Tenant-scoped with the standard RLS ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)), plus one extra clause for the lookup problem below.

### Management (authenticated, `can_manage_campaign`)

`POST .../campaigns/{id}/invites` (returns the token once), `GET .../invites` (metadata and counts, never tokens), `DELETE .../invites/{id}` (sets `revoked_at`). Creation and revocation are recorded in the activity log ([ADR 0084](../adr/0084-activity-log-coverage-and-member-removal-notice.md)); so is every redemption, actor = the redeemer.

### Redemption

- `GET /invites/{token}` - **unauthenticated**, a preview: campaign name and picture URL only. No tenant name, no roster, nothing an attacker holding a leaked link couldn't already infer.
- `POST /invites/{token}/redeem` - **authenticated, but not tenant-scoped**: any verified Authgear user (suspended accounts already rejected centrally, [ADR 0057](../adr/0057-platform-operations.md)). Creates the `player` row through the same core mechanics `POST .../players` uses, in one transaction with the counter increment. Idempotent for someone already a player: `200`, no second seat, no counter burn. Notifies the campaign's GMs (in-app, [ADR 0058](../adr/0058-notifications.md)).

### The RLS lookup problem

The token identifies a tenant; the caller doesn't know it yet, so `app.tenant_id` can't be set first. Follow the precedent `notification` set ([ADR 0058](../adr/0058-notifications.md)): an extra policy clause, `token_hash = current_setting('app.invite_token_hash', true)`, set only by the two redemption routes. Once resolved, the routes set `app.tenant_id` for everything after. No `SECURITY DEFINER` function, no RLS bypass.

## Abuse protection (required, not optional)

`/invites/{token}` is reachable by anyone on the internet, and `redeem` by anyone with an account. This RFC is not acceptable without an explicit answer for each of these:

1. **Token guessing.** 256-bit tokens make brute force infeasible by construction; no throttle is *needed* for this, only for the rest.
2. **Enumeration side channels.** Unknown, expired, revoked and exhausted tokens must be **indistinguishable**: same status (`404`), same problem type, same body, and comparable timing (one indexed hash lookup either way, the state check after). A distinguishing response tells an attacker a token was once real.
3. **Link farming / leaked links.** The link is a bearer credential. Bounded by required `expires_at`, required `max_uses`, instant revoke, and player-only scope. The use counter is incremented with a single atomic `UPDATE ... SET use_count = use_count + 1 WHERE id = :id AND use_count < max_uses AND expires_at > now() AND revoked_at IS NULL RETURNING ...`, never read-then-write, so concurrent redemptions cannot exceed `max_uses`.
4. **Request flooding** (DoS/cost). This is the real open question, because **this project has no rate limiter**: [ADR 0008](../adr/0008-deferred-taskiq-and-fastapi-limiter.md) deferred `fastapi-limiter` because it needs Redis, and Cloud Run runs several instances, so an in-process counter only limits each instance. Options, none decided:
   - **(A) Edge limit** - a Cloudflare or Cloud Armor rate rule in front of these two paths. Best protection; it is infrastructure, not code, and needs a doc in `docs/operations`.
   - **(B) Postgres-backed counter** - a small attempts table. Works across instances with no new service, but it turns every unauthenticated request into a DB *write*, which is itself the amplification we're trying to prevent. Only viable if writes happen on *failure* per source and are bounded.
   - **(C) In-process token bucket** - cheap, per-instance, a backstop only.
   - **(D) Revive ADR 0008** and add Redis - the honest general answer, but the largest change.
   
   **Recommendation: (A) as the real control plus (C) as a code-level backstop; do not add (B) or (D) for this feature alone.** `GET`-preview does only an indexed read and never writes; `redeem` writes only on success. Failed attempts are structured-logged (with source, no token) and counted in metrics so an operator can see a probe and add an edge rule ([observability](../architecture/observability.md)).
5. **Account farming to fill a campaign.** Requiring login makes seats cost an account, and Authgear handles signup abuse upstream. A GM who doesn't want unvetted joins uses a small `max_uses` and revokes; an approval queue is a possible follow-up, not this RFC.
6. **Token leakage through logs.** The token is in the URL path. Access logs, tracing spans (`opentelemetry` FastAPI instrumentation records paths) and `structlog` must redact or drop it. Needs an explicit test, not a hope.
7. **Referrer leakage.** The web landing page that receives the link must set `Referrer-Policy: no-referrer` and strip the token from the address bar after reading it. Recorded here as a requirement on the client apps, since this API can't enforce it.

## Open questions

- Is `redeem` allowed for a user whose email is unverified? (Recommendation: yes - Authgear controls that policy; this API doesn't add its own.)
- Default and cap for `expires_at` and `max_uses` - the numbers above are proposals.
- Should redeeming also let the joiner pick or create a character, or is that a separate, later step in account-hub? (Recommendation: separate; keep redemption to "gets a seat".)
- Tenant-level invite links (tenant membership) are a different, higher-privilege thing and are **not** proposed here.

## Consequences

- One new table and migration (`campaign_invite`), one router, two unauthenticated-or-nearly routes. The unauthenticated preview is the second such route in this API after picture-serving ([ADR 0056](../adr/0056-profile-pictures.md)) and the first that reads tenant-scoped data without any principal.
- Decision (4) has a real infrastructure component; it cannot be finished inside `apps/api` alone. The ADR that this RFC becomes must say who configures the edge rule and where that is documented.
- No client can offer "share this campaign" until account-hub adds the management UI and a landing page; those are later slices against this API, not part of it.
