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
mise run //apps/api:dev                              # autoreload
```

- API: <http://localhost:8000> (interactive docs at `/docs`, health at `/healthz`)

No `.env` needed for this baseline — `apps/api`'s own config defaults already match the `docker-compose` setup above. You only need one if you're customizing something, e.g. real Authgear tokens instead of the test suite's fake JWKS server — see [docs/operations/local-authgear-setup.md](../operations/local-authgear-setup.md), and `.env.example`'s own header comment for a real gotcha: it needs copying to *two* places (repo root, for `docker compose`; `apps/api/.env`, for the app's own config), not one.

Everything else under `apps/` is still unbuilt — see [docs/guides/adding-an-app.md](adding-an-app.md) for what that takes, and [docs/architecture/overview.md](../architecture/overview.md) for the intended shape of the whole system.

## Running tests

```bash
mise run test
```

`apps/api`'s `test_readyz` and `test_tracing` need the live Postgres container above; they're real connectivity checks, not mocked.

## Troubleshooting

- **`mise: command not found`** — install mise itself first; it's the one thing this repo can't install for you.
- **Postgres connection errors** — check `docker compose -f infra/docker-compose.yml ps` and that port `55432` isn't already in use by something else (`.env.example` explains why that port, not `5432`).
