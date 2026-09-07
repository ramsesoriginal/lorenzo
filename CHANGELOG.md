# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Each app under `apps/` will be versioned and changelogged independently by release-please once it exists — see [docs/operations/releasing.md](docs/operations/releasing.md). This root file is a hand-curated, high-level narrative across the whole monorepo.

## [Unreleased]

### Added

- Repository foundation: monorepo layout, tooling (mise, pnpm workspace, pre-commit, release-please), CI/CD workflows, GitHub templates and ruleset, and ADRs recording the key decisions. See [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md) for how apps get added.
- `apps/api`: FastAPI backend infrastructure — health/readiness/metrics, async SQLAlchemy + Alembic wired to a real Postgres (`infra/docker-compose.yml`), mypy, RFC 9457 problem+json error responses, pagination wired (unused so far), OpenTelemetry tracing (console exporter). No domain models or auth yet.
- ADRs 0008–0010: taskiq + fastapi-limiter chosen but deferred until Redis is actually needed, Authgear as the identity provider, and the User/Tenant/Membership model — none of these three are built yet.
