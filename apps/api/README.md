# apps/api

Lorenzo's backend REST API. Python, FastAPI, PostgreSQL (async SQLAlchemy + Alembic).

Infrastructure (health/readiness/metrics, DB connectivity), plus the first domain table — a bare `entity` (see [ADR 0012](../../docs/adr/0012-entity-table.md)), not yet meaningful on its own. No auth yet.

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
| --- | --- | --- |
| GET | `/healthz` | liveness — no dependencies checked |
| GET | `/readyz` | readiness — checks the database |
| GET | `/metrics` | Prometheus |

Full interactive docs at `/docs` once running.

## Domain model

Being built as a series of small, tested sub-slices, per [RFC 0001](../../docs/rfcs/0001-core-domain-data-model.md) (entity/component core) and [RFC 0002](../../docs/rfcs/0002-campaign-player-character-model.md) (campaign/player/character) — [ADR 0012](../../docs/adr/0012-entity-table.md) is the first, just the bare `entity` table with real (if not yet fully enforced — see that ADR) row-level security. Concrete types (`item`, `being`, `place`) are next.

## Errors

Every error response — unhandled exceptions, request validation failures, `HTTPException`s including plain 404s — is [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) "Problem Details" (`application/problem+json`), via [fastapi-problem](https://github.com/NRWLDev/fastapi-problem/). No custom problem types yet; wired and proven (`tests/test_errors.py`), waiting for the first domain-specific error worth distinguishing.

## Pagination

[fastapi-pagination](https://github.com/uriyyo/fastapi-pagination) is wired (`add_pagination(app)` in `main.py`) but unused so far — there's no list endpoint yet. The first one that needs paging returns `Page[...]` and gets it for free.

## Tracing

OpenTelemetry instruments FastAPI (HTTP spans) and SQLAlchemy (query spans) — see `src/lorenzo_api/observability/tracing.py`. Exports to the console only, on purpose: there's no trace collector anywhere in this project's infrastructure yet, and adding the OTLP exporter for a collector that doesn't exist isn't something that could actually be verified. `tests/test_tracing.py` proves real spans are produced, not just that setup code runs without erroring. When there's a real collector to point at: add `opentelemetry-exporter-otlp`, export via OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

See [docs/architecture/observability.md](../../docs/architecture/observability.md) for logs, metrics, and health checks too.

## Deployment

Google Cloud Run + Neon, continuously — see [ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md). `.github/workflows/deploy-api.yml` builds, migrates, and deploys on every push to `main` that touches this directory. Confirmed working end to end; live at the URL Cloud Run assigns (see the GCP Console — not hardcoded here since it isn't a secret but does depend on your own project setup).

See [docs/architecture/deployment.md](../../docs/architecture/deployment.md) for how the pieces connect, and [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md) for the one-time setup.
