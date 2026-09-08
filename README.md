# Lorenzo

> World, campaign, and character bookkeeping for game masters, players, and authors — one tool for a single D&D one-shot or a shared multiverse.

[![CI](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml)
[![Security](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml)
[![License: AGPL-3.0](https://img.shields.io/github/license/ramsesoriginal/lorenzo)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

Lorenzo tracks the things a game master or worldbuilder actually juggles: where something is — physically, in space, across parallel planes, timelines, or whole multiverses — who knows what about whom, which shared settings ("repositories") a given game draws on, and the text, stats, and secrets attached to every item, being, and place, split by who's allowed to see it.

This repository is the monorepo for the whole project. `apps/api` exists as infrastructure (health/readiness/metrics, DB connectivity), plus its first domain table (a bare `entity` — see [ADR 0012](docs/adr/0012-entity-table.md) — not yet meaningful on its own); no auth yet. Everything else is still structure and tooling. See [Roadmap](#roadmap).

| Component type | Role | Instances so far |
| --- | --- | --- |
| Backend API | Multi-tenant REST API, source of truth | [`apps/api`](apps/api) — infra + a first domain table, no auth yet |
| Web frontend(s) | Static UI, POSH + minimal JS | none yet — can be more than one |
| Discord bot(s) | Talks to the API | none yet — at least one is planned |
| Mobile app(s) | Talks to the API | none yet — can be more than one |

Each app lives under [`apps/`](apps/README.md) once it exists — see [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md).

## Quick start

```bash
mise install                                      # fetches the pinned toolchains
docker compose -f infra/docker-compose.yml up -d  # Postgres
mise run //apps/api:dev                            # apps/api, with autoreload
```

Then <http://localhost:8000/healthz> and <http://localhost:8000/docs>.

## Installation

See [docs/guides/getting-started.md](docs/guides/getting-started.md).

## Usage

Not yet — see [Roadmap](#roadmap) and [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) for how the first app gets added.

## Configuration

Copy [.env.example](.env.example) to `.env` — it already has the Postgres/`DATABASE_URL` values `apps/api` needs for local dev; each further app adds its own keys as it's scaffolded.

## Architecture

Start with [docs/architecture/overview.md](docs/architecture/overview.md) and the [system context diagram](docs/architecture/diagrams/system-context.md). Every non-obvious decision is recorded as an [ADR](docs/adr/README.md).

## Documentation

- [Domain](docs/domain/README.md) — what Lorenzo actually is, in plain language: the world model, repositories, entities/knowledge/visibility
- [Architecture](docs/architecture/overview.md) — the technical design
- [ADRs](docs/adr/README.md) — why things are the way they are
- [Guides](docs/guides/README.md) — task-oriented how-tos
- [Operations](docs/operations/README.md) — releasing, GitHub setup

## Development

This repo is built structure-and-config-first: an app only gets real code once it's explicitly scoped, not speculatively. See [CONTRIBUTING.md](CONTRIBUTING.md) for the git/branch/commit strategy.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md) for supported versions and how to report a vulnerability.

## Roadmap

Tracked as [GitHub issues](https://github.com/ramsesoriginal/lorenzo/issues) and milestones. Two vertical slices in progress in parallel: simple inventory management (`entity` landed, [ADR 0012](docs/adr/0012-entity-table.md); concrete types next) and auth/users (Authgear + the User/Tenant/Membership model, [ADR 0009](docs/adr/0009-identity-provider-authgear.md), [ADR 0010](docs/adr/0010-user-tenant-membership-model.md) — decided, not yet built).

## License

[AGPL-3.0](LICENSE) — if you run a modified version of this as a network service, you must offer its source to your users.
