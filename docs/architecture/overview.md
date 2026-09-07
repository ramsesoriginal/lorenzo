# Architecture overview

## Components

Every deployable app lives under `apps/`, one directory per app, named by purpose rather than type — see [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md). Only `apps/api` exists so far, as infrastructure (no domain models yet).

| Component type | Role | Multiplicity |
| --- | --- | --- |
| Backend API | Source of truth. Multi-tenant REST API over PostgreSQL. | One — [`apps/api`](../../apps/api) exists (infra only) |
| Web frontend(s) | Static UI for GMs/players (zero-JS by default). | One or many |
| Discord bot(s) | Talks to the API — e.g. loot/inventory. | At least one, possibly more |
| Mobile app(s) | Talks to the API — narrower, audience-specific views. | Possibly more than one |

Everything other than the backend API is a *view* onto it — narrower, audience-specific slices of the same data, not a separate source of truth. See the [system context diagram](diagrams/system-context.md).

## Domain shape (why the data model will look the way it does)

The full picture — the layered world model, repositories, entities/knowledge/visibility, and how different client apps narrow all of it down — lives in [docs/domain](../domain), not here. This section is just the one-line technical summary: **where** something is (several independent, not-always-linear coordinate systems at once, not one hierarchy), **who knows what** (per-character, per-point-in-time, not global), and **who can see what** (every piece of text/stats split by audience).

None of this is modeled as a schema yet — no ADR/RFC for the entity design. That's real design work for when the backend API is actually scoped, not something to improvise into this foundation pass.

## Cross-cutting concerns (intentions, not yet built)

- **Multi-tenancy**: [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md) — shared schema + PostgreSQL row-level security. Not implemented yet — `apps/api` has no domain tables to scope.
- **Observability**: health/readiness/metrics and structured logs exist in `apps/api` from its first commit, as intended, plus OpenTelemetry tracing (console exporter — no collector in this project's infra yet).
- **Auth**: [ADR 0009](../adr/0009-identity-provider-authgear.md) decided Authgear as the identity provider; not built yet.
- **Deployment**: [ADR 0011](../adr/0011-deploy-target-cloud-run-neon.md) — Google Cloud Run + Neon, continuously deployed on every push to `main` that touches `apps/api/` (`.github/workflows/deploy-api.yml`). Needs one-time setup — see [docs/operations/deployment-setup.md](../operations/deployment-setup.md).

## Roadmap

Tracked as [GitHub issues/milestones](https://github.com/ramsesoriginal/lorenzo/issues) once there's something to track. Immediate next step: Authgear + the User/Tenant/Membership model ([ADR 0009](../adr/0009-identity-provider-authgear.md), [ADR 0010](../adr/0010-user-tenant-membership-model.md)) — decided, not yet built.
