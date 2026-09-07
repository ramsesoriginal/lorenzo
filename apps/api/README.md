# apps/api

Lorenzo's backend REST API. Python, FastAPI, PostgreSQL (async SQLAlchemy + Alembic).

This is infrastructure only right now — health/readiness/metrics and DB connectivity, no domain models, no auth. See [ADR 0002](../../docs/adr/0002-multi-tenancy-shared-schema-rls.md) for the multi-tenancy approach this will grow into once there's an actual domain table.

## Run

```bash
mise run //apps/api:dev
```

or, from this directory: `uv run fastapi dev src/lorenzo_api/main.py`.

Needs Postgres — see [../../infra/docker-compose.yml](../../infra/docker-compose.yml) and [../../docs/guides/getting-started.md](../../docs/guides/getting-started.md).

## Test

```bash
mise run //apps/api:test
```

`test_readyz` needs a live Postgres — it's a real connectivity check, not mocked.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | liveness — no dependencies checked |
| GET | `/readyz` | readiness — checks the database |
| GET | `/metrics` | Prometheus |

Full interactive docs at `/docs` once running.

## Errors

Every error response — unhandled exceptions, request validation failures, `HTTPException`s including plain 404s — is [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) "Problem Details" (`application/problem+json`), via [fastapi-problem](https://github.com/NRWLDev/fastapi-problem/). No custom problem types yet; wired and proven (`tests/test_errors.py`), waiting for the first domain-specific error worth distinguishing.
