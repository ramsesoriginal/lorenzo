# Architecture overview

## Components

Every deployable app lives under `apps/`, one directory per app, named by purpose rather than type — see [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md). Only `apps/api` exists so far. Its full domain model — the entity/component core (stats, prototypes, containment, information/payloads, item/item_instance, [ADR 0012](../adr/0012-entity-table.md)-[0019](../adr/0019-item-and-v-item.md)) plus tenant/user/membership, campaign/player, character/ownership, and campaign GM/orga ([ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)-[0026](../adr/0026-campaign-gm-orga-and-access-rule.md)) — and a read-only REST API plus Authgear-backed auth over it ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)/[0023](../adr/0023-authgear-token-verification.md)/[0027](../adr/0027-authgear-cloud-not-self-hosted.md)) both exist now - see the [domain model ER diagram](diagrams/domain-model-er.md).

| Component type | Role | Multiplicity |
| --- | --- | --- |
| Backend API | Source of truth. Multi-tenant REST API over PostgreSQL. | One — [`apps/api`](../../apps/api), read-only endpoints for entities/items/item instances/payloads, plus auth (`/me`) |
| Web frontend(s) | Static UI for GMs/players (zero-JS by default). | One or many |
| Discord bot(s) | Talks to the API — e.g. loot/inventory. | At least one, possibly more |
| Mobile app(s) | Talks to the API — narrower, audience-specific views. | Possibly more than one |

Everything other than the backend API is a *view* onto it — narrower, audience-specific slices of the same data, not a separate source of truth. See the [system context diagram](diagrams/system-context.md).

## Domain shape (why the data model will look the way it does)

The full picture — the layered world model, repositories, entities/knowledge/visibility, and how different client apps narrow all of it down — lives in [docs/domain](../domain), not here. This section is just the one-line technical summary: **where** something is (several independent, not-always-linear coordinate systems at once, not one hierarchy), **who knows what** (per-character, per-point-in-time, not global), and **who can see what** (every piece of text/stats split by audience).

The entity design itself is recorded in [RFC 0001](../rfcs/0001-core-domain-data-model.md) (the entity/component core) and [RFC 0002](../rfcs/0002-campaign-player-character-model.md) (campaign/player/character) — being built incrementally, smallest sub-slice first, starting with the bare `entity` table ([ADR 0012](../adr/0012-entity-table.md)). See the [domain model ER diagram](diagrams/domain-model-er.md) for how every table built so far actually connects.

## Cross-cutting concerns

- **Multi-tenancy**: [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md) — shared schema + PostgreSQL row-level security. The app's own connection is a restricted, non-superuser role RLS actually applies to ([ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)), locally, in CI, and in production — the live Neon role rotation is done and confirmed (not just deployed: the restricted role's privilege flags and `FORCE ROW LEVEL SECURITY` were checked directly against production Postgres).
- **Observability**: health/readiness/metrics and structured (`structlog`) JSON logs exist in `apps/api` from its first commit, as intended, now correlated with `trace_id`/`span_id` from the active OpenTelemetry span, plus OpenTelemetry tracing itself (console exporter — no collector in this project's infra yet). See [docs/architecture/observability.md](observability.md) for what each signal actually covers and what isn't wired up yet.
- **Auth**: [ADR 0009](../adr/0009-identity-provider-authgear.md)/[ADR 0023](../adr/0023-authgear-token-verification.md)/[ADR 0027](../adr/0027-authgear-cloud-not-self-hosted.md) — Authgear Cloud as the identity provider, with real OIDC bearer-token verification built and required on every tenant-scoped route.
- **Deployment**: [ADR 0011](../adr/0011-deploy-target-cloud-run-neon.md) — Google Cloud Run + Neon, continuously deployed on every push to `main` that touches `apps/api/` (`.github/workflows/deploy-api.yml`). Confirmed working end to end (2026-09-09): a real login through production Authgear Cloud, a real token, verified against the live deployed Cloud Run service, correctly auto-provisioned a real `app_user` row via `GET /me`. See [docs/architecture/deployment.md](deployment.md) for the components and how they connect, and [docs/operations/deployment-setup.md](../operations/deployment-setup.md) for the one-time account setup.

## Roadmap

Tracked as [GitHub issues/milestones](https://github.com/ramsesoriginal/lorenzo/issues) once there's something to track. Both vertical slices that were in progress are now built and merged to `main`: simple inventory management (entity/stats/information/payloads/prototypes/containment/item/item_instance, ADRs 0012-0019, plus a read-only REST API over all of it, [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)) and auth/users/campaigns/GM (Authgear, User/Tenant/Membership, Campaign/Player, Character/ownership, Campaign GM/orga — ADRs 0009/0021-0026, RFC 0002 accepted), plus production Authgear Cloud wiring (ADR 0027) and per-character/per-group/public information visibility ([ADR 0028](../adr/0028-knowledge-and-group-membership.md)) on top. Remaining, not yet built: RFC 0001's redaction-alternative open question (ADR 0028 built the authored-truths knowledge model; the "one truth, redacted per audience" alternative stays open), a fuller CRUD REST surface beyond read-only, campaign-scoped REST routes (the access rule itself is built - `campaign_access.can_access_campaign()` - just not wired to a route), and cross-tenant repositories ([docs/domain/repositories.md](../domain/repositories.md)).
