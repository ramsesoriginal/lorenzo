# 0048 - CORS configuration

Status: accepted

## Context

`apps/api` has never configured CORS - no `CORSMiddleware`, no mention in any prior ADR. That's fine as long as every caller is server-side (tests, a Discord bot, `curl`), but [ADR 0004](0004-static-astro-frontend.md) commits to static web frontends as one of this project's own client types, and a static site's JS necessarily calls this API cross-origin (a different origin than whatever serves the static assets). Without CORS headers, a browser blocks the response before the page's own JS ever sees it - not something the frontend can work around unilaterally, which is why it's the API's problem to solve, not each client's.

## Decision

`CORSMiddleware` (Starlette's own, added via FastAPI's `app.add_middleware`), configured from a new `Settings.cors_allowed_origins: list[str]` (pydantic-settings decodes a `CORS_ALLOWED_ORIGINS` env var as a JSON array, e.g. `["https://lorenzo.example.com"]`) - **defaults to `[]`**, matching this app's existing fail-closed defaults elsewhere (e.g. [ADR 0033](0033-tenant-creation-and-update-api.md)'s tenant-creator role): an unconfigured deployment allows zero cross-origin browser access rather than accidentally allowing all of it. `curl`/server-to-server callers (this app's own test suite included) are entirely unaffected either way - CORS only ever restricts browser JS, never a direct HTTP client.

`allow_credentials=False`: this API is bearer-token authenticated ([ADR 0023](0023-authgear-token-verification.md)), not cookie-based - a client attaches its token by setting the `Authorization` header itself, which doesn't require (or benefit from) the browser's credentialed-request mode. Also avoids the spec's own `allow_origins=["*"]` + `allow_credentials=True` combination being rejected outright, in case a deployment ever does configure a wildcard.

`allow_methods=["*"]`, `allow_headers=["*"]` - this API has no cross-cutting reason to enumerate a narrower set; every route already gates itself by tenant/authorization regardless of which HTTP verb or header reached it.

`expose_headers=["ETag", "Location"]` - the one genuinely easy-to-miss part of this decision. Browsers only expose a small built-in safelist of response headers to cross-origin JS by default (`Content-Type`, `Content-Length`, etc.) - **not** `ETag` or `Location`. Both are load-bearing for this API specifically: `ETag` is the entire point of [ADR 0042](0042-concurrency-token-on-reads.md)'s concurrency token, and `Location` is how every `201 Created` response points at the new resource ([ADR 0032](0032-item-and-item-instance-crud-api.md)). Configuring CORS without listing them would make every cross-origin browser client silently unable to read either header - the request itself would still succeed, making this the kind of gap that's invisible until someone actually tries to build the exact static frontend this ADR exists for.

## Not in scope

Per-route or per-origin variation (e.g. a public read-only origin vs. an authenticated-write one) - one configured origin list applies uniformly to every route. Cookie-based auth or any other reason to reconsider `allow_credentials` - stays tied to this API remaining bearer-token-only.

## Consequences

- `config.py`: new `Settings.cors_allowed_origins: list[str] = []`.
- `main.py`: `app.add_middleware(CORSMiddleware, ...)`, added early in `create_app()` (middleware order matters in Starlette; CORS should wrap as much of the response pipeline as possible, so it's added right after the app is constructed, before routers).
- A deployment that wants browser clients to work sets `CORS_ALLOWED_ORIGINS` to the origin(s) serving its static frontend(s) (see this ADR's own addendum for the exact format); local dev does the same in `.env` if a local static frontend is ever built against this API.

## Addendum: space-separated, not a JSON array

A real deploy with two origins in `CORS_ALLOWED_ORIGINS` (the JSON array this ADR originally specified, e.g. `["https://a.example.com","https://b.example.com"]`) crashed the app on startup with `SettingsError: error parsing value for field "cors_allowed_origins"`. The cause was entirely in the deploy pipeline, not this app's own logic: `google-github-actions/deploy-cloudrun`'s `env_vars` input joins `KEY=VALUE` pairs with `,`, and a JSON array of more than one origin has a literal `,` *inside* the value (between origins) - a direct collision with that separator. Backslash-escaping the internal comma (the action's own documented convention for its `env_vars` input) didn't fix it either: gcloud's own list-argument parser doesn't actually support backslash-escaping at all, only its own `^DELIM^` alternate-delimiter syntax - which this action doesn't expose control over. Either way, the container ended up seeing a truncated, invalid-JSON fragment and crashed at `Settings()` construction, before ever binding to a port.

Changed the format to space-separated exact origins instead (`https://a.example.com https://b.example.com`) - no comma, so no collision, regardless of how many origins are configured. `Settings.cors_allowed_origins` is `Annotated[list[str], NoDecode]` now, with a `_parse_cors_origins` validator doing the actual parsing (`config.py`) - `NoDecode` is required specifically because pydantic-settings JSON-decodes a `list[str]` field's raw env value in its own env-source layer, *before* any field validator runs; without it, the validator never even sees the raw string. The validator still accepts the original JSON-array form too (splits on whitespace only when the value doesn't start with `[`), so an existing `.env` using the old format keeps working unchanged.
