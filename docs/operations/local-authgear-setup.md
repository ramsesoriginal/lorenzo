# Local Authgear setup (manual, for interactive testing)

See [ADR 0009](../adr/0009-identity-provider-authgear.md) for why Authgear, [ADR 0023](../adr/0023-authgear-token-verification.md) for how `apps/api` verifies its tokens, and [ADR 0027](../adr/0027-authgear-cloud-not-self-hosted.md) for why this is Authgear Cloud rather than a self-hosted instance. This doc is the other half: getting a real Authgear project, and a real login round-trip against it, working locally. **Not required for `apps/api`'s own test suite** - that runs against a real fake-JWKS server instead (`apps/api/tests/_fake_jwks.py`), specifically so nobody needs a real Authgear project just to run `pytest`.

Use a **separate Authgear Cloud project from production** - free-tier accounts support more than one project, confirmed directly rather than assumed (see ADR 0027). Nothing in the steps below touches the production project, but see the first gotcha: tasks run through `mise` carry the production Authgear values.

## Steps

1. Sign up at [authgear.com](https://www.authgear.com) (free tier, no card needed) if you haven't already, and create a project for local dev (e.g. "development" - distinct from the "production" one used in [docs/operations/deployment-setup.md](deployment-setup.md)).

2. **Applications → New Application → OIDC Client Application.** `apps/api` itself never runs a login flow - it only verifies tokens afterward - but registering a client here is what lets you actually mint one to test with, via `scripts/get_dev_token.py` (step 5). Set **Authorized Redirect URIs** to exactly `http://127.0.0.1:8765/callback` - that script's own fixed loopback address. Note the **Client ID** and **Client Secret Key** too.

3. The application's own page lists everything needed under different names than "issuer"/"JWKS URL":
   - **JSON Web Key (JWK) Set** - this is `AUTHGEAR_JWKS_URL` directly.
   - **OpenID Configuration Endpoint** - fetch this URL; the returned JSON's `"issuer"` field is `AUTHGEAR_ISSUER` (and also `AUTHGEAR_AUDIENCE` - see the gotcha below), and its `"userinfo_endpoint"` field is `AUTHGEAR_USERINFO_URL` (ADR 0075 - this is what actually populates `User.email`, since the access token itself never carries an `email` claim).

4. Set `apps/api`'s `.env`:

   ```bash
   AUTHGEAR_ISSUER=<issuer from step 3>
   AUTHGEAR_JWKS_URL=<JWK Set URL from step 3>
   AUTHGEAR_AUDIENCE=<issuer from step 3>  # same as issuer for access tokens - see ADR 0023
   AUTHGEAR_USERINFO_URL=<userinfo_endpoint from step 3>
   ```

5. Get a real access token with `mise run //apps/api:dev-token` (against production unless run as the first gotcha describes; needs `AUTHGEAR_DEV_CLIENT_ID`/`AUTHGEAR_DEV_CLIENT_SECRET` set in your shell first, from step 2 - deliberately not read from `.env`, since they identify a login-flow client, not something `apps/api` itself needs to run). Opens your browser, logs you in, and prints a ready-to-use token - no manual URL-building or curl required. Call `GET /me` with it as a `Bearer` token - a fresh subject auto-provisions an `app_user` row on first call (ADR 0023).

## Known gotchas

**The root `mise.toml` sets production values.** Its `[env]` block names the production Authgear project (`AUTHGEAR_ISSUER`, `AUTHGEAR_JWKS_URL`, `AUTHGEAR_AUDIENCE`, `AUTHGEAR_DEV_CLIENT_ID`, `PUBLIC_AUTHGEAR_ENDPOINT`, `PUBLIC_AUTHGEAR_CLIENT_ID`), and `mise` applies it to every task and `mise exec`, over the shell's own variables as well. A process that is handed an environment variable ignores the same name in `.env` (pydantic-settings for `apps/api`, Vite for the web apps), so `mise run //apps/api:dev` and `:dev-token` verify and sign in against production, whatever `apps/api/.env` says in step 4. To use the development project, run the tool without `mise` supplying that block: from `apps/api`, `uv run fastapi dev src/lorenzo_api/main.py` reads `.env`, and `uv run python scripts/get_dev_token.py --issuer <issuer from step 3>` with `AUTHGEAR_DEV_CLIENT_ID` and `AUTHGEAR_DEV_CLIENT_SECRET` set in a shell where `mise` is not active.

**The audience is the project endpoint.** Authgear's access-token `aud` claim is the **project endpoint URL** - the OIDC client id from step 2 is *not* the audience apps/api checks against (that's only true for ID tokens). Getting this backwards produces a confusing "wrong audience" 401 for an otherwise-correctly-configured setup.
