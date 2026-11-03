# apps/api

Lorenzo's backend REST API. Python, FastAPI, PostgreSQL (async SQLAlchemy + Alembic).

Infrastructure (health/readiness/metrics, DB connectivity) plus the domain model and the surfaces listed under [Endpoints](#endpoints), tenant-scoped row-level security, and Authgear-backed auth — see [Domain model](#domain-model) and [Auth](#auth) below.

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

Full read/write REST API, tenant-scoped under `/tenants/{tenant_id}/...` — see [ADR 0020](../../docs/adr/0020-rest-api-tenant-scoping-and-schemas.md) for the scoping/schema conventions. The live `/docs` is the reference, so there is no endpoint table here (it would drift): see [docs/reference/README.md](../../docs/reference/README.md) for `/docs` and the static export you generate with `mise run //apps/api:openapi-schema`, and [docs/adr/README.md](../../docs/adr/README.md) for the ADR-by-ADR history of how each surface landed. The areas it covers:

| Area | Covers | Decided in |
| --- | --- | --- |
| Library core | entries, items and item instances, stats and computed stats, information and payloads, pictures, groups, knowledge, bulk entry export | [RFC 0001](../../docs/rfcs/0001-core-domain-data-model.md), [ADR 0262](../../docs/adr/0262-bulk-entity-export.md) |
| People | libraries (tenants), memberships, users, players, characters, campaigns, the activity log, invite links of every kind | [RFC 0002](../../docs/rfcs/0002-campaign-player-character-model.md), [ADR 0092](../../docs/adr/0092-campaign-invite-links.md), [ADR 0220](../../docs/adr/0220-one-invite-table-with-kinds.md) |
| Beings | a being's sheet, the stat vocabulary and sheet settings | [RFC 0043](../../docs/rfcs/0043-the-being-sheet.md) |
| Repositories | publishing, grants, browsing, copying and updates, releases, public reads, Discover, previews | [RFC 0024](../../docs/rfcs/0024-repositories.md), [RFC 0037](../../docs/rfcs/0037-releases-and-public-snapshots.md), [RFC 0038](../../docs/rfcs/0038-public-repositories-and-discovery.md) |
| Time | calendars, periods, observances, calendar imports, clocks, Events and their order | [ADR 0308](../../docs/adr/0308-authored-calendars-and-calculation.md) onward |
| Places | Locations, Maps, connections, distance, frames and axes | [RFC 0048](../../docs/rfcs/0048-locations-maps-connections-and-optional-dates.md) |
| Writing | Manuscripts, moves, splits, extraction and reviews | [RFC 0047](../../docs/rfcs/0047-lorenzo-writing.md) |
| Sessions | Sessions, Scenes, play and personal lived order | [RFC 0046](../../docs/rfcs/0046-sessions-scenes-and-lived-order.md) |
| Account and platform | personal access tokens and device authorization, app links, link previews, `admin` (platform operators only) | [ADR 0268](../../docs/adr/0268-personal-access-tokens-api.md), [ADR 0273](../../docs/adr/0273-app-links-registry.md), [ADR 0264](../../docs/adr/0264-link-previews.md) |

`/me` (current user + memberships), `/me/managed` (the tenants and campaigns the caller runs, [ADR 0086](../../docs/adr/0086-managed-scope-aggregate-and-notifications-since-filter.md)), `/me/changes` (what happened to things the caller's characters own or carry, [ADR 0099](../../docs/adr/0099-player-facing-change-feed.md)), `/me/sessions`, `/invites/{token}` (an unauthenticated preview and an authenticated redeem, [ADR 0092](../../docs/adr/0092-campaign-invite-links.md)), and `/healthz`/`/readyz`/`/metrics` sit outside tenant scoping. How an owner exports a tenant through these reads is in [docs/operations/exporting-your-tenant.md](../../docs/operations/exporting-your-tenant.md).

Settings are defined in [`config.py`](src/lorenzo_api/config.py); the ones set at deploy time are in [`.github/workflows/deploy-api.yml`](../../.github/workflows/deploy-api.yml).

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

Google Cloud Run + Neon, continuously — see [ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md). `.github/workflows/deploy-api.yml` builds, migrates, and deploys on every push to `main` that touches this app or the calendar and map engines it bundles (`packages/calendar-engine`, `packages/map-engine`). Confirmed working end to end (2026-09-09): the full domain model, the RLS-restricted role, and production Authgear Cloud ([ADR 0027](../../docs/adr/0027-authgear-cloud-not-self-hosted.md)) all verified together against the live deployed service — a real login, a real token, a real `GET /me` round-trip — see [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md).

See [docs/architecture/deployment.md](../../docs/architecture/deployment.md) for how the pieces connect, and [docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md) for the one-time setup.

## Sheet settings

`PATCH /tenants/{id}` accepts nullable `being_stat_group_id`, alongside `weapon_stat_group_id` and `ability_information_type`. A group must belong to that tenant; omitting a field preserves it and sending null clears it. Tenant administrators configure these settings. Deleting the selected group clears its reference while preserving the tenant.

The tenant detail and `GET /tenants/{id}/beings/{id}/sheet` return `being_stat_group_id`. The sheet's optional `campaign_id` must name a campaign in that tenant that the caller may read; it does not override the tenant setting. The API stores and returns the setting and does not filter stat reads; Beings uses it to choose the stats its sheet shows ([ADR 0296](../../docs/adr/0296-being-stat-group.md), [ADR 0297](../../docs/adr/0297-beings-stat-selection.md)).

## Information bundles

Information holds ordered text (LorenzoScript) and picture payloads under one audience.
`POST .../information/{id}/texts` appends text; `PUT .../information/{id}/payloads/order`
replaces the complete order. Both require the information ETag as `If-Match`. Text/picture
appends accept a stable payload id for retry-safe delivery. Text removal requires its own
payload ETag; picture callers may supply it too. Bytes are for tenant participants who can
read the information, with authorization repeated before a cached 304 ([ADR 0306](../../docs/adr/0306-information-bundles-and-their-editors.md)).

## Facts and their audiences

`fact` is an entry kind for a tenant-wide information anchor. New facts have a restricted
outer audience, controlling existence and name together. `GET`/`PUT .../entities/{id}/audience`
inspect and atomically replace it under `If-Match`. Information audiences are independent:
reading requires both gates. `.../entities/{fact}/about` lists explicit subjects; `PUT`/`DELETE`
on `about/{subject}` manage each edge, and `.../entities/{subject}/facts` lists visible facts.
Ancestry and LorenzoScript links remain independent of About ([ADR 0305](../../docs/adr/0305-facts-and-entry-audiences.md)).

## Authored calendars and dated entries

Calendars carry a versioned definition of segments, weeks and moons, independent of clocks or
story order ([ADR 0308](../../docs/adr/0308-authored-calendars-and-calculation.md)).
Definition updates require their own `If-Match`; preview/year reads calculate without writing.
Explicit period authoring creates/reuses structural year/month/day entries. Periods and Event
entries have restricted outer audiences by default; reading period coordinates also requires
visibility of their calendar. Ordinary dated notes are Information on one period. Entry date
associations are a separate n:m relation, replaced under the source entry's `If-Match`; they
assert no interval, chronology or historical truth ([ADR 0309](../../docs/adr/0309-calendar-periods-events-and-date-associations.md)).
Definition changes that erase recorded periods and deletion of referenced periods/calendars
are refused. Copies preserve local identities and remap structural/date links; definition
updates remain explicit and validate local periods.

Recurring observances are entries with one calendar-bound segment/day rule and optional
periodic years ([ADR 0310](../../docs/adr/0310-recurring-calendar-observances.md)). Occurrence reads calculate
visible results for a year, optionally filtered to a segment, without creating periods or
Events. Missing dates skip. Rule edits require the observance entry's ETag; definition edits
validate its rules too. Copied rule updates are explicit review fields. Release documents
carry the rules; every format change keeps the earlier formats readable ([ADR 0214](../../docs/adr/0214-the-release-document.md); the current number is `FORMAT` in [`release_document.py`](src/lorenzo_api/release_document.py)).

Calendar imports use read-only `POST .../calendar-imports/plan`, followed by atomic
`POST .../calendar-imports` with its token. The token covers tenant/calendar, file, choices,
versions and recorded periods; apply rechecks authorization and current state under locks.
A repeated successful request returns its receipt. Source keys and annotation bindings are
local tenant data with forced RLS and same-tenant references, explicitly excluded from repository
content. `GET .../calendar-imports/{source_key}/document` exports the current managed text source
with the same visibility/authoring checks. See the CLI's calendar-file workflow and ADR 0311.

## Explicit clocks

ADR 0320 adds optional `/tenants/{tenant_id}/clocks` entries, per-clock `/reckonings`, and
`/events/{event_id}/clock-readings`. Collection reads return ETags; reading/reckoning writes
require that collection's If-Match. Clock mode edits use the Clock ETag. Whole calendar days
convert to ranges through `/clocks/{clock_id}/date-reading`; `/reading-dates` formats a reading
without authoring periods. Rational strings preserve exact values and endpoint inclusion.

Timeless clocks reject readings and reckonings. Private relations and hidden endpoints are
filtered before returned lists and response versions. Existing period associations, current
knowledge grants and all ordering semantics stay unchanged. New clock content participates in
repository copy, explicit update review, release documents and purge. No clock is seeded.

ADR 0321 adds private/shared constant clock relationships with exact nonzero signed ratios and
optional paired anchors. `/clocks/{clock_id}/relationships` uses collection ETags;
`/relationship-preview` beneath a Clock previews an unsaved relationship. `/clock-conversions`
converts readings or durations, and `/events/{event_id}/clock-readings/{clock_id}/derived`
reads an Event through permitted relationships without saving inferred evidence. Responses
separate entered, derived, not-reckoned, conflicting and limit-reached results. Hidden sources
are filtered before traversal, provenance and work limits. Repository release documents carry
relationships; earlier formats remain readable.
