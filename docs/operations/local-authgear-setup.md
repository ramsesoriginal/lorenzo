# Local Authgear setup (manual, for interactive testing)

See [ADR 0009](../adr/0009-identity-provider-authgear.md) for why Authgear, and [ADR 0023](../adr/0023-authgear-token-verification.md) for how `apps/api` verifies its tokens. This doc is the other half: actually getting a real, local Authgear instance running, so a real login round-trip can be tested by hand. **Not required for `apps/api`'s own test suite** - that runs against a real fake-JWKS server instead (`apps/api/tests/_fake_jwks.py`), specifically so nobody needs to stand up Authgear's full stack just to run `pytest`.

This is deliberately **not** folded into `infra/docker-compose.yml`: Authgear's own reference stack is ~7 services (a `pg_partman`-patched Postgres unrelated to `apps/api`'s own `postgres:17-alpine`, Redis, MinIO, nginx, the auth server, the admin portal, a few one-shot init jobs) - a different lifecycle and footprint than this project's own local dev database, and not something this ADR's author has personally stood up and clicked through (see ADR 0023's own note on this).

## Steps

1. Clone the reference compose separately from this repo:

   ```bash
   git clone https://github.com/authgear/authgear-example-docker-compose.git
   cd authgear-example-docker-compose
   ```

2. Bring it up and run its one-time setup script (creates the initial portal admin - override `ADMIN_EMAIL`/`ADMIN_PASSWORD` first if you don't want the example's defaults):

   ```bash
   docker compose up -d
   ./setup.sh
   ```

3. Open the portal (`http://localhost:8010` by default) and sign in as the admin created above.

4. **Applications → New Application → OIDC Client Application.** Note the **Client ID**, and set an **Authorized Redirect URI** matching whatever will actually call back (a local test client, not `apps/api` itself - it never runs the login flow, only verifies tokens afterward).

5. From the application's **Endpoints** section, get the issuer URL, and fetch `<issuer>/.well-known/openid-configuration` to find `jwks_uri`.

6. Set `apps/api`'s `.env`:

   ```bash
   AUTHGEAR_ISSUER=<issuer URL from step 5>
   AUTHGEAR_JWKS_URL=<jwks_uri from step 5>
   AUTHGEAR_AUDIENCE=<issuer URL from step 5>  # same as issuer for access tokens - see ADR 0023
   ```

7. Get a real access token by completing a login through Authgear's own hosted UI (e.g. via the client application's own auth flow, or Authgear's API explorer) and call `GET /me` with it as a `Bearer` token - a fresh subject auto-provisions an `app_user` row on first call (ADR 0023).

## Known gotcha

Authgear's access-token `aud` claim is the **project endpoint URL** - the OIDC client id from step 4 is *not* the audience apps/api checks against (that's only true for ID tokens). Getting this backwards produces a confusing "wrong audience" 401 for an otherwise-correctly-configured setup.
