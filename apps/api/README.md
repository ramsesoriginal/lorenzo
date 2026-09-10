# apps/api

Lorenzo's backend REST API. Python, FastAPI, PostgreSQL (async SQLAlchemy + Alembic).

Infrastructure (health/readiness/metrics, DB connectivity) plus the full [RFC 0001](../../docs/rfcs/0001-core-domain-data-model.md)/[RFC 0002](../../docs/rfcs/0002-campaign-player-character-model.md) domain model, tenant-scoped row-level security, and Authgear-backed auth — see [Domain model](#domain-model) and [Auth](#auth) below.

## Run

```bash
mise run //apps/api:dev
```

or, from this directory: `uv run fastapi dev src/lorenzo_api/main.py`.

Needs Postgres — see [../../infra/docker-compose.yml](../../infra/docker-compose.yml) and [../../docs/guides/getting-started.md](../../docs/guides/getting-started.md). A local Authgear instance is only needed to exercise real token verification end to end — see [docs/operations/local-authgear-setup.md](../../docs/operations/local-authgear-setup.md); the test suite uses a fake JWKS server instead.

## Test

```bash
mise run //apps/api:test
```

`test_readyz`, the RLS-isolation tests, and the auth tests all need a live Postgres — real checks, not mocked.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/healthz` | liveness — no dependencies checked |
| GET | `/readyz` | readiness — checks the database |
| GET | `/metrics` | Prometheus |
| GET | `/me` | current authenticated user + their tenant memberships |
| GET | `/tenants/{tenant_id}/entities` | paginated |
| GET | `/tenants/{tenant_id}/entities/{entity_id}` | detail: stats, information, prototypes, parent/children |
| GET | `/tenants/{tenant_id}/items` | paginated |
| GET | `/tenants/{tenant_id}/items/{entity_id}` | detail |
| GET | `/tenants/{tenant_id}/item-instances` | paginated; `container_id`/`recursive` filters |
| GET | `/tenants/{tenant_id}/item-instances/{entity_id}` | detail |
| GET | `/tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}` | grouped by direct container |
| GET | `/tenants/{tenant_id}/payloads/{payload_id}/content` | binary content, correct `Content-Type`/`Content-Disposition` |

All read-only (`GET`) so far — see [ADR 0020](../../docs/adr/0020-rest-api-tenant-scoping-and-schemas.md). Full interactive docs at `/docs` once running.

## Auth

Bearer-token auth against Authgear (OIDC) — [ADR 0009](../../docs/adr/0009-identity-provider-authgear.md)/[ADR 0023](../../docs/adr/0023-authgear-token-verification.md). A verified token's `sub` auto-provisions an `app_user` row on first use. Every `/tenants/{tenant_id}/...` route also requires a `Membership` row for that user in that tenant — the same 404 either way, whether the tenant doesn't exist or the caller just isn't a member of it. `GET /me` is the one route that isn't tenant-scoped, by design.

## Domain model

The full domain model from [RFC 0001](../../docs/rfcs/0001-core-domain-data-model.md) (entity/component core: stats, inheritance prototypes, containment, information/payloads, item/item_instance) and [RFC 0002](../../docs/rfcs/0002-campaign-player-character-model.md) (tenant/user/membership, campaign/player, character/ownership, campaign GM/orga) is built — see [docs/architecture/diagrams/domain-model-er.md](../../docs/architecture/diagrams/domain-model-er.md) for the merged picture and [docs/adr/README.md](../../docs/adr/README.md) for the full ADR-by-ADR history. RFC 0001's `knowledge`/group-membership/public-information system is built too ([ADR 0028](../../docs/adr/0028-knowledge-and-group-membership.md)); its redaction-alternative open question — "one truth, redacted per audience" instead of the authored-truths model ADR 0028 built — is what's left.

Every tenant-scoped table has row-level security, and — as of [ADR 0021](../../docs/adr/0021-restricted-app-role-for-rls-enforcement.md) — the app's own DB role is a properly restricted, non-superuser role that RLS actually applies to (a real, previously-live gap, not just a hardening exercise), in production too — the live Neon role rotation is done and confirmed directly against production, not just deployed; see [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md).

`campaign_access.can_access_campaign()` implements RFC 0002's campaign-visibility rule directly (a `player` row, a `campaign_gm` row, or tenant-`orga` without an opt-out) — not yet wired into a route, since no campaign-scoped endpoint exists yet.

## Errors

Every error response — unhandled exceptions, request validation failures, `HTTPException`s including plain 404s — is [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) "Problem Details" (`application/problem+json`), via [fastapi-problem](https://github.com/NRWLDev/fastapi-problem/). Typed subclasses exist for every domain-specific case worth distinguishing (tenant/entity/item/item-instance/payload not-found, invalid bearer token) — see `src/lorenzo_api/exceptions.py`.

## Pagination

[fastapi-pagination](https://github.com/uriyyo/fastapi-pagination) (`add_pagination(app)` in `main.py`) backs every list endpoint above, returning `Page[...]`.

## Logging

Structured JSON logging via `structlog` (`src/lorenzo_api/logging.py`), with `trace_id`/`span_id` injected from the active OpenTelemetry span so a log line can be correlated with the request that produced it.

## Tracing

OpenTelemetry instruments FastAPI (HTTP spans) and SQLAlchemy (query spans) — see `src/lorenzo_api/observability/tracing.py`. Exports to the console only, on purpose: there's no trace collector anywhere in this project's infrastructure yet, and adding the OTLP exporter for a collector that doesn't exist isn't something that could actually be verified. `tests/test_tracing.py` proves real spans are produced, not just that setup code runs without erroring. When there's a real collector to point at: add `opentelemetry-exporter-otlp`, export via OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

See [docs/architecture/observability.md](../../docs/architecture/observability.md) for logs, metrics, and health checks too.

## Deployment

Google Cloud Run + Neon, continuously — see [ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md). `.github/workflows/deploy-api.yml` builds, migrates, and deploys on every push to `main` that touches this directory. Confirmed working end to end (2026-09-09): the full domain model, the RLS-restricted role, and production Authgear Cloud ([ADR 0027](../../docs/adr/0027-authgear-cloud-not-self-hosted.md)) all verified together against the live deployed service — a real login, a real token, a real `GET /me` round-trip — see [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md).

See [docs/architecture/deployment.md](../../docs/architecture/deployment.md) for how the pieces connect, and [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md) for the one-time setup.
