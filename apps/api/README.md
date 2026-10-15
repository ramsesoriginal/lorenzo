# apps/api

Lorenzo's backend REST API. Python, FastAPI, PostgreSQL (async SQLAlchemy + Alembic).

Infrastructure (health/readiness/metrics, DB connectivity) plus the full [RFC 0001](../../docs/rfcs/0001-core-domain-data-model.md)/[RFC 0002](../../docs/rfcs/0002-campaign-player-character-model.md) domain model, tenant-scoped row-level security, and Authgear-backed auth — see [Domain model](#domain-model) and [Auth](#auth) below.

## Run

```bash
mise run //apps/api:dev
```

or, from this directory: `uv run fastapi dev src/lorenzo_api/main.py`.

Before the first run, start Postgres and apply `uv run --directory apps/api alembic upgrade head` from the repo root; the dev task does not migrate automatically. See [../../infra/docker-compose.yml](../../infra/docker-compose.yml) and [../../docs/guides/getting-started.md](../../docs/guides/getting-started.md). An Authgear Cloud development project is needed for an interactive login — see [docs/operations/local-authgear-setup.md](../../docs/operations/local-authgear-setup.md); the test suite uses a fake JWKS server instead.

## Test

```bash
mise run //apps/api:test
```

`test_readyz`, the RLS-isolation tests, and the auth tests all need a live Postgres — real checks, not mocked.

The tests run on `TEST_WORKERS` parallel workers, four by default and `TEST_WORKERS=0` for one process (a single test, a debugger). Each worker has a database of its own, cloned from a template that one of them migrates and dropped when the worker finishes, so the Postgres user needs to be able to create databases, as the compose one can (`tests/_workers.py`, ADR 0148). A run without workers uses the database it is given.

## Endpoints

Full read/write REST API, tenant-scoped under `/tenants/{tenant_id}/...` — see [ADR 0020](../../docs/adr/0020-rest-api-tenant-scoping-and-schemas.md) for the scoping/schema conventions. Routers under `src/lorenzo_api/routers/`: `entities`, `items`/`item_instances`, `payloads`/`information`, `stats`/`entity_stats`/`computed_stats`, `campaigns`, `campaign_invites`, `tenant_invites` (an Owner's role and library-access links, [ADR 0220](../../docs/adr/0220-one-invite-table-with-kinds.md)), `players`, `characters`, `groups`, `tenants`, `repositories` (repository publishing, grants, browsing, copying, and updates, [RFC 0024](../../docs/rfcs/0024-repositories.md)), `users`, `activity_log`, `knowledge`, plus repository profiles, releases, public reads, Discover and previews (RFC 0037/0038), bulk entity export (ADR 0262), personal tokens and device authorization (ADR 0268), app links (ADR 0273), `admin` (platform-operator only), `pictures`, and `invites` (the public side of invite links of every kind). `/me` (current user + memberships), `/me/managed` (the tenants and campaigns the caller runs, [ADR 0086](../../docs/adr/0086-managed-scope-aggregate-and-notifications-since-filter.md)), `/me/changes` (what happened to things the caller's characters own or carry, [ADR 0099](../../docs/adr/0099-player-facing-change-feed.md)), `/invites/{token}` (an unauthenticated preview and an authenticated redeem, [ADR 0092](../../docs/adr/0092-campaign-invite-links.md)), and `/healthz`/`/readyz`/`/metrics` sit outside tenant scoping. How an owner exports a tenant through these reads is in [docs/operations/exporting-your-tenant.md](../../docs/operations/exporting-your-tenant.md). This list is deliberately not an exhaustive endpoint table — that duplicates and drifts from the generated source of truth; see [docs/reference/README.md](../../docs/reference/README.md) for the live `/docs` and the static `openapi.json` export, and [docs/adr/README.md](../../docs/adr/README.md) for the ADR-by-ADR history of how each surface landed.

## Auth

Bearer-token auth verifies Authgear Cloud access tokens ([ADR 0023](../../docs/adr/0023-authgear-token-verification.md), [ADR 0027](../../docs/adr/0027-authgear-cloud-not-self-hosted.md)); a verified subject auto-provisions an `app_user` row on first use. Personal access tokens also authenticate as their owner, except for platform operations and token management ([ADR 0268](../../docs/adr/0268-personal-access-tokens-api.md)).

Tenant-scoped authorization depends on the route: library membership, campaign participation, GM reach or character control. Players and GMs need not have a tenant-wide membership to use their permitted routes. Repository reads use the explicit read gate; public visitor routes require sign-in and are subject to the preview rules and the public-repository feature switch (ADR 0287, 0290, 0293). Administrative writes use the Owner/Organizer gate; the Author role grants content authoring without library administration (ADR 0219). A hidden resource is answered as not found.

## Domain model

The full domain model from [RFC 0001](../../docs/rfcs/0001-core-domain-data-model.md) (entity/component core: stats, inheritance prototypes, containment, information/payloads, item/item_instance) and [RFC 0002](../../docs/rfcs/0002-campaign-player-character-model.md) (tenant/user/membership, campaign/player, character/ownership, campaign GM/orga) is built — see [docs/architecture/diagrams/domain-model-er.md](../../docs/architecture/diagrams/domain-model-er.md) for the merged picture and [docs/adr/README.md](../../docs/adr/README.md) for the full ADR-by-ADR history. RFC 0001's `knowledge`/group-membership/public-information system is built too ([ADR 0028](../../docs/adr/0028-knowledge-and-group-membership.md)); its redaction-alternative open question — "one truth, redacted per audience" instead of the authored-truths model ADR 0028 built — is what's left.

Every tenant-scoped table has row-level security, and — as of [ADR 0021](../../docs/adr/0021-restricted-app-role-for-rls-enforcement.md) — the app's own DB role is a properly restricted, non-superuser role that RLS actually applies to (a real, previously-live gap, not just a hardening exercise), in production too — the live Neon role rotation is done and confirmed directly against production, not just deployed; see [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md).

`campaign_access.can_access_campaign()` implements RFC 0002's campaign-visibility rule directly (a `player` row, a `campaign_gm` row, or tenant-`orga` without an opt-out) — wired into `routers/campaigns.py`'s campaign-scoped routes ([ADR 0034](../../docs/adr/0034-campaign-crud-api.md)/[0035](../../docs/adr/0035-campaign-scoped-gm-visibility.md)).

## Errors

Every error response — unhandled exceptions, request validation failures, `HTTPException`s including plain 404s — is [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) "Problem Details" (`application/problem+json`), via [fastapi-problem](https://github.com/NRWLDev/fastapi-problem/). Typed subclasses exist for every domain-specific case worth distinguishing (tenant/entity/item/item-instance/payload not-found, invalid bearer token) — see `src/lorenzo_api/exceptions.py`.

## Pagination

[fastapi-pagination](https://github.com/uriyyo/fastapi-pagination) (`add_pagination(app)` in `main.py`) backs ordinary paginated lists, returning `Page[...]`. Some reads return a plain array (campaign GMs and group members), and the bulk entity export uses `items`, `revision` and `next_cursor` instead (ADR 0262). See the generated schema for each route's actual shape.

## Logging

Structured JSON logging via `structlog` (`src/lorenzo_api/logging.py`), with `trace_id`/`span_id` injected from the active OpenTelemetry span so a log line can be correlated with the request that produced it.

## Tracing

OpenTelemetry instruments FastAPI (HTTP spans) and SQLAlchemy (query spans) — see `src/lorenzo_api/observability/tracing.py`. Exports to the console only, on purpose: there's no trace collector anywhere in this project's infrastructure yet, and adding the OTLP exporter for a collector that doesn't exist isn't something that could actually be verified. `tests/test_tracing.py` proves real spans are produced, not just that setup code runs without erroring. When there's a real collector to point at: add `opentelemetry-exporter-otlp`, export via OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

See [docs/architecture/observability.md](../../docs/architecture/observability.md) for logs, metrics, and health checks too.

## Deployment

Google Cloud Run + Neon, continuously — see [ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md). `.github/workflows/deploy-api.yml` builds, migrates, and deploys on every push to `main` that touches this directory. Confirmed working end to end (2026-09-09): the full domain model, the RLS-restricted role, and production Authgear Cloud ([ADR 0027](../../docs/adr/0027-authgear-cloud-not-self-hosted.md)) all verified together against the live deployed service — a real login, a real token, a real `GET /me` round-trip — see [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md).

See [docs/architecture/deployment.md](../../docs/architecture/deployment.md) for how the pieces connect, and [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md) for the one-time setup.

## Sheet settings

`PATCH /tenants/{id}` accepts nullable `being_stat_group_id`, alongside `weapon_stat_group_id` and `ability_information_type`. A group must belong to that tenant; omitting a field preserves it and sending null clears it. Tenant administrators configure these settings. Deleting the selected group clears its reference while preserving the tenant.

The tenant detail and `GET /tenants/{id}/beings/{id}/sheet` return `being_stat_group_id`. The sheet's optional `campaign_id` must name a campaign in that tenant that the caller may read; it does not override the tenant setting yet. The setting does not filter stat reads or change frontend display ([ADR 0296](../../docs/adr/0296-being-stat-group.md)).
