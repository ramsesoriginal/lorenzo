# Getting started

## Prerequisites

- [mise](https://mise.jdx.dev) — manages every other toolchain
- Docker (or compatible) — for local Postgres
- Git

## From clone to running

```bash
git clone git@github.com:ramsesoriginal/lorenzo.git
cd lorenzo
mise install

docker compose -f infra/docker-compose.yml up -d   # Postgres for apps/api
uv run --directory apps/api alembic upgrade head   # schema and restricted app role
mise run //apps/api:dev                              # autoreload
```

- API: <http://localhost:8000> (interactive docs at `/docs`, health at `/healthz`)

No `.env` needed for this baseline — `apps/api`'s own config defaults already match the `docker-compose` setup above. You only need one if you're customizing something, e.g. real Authgear tokens instead of the test suite's fake JWKS server — see [docs/operations/local-authgear-setup.md](../operations/local-authgear-setup.md), and `.env.example`'s own header comment for a real gotcha: it needs copying to *two* places (repo root, for `docker compose`; `apps/api/.env`, for the app's own config), not one.

## The other apps

Every other app is built on top of `apps/api`, so start the API first. Each web frontend needs its own `.env` (copy its `.env.example`) with an Authgear client of its own, and the API has to allow the app's local origin through CORS; the app's README says how.

| App | Command | Local address |
| --- | --- | --- |
| [`apps/inventory-web`](../../apps/inventory-web) | `mise run //apps/inventory-web:dev` | <http://localhost:4321> (Astro's default port) |
| [`apps/account-hub`](../../apps/account-hub) | `mise run //apps/account-hub:dev` | <http://localhost:4322> |
| [`apps/beings`](../../apps/beings) | `mise run //apps/beings:dev` | <http://localhost:4323> |
| [`apps/calendars`](../../apps/calendars) | `mise run //apps/calendars:dev` | <http://127.0.0.1:4325> |
| [`apps/sessions`](../../apps/sessions) | `mise run //apps/sessions:dev` | port 4326 |
| [`apps/bench`](../../apps/bench) | `mise run //apps/bench:dev` | no fixed port (see below) |
| [`apps/loot-bot`](../../apps/loot-bot) | `mise run //apps/loot-bot:dev` | port 8090 (`LOOT_BOT_HTTP_PORT`), where Discord's interactions endpoint is served |

`apps/inventory-web` and `apps/bench` set no port of their own, so Astro's default, 4321, applies to both, and `apps/bench`'s `.env.example` expects that address. Run one of them at a time, or give the other a port (`mise run //apps/bench:dev -- --port 4324`) and register that address as a redirect URI on its Authgear client. The other web apps have fixed ports so that they can run side by side; 4324 is not used by any app.

`apps/cli` (the Python `lorenzo` command line, [ADR 0137](../adr/0137-lorenzo-cli-app-python-client-and-auth.md)) also uses the API: `mise run //apps/cli:dev -- --help` from a checkout, or `uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"` to have `lorenzo` on your path without one. See its README.

The two inventory companions are native apps. [`apps/inventory-mobile`](../../apps/inventory-mobile), Lorenzo Inventory for Android, needs a JDK and the Android SDK: follow its [JDK/SDK setup and local APK installation](../../apps/inventory-mobile/README.md#install-or-run), then connect through account hub. [`apps/inventory-ios`](../../apps/inventory-ios), Lorenzo Inventory for iOS, needs macOS with Xcode for its native checks; see its README.

What Calendars and Sessions do, from a user's side, is described in [Lorenzo Calendars](calendars.md) and [Lorenzo Sessions](sessions.md). For the shape of the whole system see [docs/architecture/overview.md](../architecture/overview.md); to add another app, see [docs/guides/adding-an-app.md](adding-an-app.md).

## Running tests

```bash
mise run test
```

Root tests also include inventory-mobile's JVM and Android unit tests. Install JDK 17 with `mise install` from `apps/inventory-mobile`, and set up its Android SDK before running root checks; no emulator is needed for unit tests.

`apps/api`'s `test_readyz` and `test_tracing` need the live Postgres container above; they're real connectivity checks, not mocked.

## Troubleshooting

- **`mise: command not found`** — install mise itself first; it's the one thing this repo can't install for you.
- **Postgres connection errors** — check `docker compose -f infra/docker-compose.yml ps` and that port `55432` isn't already in use by something else (`.env.example` explains why that port, not `5432`).
