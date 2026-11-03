# Architecture overview

## Components

Every deployable app lives under `apps/`, one directory per app, named by purpose rather than type — see [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md). [apps/README.md](../../apps/README.md) lists the apps and [packages/README.md](../../packages/README.md) the shared packages; this table gives only the types, their roles and how many of each there are. How the pieces connect is in the [system context diagram](diagrams/system-context.md), what the API stores is in the [domain model ER diagram](diagrams/domain-model-er.md).

| Component type | Role | Multiplicity |
| --- | --- | --- |
| Backend API | Source of truth. Multi-tenant REST API over PostgreSQL, with Authgear-backed auth and personal access tokens. | One — [`apps/api`](../../apps/api) |
| Web frontend(s) | Static UI for GMs and players (zero-JS by default), one app per purpose ([ADR 0004](../adr/0004-static-astro-frontend.md), [ADR 0071](../adr/0071-account-hub-stack-auth-deploy.md)). | One per purpose, more as they are scoped |
| Authoring app | Repository content editing through the API. | One — [`apps/bench`](../../apps/bench); persistent offline work remains a later slice of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) |
| Brand site | Shared identity assets and preview. | One — [`apps/brand`](../../apps/brand), consumed through `packages/brand` |
| Discord bot(s) | Talks to the API — loot and inventory. Runs on Google Cloud Run over Discord's HTTP Interactions Endpoint rather than its Gateway ([ADR 0053](../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)). | One today — [`apps/loot-bot`](../../apps/loot-bot); more bots are possible |
| Command line | Talks to the API — bulk import, repositories and scripting. | One — [`apps/cli`](../../apps/cli), the `lorenzo` tool ([ADR 0137](../adr/0137-lorenzo-cli-app-python-client-and-auth.md)) |
| Converter(s) | Standalone tools that turn another source into a Lorenzo file, never talking to the API. | [`packages/converters`](../../packages/converters) (`lorenzo-convert`); outside this repository, [`lorenzo-beyond`](https://github.com/ramsesoriginal/lorenzo-beyond) ([PyPI](https://pypi.org/project/lorenzo-beyond/)), a public D&D Beyond character's inventory as a LorenzoLedger ([ADR 0226](../adr/0226-lorenzoledger.md)) |
| Mobile app(s) | Native clients of the REST API, installed locally rather than from a store. | One per platform — [`apps/inventory-mobile`](../../apps/inventory-mobile) (Android, [ADR 0291](../adr/0291-inventory-mobile-native-android-app.md)), [`apps/inventory-ios`](../../apps/inventory-ios) ([ADR 0307](../adr/0307-inventory-ios-and-altstore-testing.md)) |
| Shared packages | Generic libraries extracted from the apps, each independently versioned; the API image bundles `calendar-engine` and `map-engine`. | Many — [packages/README.md](../../packages/README.md) |

Everything other than the backend API is a *view* onto it — narrower, audience-specific slices of the same data, not a separate source of truth.

## Domain shape (why the data model will look the way it does)

The full picture — the layered world model, repositories, entities/knowledge/visibility, and how different client apps narrow all of it down — lives in [docs/domain](../domain), not here. This section is just the one-line technical summary: **where** something is (several independent, not-always-linear coordinate systems at once, not one hierarchy), **who knows what** (per-character, per-point-in-time, not global), and **who can see what** (every piece of text/stats split by audience).

The entity design itself is recorded in [RFC 0001](../rfcs/0001-core-domain-data-model.md) (the entity/component core) and [RFC 0002](../rfcs/0002-campaign-player-character-model.md) (campaign/player/character), built as a series of small sub-slices starting with the bare `entity` table ([ADR 0012](../adr/0012-entity-table.md)). See the [domain model ER diagram](diagrams/domain-model-er.md) for how the stored tables connect.

## Cross-cutting concerns

- **Multi-tenancy**: [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md) — shared schema + PostgreSQL row-level security. The app's own connection is a restricted, non-superuser role RLS actually applies to ([ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)), locally, in CI, and in production — the live Neon role rotation is done and confirmed (not just deployed: the restricted role's privilege flags and `FORCE ROW LEVEL SECURITY` were checked directly against production Postgres).
- **Observability**: health/readiness/metrics and structured (`structlog`) JSON logs exist in `apps/api` from its first commit, as intended, correlated with `trace_id`/`span_id` from the active OpenTelemetry span, plus OpenTelemetry tracing itself (console exporter — no collector in this project's infra yet). See [docs/architecture/observability.md](observability.md) for what each signal actually covers and what isn't wired up yet.
- **Auth**: [ADR 0009](../adr/0009-identity-provider-authgear.md)/[ADR 0023](../adr/0023-authgear-token-verification.md)/[ADR 0027](../adr/0027-authgear-cloud-not-self-hosted.md) — Authgear Cloud as the identity provider, with real OIDC bearer-token verification built and required on every tenant-scoped route; personal access tokens and the device-code flow ([ADR 0268](../adr/0268-personal-access-tokens-api.md)) are the other way in, for the command line and the native apps.
- **Deployment**: [ADR 0011](../adr/0011-deploy-target-cloud-run-neon.md) — Google Cloud Run + Neon, continuously deployed on every push to `main` that touches `apps/api/`, `packages/calendar-engine/` or `packages/map-engine/`, which the API image bundles (`.github/workflows/deploy-api.yml`). Confirmed working end to end (2026-09-09): a real login through production Authgear Cloud, a real token, verified against the live deployed Cloud Run service, correctly auto-provisioned a real `app_user` row via `GET /me`. `apps/loot-bot` shares the same Cloud Run/GCP project, but first needed its transport rewritten off the Discord Gateway onto Discord's HTTP Interactions Endpoint to fit Cloud Run's scale-to-zero model at all ([ADR 0053](../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)); it deploys on every push to `main` that touches `apps/loot-bot/` or `packages/api-client/` (`.github/workflows/deploy-loot-bot.yml`), with one-time GCP setup described in [docs/operations/deployment-setup.md](../operations/deployment-setup.md). The static web apps deploy through Cloudflare Pages' own Git integration, outside GitHub Actions. See [docs/architecture/deployment.md](deployment.md) for the components and how they connect.

## Roadmap

[Roadmap history](roadmap-history.md) is the chronicle of what shipped, in order, each fact tied to the ADR that decided it. It is append-only and holds only what has already landed.

### What's next

What is in flight lives in GitHub's own tracker, not in this file: see open [Issues](https://github.com/ramsesoriginal/lorenzo/issues) and [Milestones](https://github.com/ramsesoriginal/lorenzo/milestones) (`gh issue list --state open`). Per [ADR 0070](../adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md), that live state belongs there, not in hand-maintained prose.
