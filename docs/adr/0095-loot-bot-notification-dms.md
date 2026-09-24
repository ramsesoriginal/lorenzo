# 0095 - loot-bot: notification DMs, with a "couldn't DM you" fallback

Status: accepted

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 6. `apps/api` fans notifications out per recipient ([ADR 0058](0058-notifications.md)) and `apps/account-hub` shows them, but a player who lives in Discord only learns about an award by opening a web app. The bot already holds each user's own Authgear token ([ADR 0050](0050-loot-bot-stack-linking-and-isolation.md)), so it can read a user's own inbox with no `apps/api` change: `GET /me/notifications?unread_only=true`.

The decisions below were settled in conversation before this was built: Cloud Scheduler as the trigger, a queued "couldn't DM you" banner as the closed-DMs fallback, and the bot keeping its own cursor. What the code added:

- **The bot can't poll for itself.** It runs on Cloud Run and scales to zero ([ADR 0053](0053-loot-bot-http-interactions-and-cloud-run-deploy.md)); an in-process timer only fires while some request happens to keep an instance warm. `min-instances: 1` would fix that at real recurring cost and reverse ADR 0053's whole point.
- **The endpoint can't simply be private.** The same service must stay publicly reachable for Discord's webhooks, so Cloud Run's own IAM can't gate a route on it.
- **`/read` is not the bridge's to call.** Marking a notification read in Lorenzo would silently empty the user's `apps/account-hub` inbox.
- **Discord DMs fail in a specific, expected way.** A user with DMs closed gets Discord error code 50007 ("Cannot send messages to this user"), a fact about the user rather than a fault.
- **The API has no per-user "since" filter on this route in this codebase** (only `unread_only`, paged newest-first), so "what's new" has to be decided bot-side.

## Decision

### Cloud Scheduler calls `POST /internal/deliver-notifications`

One Cloud Scheduler job (every five minutes) posts to a new route on the existing service, keeping ADR 0053's scale-to-zero and $0-at-idle properties; one job is inside the free tier. The route:

