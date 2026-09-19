# 0075 - Sync user email via Authgear's UserInfo endpoint, not the access token

Status: accepted

## Context

[ADR 0054](0054-user-identity-email-and-nickname.md) added `User.email`, synced "read-only from the verified ID token, at the same JIT-provisioning moment `authgear_subject_id` is upserted (`dependencies.get_current_user`)". The code that actually shipped reads `email`/`email_verified` off `verify_token`'s decoded claims - but `verify_token` only ever decodes the **access token** ([ADR 0023](0023-authgear-token-verification.md) is explicit that this app never receives an ID token at all, only the Bearer access token). ADR 0054's own text and the code it describes were already talking about two different tokens.

This went undetected because every test proving `_sync_email_from_claims` works hand-crafts a JWT with `email`/`email_verified` embedded directly (`fake_jwks_server.issue_token(subject, email=..., email_verified=True)`) - which proves the sync *logic*, never that a real Authgear-issued access token actually carries those claims.

It doesn't. Per Authgear's own documentation, a JWT access token's default claims are `aud`/`client_id`/`exp`/`iat`/`iss`/`jti`/`sub` plus `https://authgear.com/claims/user/{is_verified,is_anonymous,can_reauthenticate}` - never `email`. Getting `email`/`name` onto the access token itself needs an explicit "JWT Access Token" hook configured in the Authgear project (a console/hook change, not something this repo's code controls) - not currently set up. Authgear does support an `email` OAuth scope-adjacent capability, but per its docs the profile-detail-bearing surface reachable from just the `openid` scope is the **UserInfo endpoint** (`GET /oauth2/userinfo`), the same thing `apps/inventory-web`'s own `fetchUserInfo()` already calls client-side to show the signed-in user's email (`src/pages/index.astro`).

Net effect, confirmed by reasoning through the actual claim set rather than assumed: `_sync_email_from_claims` has been a permanent no-op against every real Authgear-issued token since ADR 0054 landed. `User.email` never gets populated, which is why `GET /me` always shows `email: null` and `GET /users/{id}/picture`'s Gravatar fallback ([ADR 0056](0056-profile-pictures.md)) - itself implemented and tested correctly - never fires: it correctly has no email to build a Gravatar URL from. See [issue #89](https://github.com/ramsesoriginal/lorenzo/issues/89).

## Decision

`dependencies.get_current_user` now calls Authgear's UserInfo endpoint - using the caller's own already-verified access token as the Bearer credential - whenever the decoded access token itself doesn't already carry a valid verified email claim **and** `user.email` is still unset:

- New `Settings.authgear_userinfo_url` (default `http://localhost:4000/oauth2/userinfo`), explicit config mirroring `authgear_jwks_url`'s own precedent (ADR 0023's "explicit issuer/JWKS URL/audience, not dynamic discovery") - Authgear's endpoint shape is stable enough that hand-configuring it isn't a real burden, and it keeps this app's IdP-adjacent config in one consistent place.
- A new `get_userinfo_url()` dependency (not a bare `Settings` read) specifically so tests can override it via `app.dependency_overrides`, the same pattern `get_jwks_client` already established - `tests/_fake_jwks.py`'s fake server gains a `/userinfo` route and a `register_userinfo(token, **fields)` method tests use to control what it returns for a specific token.
- `_sync_email_from_claims` checks the decoded access token's own `email`/`email_verified` claims *first* - unchanged from before, and forward-compatible with a future JWT-hook-based Authgear config that does put them there directly - and only falls through to the UserInfo call when those are missing/invalid.
- The UserInfo call only happens once per user, not on every request: gated on `user.email is None` at the call site. An email is treated as a fact worth caching once obtained, not something re-checked on a hot path forever - the same one-shot-JIT framing ADR 0054 already used for the sync itself. A user whose Authgear email changes after their first successful sync won't pick that up automatically; unchanged from ADR 0054's own scope (it never promised live re-sync either).
- Any UserInfo call failure (network error, non-2xx, malformed body) is treated exactly like an absent claim - logged at most, never raised - matching `_sync_email_from_claims`'s existing "never fail the login over this" posture for the colliding-email case.

## Not in scope

- Configuring an Authgear "JWT Access Token" hook to put `email` on the access token directly - would remove the extra UserInfo round-trip, but is a project-console change outside this repo, and the code above already works correctly without it (and keeps working if it's added later).
- Re-syncing an already-populated `User.email` if it changes on the Authgear side later.
- `apps/loot-bot`'s own account-linking flow: it verifies its access tokens the same way (decodes the JWT directly, ADR 0050) but has never read an `email` claim from them at all - nothing there needs to change for this fix.

## Consequences

- `dependencies.py`: new `get_userinfo_url()`/`UserinfoUrlDep`, `_fetch_userinfo_email()`, `_sync_email_from_claims` and `get_current_user` both gain a couple of parameters; `config.py` gains `authgear_userinfo_url`.
- `tests/_fake_jwks.py`'s fake server now also serves `/userinfo`, gated per-token via `register_userinfo()`; `tests/conftest.py`'s `raw_client` fixture overrides `get_userinfo_url` alongside its existing `get_jwks_client` override.
- New `test_auth.py` case proving the actual gap this ADR closes: a token with no `email` claim on the JWT itself, whose registered UserInfo response has one, ends up synced to `User.email` - the scenario every prior email test skipped over.
- Production needs a new `AUTHGEAR_USERINFO_URL` Cloud Run env var (mirroring `AUTHGEAR_JWKS_URL`) before this actually populates real users' emails - flagged in [docs/operations/deployment-setup.md](../operations/deployment-setup.md), not something this change can set itself.
- Every authenticated request now makes at most one extra outbound HTTPS call to Authgear (only for a user whose email isn't synced yet) - acceptable: it's one-shot per user, not per-request, and every existing call site already tolerates Authgear-dependent latency (JWKS fetch) on the same request path.
