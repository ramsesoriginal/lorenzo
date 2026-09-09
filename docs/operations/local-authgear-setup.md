# Local Authgear setup (manual, for interactive testing)

See [ADR 0009](../adr/0009-identity-provider-authgear.md) for why Authgear, [ADR 0023](../adr/0023-authgear-token-verification.md) for how `apps/api` verifies its tokens, and [ADR 0027](../adr/0027-authgear-cloud-not-self-hosted.md) for why this is Authgear Cloud rather than a self-hosted instance. This doc is the other half: getting a real Authgear project to test a real login round-trip against by hand. **Not required for `apps/api`'s own test suite** - that runs against a real fake-JWKS server instead (`apps/api/tests/_fake_jwks.py`), specifically so nobody needs a real Authgear project just to run `pytest`.

Use a **separate Authgear Cloud project from production** - free-tier accounts support more than one project, confirmed directly rather than assumed (see ADR 0027). Local dev never touches the production project at all.

## Steps

1. Sign up at [authgear.com](https://www.authgear.com) (free tier, no card needed) if you haven't already, and create a project for local dev (e.g. "development" - distinct from the "production" one used in [docs/operations/deployment-setup.md](deployment-setup.md)).

2. **Applications → New Application → OIDC Client Application.** `apps/api` itself never runs a login flow - it only verifies tokens afterward - but registering a client here is what lets you actually mint one to test with. Set an **Authorized Redirect URI** matching whatever will actually call back (a local test client, not `apps/api`).

3. The application's own page lists everything needed under different names than "issuer"/"JWKS URL":
   - **JSON Web Key (JWK) Set** - this is `AUTHGEAR_JWKS_URL` directly.
   - **OpenID Configuration Endpoint** - fetch this URL; the returned JSON's `"issuer"` field is `AUTHGEAR_ISSUER` (and also `AUTHGEAR_AUDIENCE` - see the gotcha below).

4. Set `apps/api`'s `.env`:

   ```bash
   AUTHGEAR_ISSUER=<issuer from step 3>
   AUTHGEAR_JWKS_URL=<JWK Set URL from step 3>
   AUTHGEAR_AUDIENCE=<issuer from step 3>  # same as issuer for access tokens - see ADR 0023
   ```

5. Get a real access token by completing a login through Authgear's own hosted UI (e.g. via the client application's own auth flow, or Authgear's API explorer) and call `GET /me` with it as a `Bearer` token - a fresh subject auto-provisions an `app_user` row on first call (ADR 0023).

## Known gotcha

Authgear's access-token `aud` claim is the **project endpoint URL** - the OIDC client id from step 2 is *not* the audience apps/api checks against (that's only true for ID tokens). Getting this backwards produces a confusing "wrong audience" 401 for an otherwise-correctly-configured setup.