- **Is off unless configured.** With no `NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT` it answers a plain 404, so a deploy that hasn't done the one-time setup exposes nothing.
- **Only serves Cloud Scheduler.** It verifies the Google-signed **OIDC ID token** the job attaches as a bearer token (`jose`, against Google's published keys): a valid signature, Google as issuer, an audience equal to exactly this route's URL (Cloud Scheduler's default for a job), not expired — and, crucially, `email` equal to the one configured service account with `email_verified` true. Without that last check, any Google-issued token with this audience, minted for anyone's own account, would pass. Every failure is the same bare 401 (the reason goes to the log only), and only POST is accepted.
- **Holds no long-lived secret.** The token is minted per request and expires within the hour — the same property Workload Identity Federation gives the deploy pipeline ([ADR 0011](0011-deploy-target-cloud-run-neon.md)/[0053](0053-loot-bot-http-interactions-and-cloud-run-deploy.md)), which a static shared-secret header would not. The service account needs no IAM roles; it exists only to identify the caller.
- `jose` (already in the lockfile transitively, via `openid-client`) becomes a direct dependency.

### Every read is as the recipient

For each linked user the run takes *that user's* stored token ([`getValidAccessToken`](../../apps/loot-bot/src/token-provider.ts), the same refresh machinery every command uses) and reads *their own* unread notifications. There is still no shared service token. A user with no usable token is skipped and counted (they get the usual "run `/link` again" the next time they use the bot).

### A bot-side ledger, not `/read`

Two new `loot_bot` tables (migration `0005`), no RLS, matching the schema's other bot-local tables:

- `notification_enrollment(discord_user_id, enrolled_at)` — stamped **once**, the first time the bridge sees a linked user.
- `notification_delivery((discord_user_id, notification_id), state, title, body, claimed_at, updated_at)` — what the bridge has done with each notification. `state` is `sending` → `sent`, or `undelivered` → `noticed`. `title`/`body` are stored **only** for `undelivered` rows (the one place the bot must hold notification text, and only until the banner has shown it; they are nulled once noticed).

Delivery is exactly-once *per (user, notification)* via an atomic claim — one `INSERT … ON CONFLICT DO UPDATE … WHERE`, not check-then-write — so overlapping scheduler runs, or two Cloud Run instances, can never both DM it. A `sending` claim older than ten minutes is treated as stale and can be taken over (a run that died mid-send); `sent`/`undelivered`/`noticed` are terminal.

### What counts as deliverable

`selectDeliverable` (pure, tested on its own): unread, **this bot's tenant or platform-wide** (`GET /me/notifications` spans every tenant the user belongs to, but a bot serves exactly one — a null `tenant_id` is platform scope, addressed to the user), created **after the user's enrollment** (so enabling the bridge never DMs anyone their existing inbox), no older than **seven days** (bounding what a long outage could ever send), oldest first, at most **five per user per run** (a burst arrives as a trickle across runs rather than a flood). Finished ledger rows are pruned after thirty days — deliberately much longer than the age cap, so a row is never pruned while its notification could still be picked up.

### Failure handling: retry the transient, keep the refused

- **DMs closed (50007)** is an outcome, not an error: the notification becomes `undelivered`, with its text kept for the banner.
- **Anything else** (rate limit, 5xx, unexpected 4xx) is transient: the claim is released so the next run retries it, and the run stops for that user (more sends into a rate limit only make it worse). One user's failure never stops another's.

### The fallback: a "couldn't DM you" banner on the next command

After any **slash command** has answered, if the user has `undelivered` notifications, the bot sends a private (ephemeral) follow-up: "**Couldn't DM you.** Lorenzo has N notifications for you that Discord wouldn't let me send privately (your DMs from server members may be off). Here they are: …" — up to five, oldest first, each a title and a short snippet, with "…and K more, which I'll show on your next commands" if more wait. Only the ones actually listed are marked `noticed`, and only after the follow-up went out. This is what turns "missed an award silently" into "found out, just not by DM".

- **A follow-up, not spliced into the command's own reply.** Commands own their replies; a follow-up works identically for every one of them and needs no change to any.
- **Slash commands only**, not button clicks or menu picks — those are steps in a flow, and a banner in the middle of one would be noise.
- **Best-effort.** It runs after the user's real command already succeeded, so any failure is logged and swallowed; a notice problem never turns a working command into an error. It costs one indexed read per slash command.
- It also runs after a command that itself failed: the user should still learn what they missed.

### Configuration

`NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT` (optional email; an empty string counts as unset, as an unset GitHub Actions variable arrives as `""`). The deploy workflow passes it from a new `LOOT_BOT_SCHEDULER_SERVICE_ACCOUNT` variable. The route's URL and OIDC audience are derived from `LOOT_BOT_PUBLIC_BASE_URL`, so the two can't drift. One-time setup is in [docs/operations/deployment-setup.md](../operations/deployment-setup.md).

## Alternatives considered

- **`min-instances: 1` and an in-process timer.** Rejected: forfeits scale-to-zero, real recurring cost, reverses ADR 0053.
- **Mark notifications read from the bot as the cursor.** Rejected: silently drains the `apps/account-hub` inbox.
- **A static shared-secret header on the route.** Rejected: a long-lived credential in GitHub/Cloud Run, where OIDC needs none.
- **A channel post as the closed-DMs fallback.** Rejected as the default: it would leak a private notification to the channel.
- **Grouping notifications that share a `batch_id`.** Not built; one DM per notification, capped per run. A cheap follow-up if it reads as noisy.

## Consequences

- **A one-time human step**, made explicit: the Cloud Scheduler job, its service account, and the `LOOT_BOT_SCHEDULER_SERVICE_ACCOUNT` variable. Until then the feature is simply off.
- **Migration `0005`, chained on `/container-new`'s `0004`.** Drizzle numbers migrations sequentially and each snapshot builds on the last, so two branches can't both be `0004`. This branch therefore contains [ADR 0094](0094-loot-bot-container-new.md)'s `/container-new` (which keeps `0004`) and has its own tables regenerated on top as `0005`. It must merge after `/container-new`; the reverse order would need this one's migration regenerated.
- **At-least-once at the edges.** If a DM is sent but recording it fails, the claim goes stale and a later run may send it again after ten minutes; and a banner shown but not recorded shows once more. Both are rare and harmless, and preferred to the alternative of losing one.
- **Latency.** A notification arrives on the next five-minute tick, not instantly; the banner path is immediate on the user's next command.
- Not built: a per-user opt-out, a channel-post option, retry backoff beyond the next tick, DMs for notifications from other tenants, and grouping by `batch_id` — each an easy follow-up if it turns out to matter.

## Addendum (2026-09-24): `GET /me/notifications` does have a `since` filter ([ADR 0086](0086-managed-scope-aggregate-and-notifications-since-filter.md))

The Context bullet above saying this route has no `since` filter described the branch this ADR was written on, which didn't yet include [ADR 0086](0086-managed-scope-aggregate-and-notifications-since-filter.md)'s `?since=` (inclusive `created_at >= since`, timezone-aware, composes with `unread_only`). On `main` it exists. The decision above is unchanged: the bridge still reads `unread_only=true` and applies the tenant, enrollment and seven-day cutoffs bot-side in `selectDeliverable`, and the ledger, not a timestamp, is what makes delivery exactly-once per notification. Passing `since` could narrow what each run reads; not done here.
