# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Each app under `apps/` will be versioned and changelogged independently by release-please once it exists — see [docs/operations/releasing.md](docs/operations/releasing.md). This root file is a hand-curated, high-level narrative across the whole monorepo.

## [Unreleased]

### Added

- Repository foundation: monorepo layout, tooling (mise, pnpm workspace, pre-commit, release-please), CI/CD workflows, GitHub templates and ruleset, and ADRs recording the key decisions. See [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md) for how apps get added.
- `apps/api`: FastAPI backend infrastructure — health/readiness/metrics, async SQLAlchemy + Alembic wired to a real Postgres (`infra/docker-compose.yml`), mypy, RFC 9457 problem+json error responses, pagination, OpenTelemetry tracing (console exporter).
- `apps/api`'s full domain model (entity/component core plus tenant/user/membership, campaign/player, character/ownership, campaign GM/orga, knowledge/visibility — [ADR 0012](docs/adr/0012-entity-table.md) onward) and a full read/write REST API over it ([RFC 0001](docs/rfcs/0001-core-domain-data-model.md)/[RFC 0002](docs/rfcs/0002-campaign-player-character-model.md) and onward, landed as ADR 0020 and ADR 0030-0067) are built and merged to `main` — see [docs/architecture/overview.md](docs/architecture/overview.md#roadmap) for the detailed history.
- ADR 0008: taskiq + fastapi-limiter chosen but deferred until Redis is actually needed — still deferred. ADRs 0009/0010: Authgear as the identity provider, and the User/Tenant/Membership model — both built; real OIDC bearer-token verification is required on every tenant-scoped route ([ADR 0023](docs/adr/0023-authgear-token-verification.md)/[ADR 0027](docs/adr/0027-authgear-cloud-not-self-hosted.md)).
- ADR 0011 + CI/CD: `apps/api` now deploys continuously to Google Cloud Run + Neon Postgres on every push to `main` that touches it (`.github/workflows/deploy-api.yml`), with OIDC auth (no stored cloud credentials) and automated migrations. Confirmed live end to end.
- `apps/loot-bot`: a Discord bot built on top of `apps/api`'s write API — account linking, self-service inventory viewing/managing, loot-splitting, GM loot drops with claims, and item awarding ([ADR 0050](docs/adr/0050-loot-bot-stack-linking-and-isolation.md)/[0051](docs/adr/0051-loot-bot-give-command.md)/[0052](docs/adr/0052-loot-bot-loot-drop-and-claims.md)), deployed on Google Cloud Run over Discord's HTTP Interactions Endpoint ([ADR 0053](docs/adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)).
