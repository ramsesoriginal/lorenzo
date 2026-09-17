<p align="center">
  <img src="docs/brand/assets/mascot_emblem_web.png" alt="Lorenzo leaning on a stack of Worlds, People, Places, Ideas, and Stories volumes, Catileo asleep on the open book beside them" width="200">
</p>

# ✧ Lorenzo

> World, campaign, and character bookkeeping for game masters, players, and authors — one tool for a single D&D one-shot or a shared multiverse.

[![CI](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml)
[![Security](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml)
[![Docs](https://github.com/ramsesoriginal/lorenzo/actions/workflows/docs.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/docs.yml)
[![License: AGPL-3.0](https://img.shields.io/github/license/ramsesoriginal/lorenzo)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Dependabot](https://img.shields.io/badge/dependabot-enabled-025E8C?logo=dependabot&logoColor=white)](.github/dependabot.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

[![Python](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](apps/api/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](apps/api/Dockerfile)

[![Node.js](https://img.shields.io/badge/node.js-22-339933?logo=node.js&logoColor=white)](apps/loot-bot/package.json)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)](apps/loot-bot/tsconfig.json)
[![discord.js](https://img.shields.io/badge/discord.js-5865F2?logo=discord&logoColor=white)](https://discord.js.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](apps/loot-bot/Dockerfile)

Lorenzo tracks the things a game master or worldbuilder actually juggles: where something is — physically, in space, across parallel planes, timelines, or whole multiverses — who knows what about whom, which shared settings ("repositories") a given game draws on, and the text, stats, and secrets attached to every item, being, and place, split by who's allowed to see it.

This repository is the monorepo for the whole project. `apps/api` exists with its full domain model (entity/component core plus tenant/campaign/player/character — see [ADR 0012](docs/adr/0012-entity-table.md) onward), a full read/write REST API over it, and Authgear-backed auth. `apps/loot-bot`, a Discord bot, is built on top of it, with its deploy pipeline wired up (Google Cloud Run, [ADR 0053](docs/adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)) pending its one-time GCP setup. Everything else is still structure and tooling. See [Roadmap](#roadmap).

| Component type | Role | Instances so far |
| --- | --- | --- |
| Backend API | Multi-tenant REST API, source of truth | [`apps/api`](apps/api) — domain model, full read/write REST API, Authgear auth |
| Web frontend(s) | Static UI, POSH + minimal JS | none yet — can be more than one |
| Discord bot(s) | Talks to the API | [`apps/loot-bot`](apps/loot-bot) — Discord account linking, self-service inventory viewing/managing, loot-splitting, GM loot drops with claims, and item awarding (see [ADR 0050](docs/adr/0050-loot-bot-stack-linking-and-isolation.md)/[0051](docs/adr/0051-loot-bot-give-command.md)/[0052](docs/adr/0052-loot-bot-loot-drop-and-claims.md)), deployed on Google Cloud Run over Discord's HTTP Interactions Endpoint ([ADR 0053](docs/adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)) |
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

`apps/api` itself has no UI — it's the backend. [`apps/loot-bot`](apps/loot-bot) is the first real, user-facing way to use the project, from Discord (`/inventory`, `/give`, `/drop`, and more — see its own README for the full command list). See [Roadmap](#roadmap) and [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) for how the next app (a frontend or mobile client) gets added.

## Configuration

[Quick start](#quick-start) above needs no `.env` — `apps/api`'s defaults already match `docker-compose`. Copy [.env.example](.env.example) to `.env` only to customize something, e.g. real Authgear tokens instead of the test suite's fake JWKS server — see [docs/guides/getting-started.md](docs/guides/getting-started.md) for where it needs to go (two places, not one). Each further app adds its own keys as it's scaffolded.

## Architecture

Start with [docs/architecture/overview.md](docs/architecture/overview.md) and the [system context diagram](docs/architecture/diagrams/system-context.md). Every non-obvious decision is recorded as an [ADR](docs/adr/README.md).

## Documentation

- [Domain](docs/domain/README.md) — what Lorenzo actually is, in plain language: the world model, repositories, entities/knowledge/visibility
- [Architecture](docs/architecture/overview.md) — the technical design
- [ADRs](docs/adr/README.md) — why things are the way they are
- [RFCs](docs/rfcs/README.md) — bigger proposals and open questions, not decided yet
- [Guides](docs/guides/README.md) — task-oriented how-tos
- [Operations](docs/operations/README.md) — releasing, GitHub setup
- [Reference](docs/reference/README.md) — API docs, configuration
- [Brand](docs/brand/README.md) — visual identity: logo, mascot, color, type, and voice

## Development

This repo is built structure-and-config-first: an app only gets real code once it's explicitly scoped, not speculatively. See [CONTRIBUTING.md](CONTRIBUTING.md) for the git/branch/commit strategy.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md) for supported versions and how to report a vulnerability.

## Roadmap

Tracked as [GitHub issues](https://github.com/ramsesoriginal/lorenzo/issues) and milestones. `apps/api`'s full domain model, auth, and REST write surface (item/item-instance, tenant, campaign, user/player/character, and information/payload/knowledge CRUD, plus effective stat resolution, campaign-scoped GM visibility, and production Authgear Cloud wiring) are built and merged to `main` — [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1)'s own end-to-end scenario passes against the real HTTP API. Further inventory-management and loot-handling gaps (concurrency tokens, stacking/splitting/merging, CORS, and more) are in progress on top of that. See [docs/architecture/overview.md](docs/architecture/overview.md#roadmap) for the detailed, ADR-by-ADR history.

## License

[AGPL-3.0](LICENSE) — if you run a modified version of this as a network service, you must offer its source to your users.
