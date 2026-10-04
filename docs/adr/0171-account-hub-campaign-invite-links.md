# 0171 - account-hub: campaign invite-link management and a landing page

Status: accepted

The client half of [ADR 0092](0092-campaign-invite-links.md), decided with the maintainer on 2026-10-04 as the last slice of the "Account Hub Refinements" milestone. ADR 0092 ended with "No client offers 'share this campaign' until account-hub adds the management UI and a landing page - later slices against this API"; this is that slice. **No `apps/api` change**: every route used here exists.

## Context

The API gives campaign managers `POST`, `GET` and `DELETE .../campaigns/{c}/invites` (`can_manage_campaign`), and gives anyone with a link `GET /invites/{token}`, unauthenticated, and `POST /invites/{token}/redeem`, which needs a login and grants a player seat and nothing more. A token is shown once, when created. Every dead link (unknown, expired, revoked, used up) answers the same `404` on purpose.

ADR 0092 left four requirements to the client (its requirement 7 and what follows from it): the page that receives a link must send `Referrer-Policy: no-referrer`, must remove the token from the address bar after reading it, and the token must not be logged or kept anywhere it need not be.

**The gate.** [docs/operations/invite-link-rate-limiting.md](../operations/invite-link-rate-limiting.md) says the feature must not be exposed publicly until the edge rate-limit rule exists (issue #161, an operator step), and the API's trusted-proxy hop count has not yet been confirmed against real Cloud Run traffic (issue #159). `apps/account-hub` deploys to Cloudflare Pages from every push to `main`, so merging this *is* exposing it. It is built and tested in full, and its pull request stays a draft, marked blocked on both, until the maintainer has done those steps.

## Decision

### Management, on `/tenants`

A new `src/lib/inviteLinksUi.ts` (`renderInviteLinks`) adds an "Invite links" panel to each campaign the caller can manage, gated as the other campaign admin panels are: a library administrator, or that campaign's own GM (`admin || role === 'gm'`, the real `can_manage_campaign`).

- **Create.** Expiry is required: a choice of one hour, one day, one week or four weeks, turned into an `expires_at` when the form is sent. Presets keep a person out of time zones, and four weeks, not the API's thirty days, keeps a client clock that runs a little fast from asking for more than the API allows. "Most people may use it" is optional: an empty box means no limit (`max_uses` omitted), otherwise a whole number of at least 1.
- **The link, once.** The response is the only time the token exists. The panel shows the whole link in a read-only box with a **Copy** button and says it will not be shown again, and that anyone who has it can join the campaign as a player until it expires or is revoked. The link lives in that element only: not in `sessionStorage`, not in the list, not in the console, and gone when the panel is dismissed or the page reloads.
- **The list.** `GET .../invites` shows what the API returns and never a token: created, expires, uses (`3 of 10`, or `3, no limit`), and a status. The status comes from one pure function, `inviteStatus(invite, now)`, in `src/lib/inviteLink.ts`: **Active**, **Revoked**, **Expired** or **Used up**.
- **Revoke.** An active link has **Revoke** behind a `window.confirm`; it calls `DELETE .../invites/{id}` and reloads the list.

### The landing page, `/join/`

A link is `https://<hub>/join/#<token>`: the token goes in the **fragment**, which a browser never sends to a server, a proxy, an access log or a `Referer`. ADR 0092's own token is a path segment of the API's URL; this keeps it out of the hub's URL on the wire as well. (`inviteLink.ts` builds the link and reads the token back, and refuses anything that is not URL-safe base64.)

1. **Read, then hide.** The page reads the token from the fragment, keeps it in `sessionStorage`, and immediately calls `history.replaceState` so the address bar and the history entry no longer hold it. It never puts the token in a link, a log line or an error.
2. **Preview, no login.** `GET /invites/{token}` through a second API client built without an access-token source (the shared `client` refuses a request without one), showing the campaign's name and picture.
3. **Join, after login.** A signed-out visitor sees the preview and **Log in to join**; `login()` returns them to `/join/` (the return path of [ADR 0170](0170-account-hub-readable-errors-self-service-exits-and-admin-basics.md)), where the token is still in `sessionStorage`, and the preview and a **Join** button show. **Join** is `POST /invites/{token}/redeem`. Afterwards the token is removed from `sessionStorage`. The answer is "You're in: <campaign> lists you as a player", or "You're already a player in <campaign>" when `already_joined`, with a link to "Your characters".
   If the browser blocks `sessionStorage`, the page can't keep the link through a login, and says so beside **Log in to join** ("Log in first, then open the link again"). A link pasted into the tab that is already showing `/join/` changes only the fragment, which a browser loads no page for, so the page reloads itself on `hashchange` and reads it like any other.
4. **One message for every dead link.** A `404` from the preview or from redeeming, and a missing token, all show "This link doesn't work any more. Ask whoever sent it for a new one." The page does not try to tell the cases apart. A `429` or a network failure keeps the token and says so with `describeError`, so a retry is possible.
5. **No referrer.** `public/_headers` (this app's first) sends `Referrer-Policy: no-referrer` for `/join` and `/join/*`, and the page also carries `<meta name="referrer" content="no-referrer">` as a backup, through a `head` slot added to `Base.astro`.

## Not in scope

Choosing or creating a character after redeeming (a later slice, as ADR 0092 said: the page links to "Your characters", where a player can already make one); tenant-level (membership) invite links; an approval queue; editing an invite; a use cap the API does not require; deduplicating the GM notifications a busy link sends.

## Consequences

- **The pull request is a draft and does not merge** until the edge rule exists (#161) and the proxy hop count is confirmed (#159). Nothing links to `/join/` from anywhere else, but a deployed page is a page.
- Unlimited uses stay the weakest link, as ADR 0092 says. The panel makes the choice visible (a use limit is a box on the form) and shows the use count, but does not push a limit on anyone.
- `sessionStorage` is now the one place a token is held between pages, for as long as a login takes, and is cleared on use. It is per tab, so a login in another tab does not find it, and the page then shows the neutral message.
- `inviteStatus`, the expiry presets and the link builder and reader are pure and unit-tested; `/join/` has a logged-out page smoke spec like the others and, where the real-API browser harness can run, a spec that creates a link through the API and redeems it in a browser.

## Addendum (2026-10-04): the edge rule is deferred to go-live

Decided with the maintainer after the gate above was looked at for real. An edge rate-limit rule needs something in front of the API that this project does not have: Cloudflare's rate-limiting rules only apply to a hostname proxied through Cloudflare, which means a domain of the project's own, and Cloud Armor needs an external load balancer in front of Cloud Run. Both are a purchase, and both change the address everything is served from. The project is pre-production and being tested, so the rule ([#161](https://github.com/ramsesoriginal/lorenzo/issues/161), closed as deferred) waits until it goes live: when there is a real domain and a settled hosting setup, **before the API has a public production address**. It is not dropped.

- **The gate above no longer applies** to this client. `/join/` and the management panel may ship, and the pull request needs no longer wait on #161.
- **Until the rule exists, the only limiter is the API's own backstop** ([ADR 0092](0092-campaign-invite-links.md)): a token bucket per client address, kept per instance, `INVITE_RATE_LIMIT_PER_MINUTE` (default 30). It does not stop a flood spread across instances, so a flood is a cost and noise risk, not a guessing risk: tokens are 256 random bits, a dead link is the same `404` whatever the reason, and a rejected attempt is logged by source. The deploy workflow sets no instance cap (`--max-instances`), so unless one was set on the service by hand, Cloud Run's default applies.
- **#159 stays open, and matters more:** with no edge layer, the backstop's trusted-proxy hop count (`INVITE_RATE_LIMIT_TRUSTED_PROXY_HOPS=1` on Cloud Run) is the whole of the limiting. A wrong value fails toward one bucket shared by everyone, not toward being open, but it would throttle the feature for all at once. It is confirmed by hammering the preview from one machine until it answers `429`, then asking for it once from another network and getting `404`.
- **The record of what is owed** is the banner in [docs/operations/invite-link-rate-limiting.md](../operations/invite-link-rate-limiting.md), which now says so, in place of the issue.
