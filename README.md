<p align="center">
  <img src="docs/brand/assets/mascot_emblem_web.png" alt="Lorenzo leaning on a stack of Worlds, People, Places, Ideas, and Stories volumes, Catileo asleep on the open book beside them" width="200">
</p>

# ✧ Lorenzo

> World, campaign, and character bookkeeping for game masters, players, and authors — one tool for a single D&D one-shot or a shared multiverse.

[![CI](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml)
[![Security](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml)
[![Docs](https://github.com/ramsesoriginal/lorenzo/actions/workflows/docs.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/docs.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ramsesoriginal/lorenzo)
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

[![Node.js](https://img.shields.io/badge/node.js-26-339933?logo=node.js&logoColor=white)](apps/loot-bot/package.json)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)](apps/loot-bot/tsconfig.json)
[![discord.js](https://img.shields.io/badge/discord.js-5865F2?logo=discord&logoColor=white)](https://discord.js.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](apps/loot-bot/Dockerfile)

[![Astro](https://img.shields.io/badge/Astro-BC52EE?logo=astro&logoColor=white)](apps/account-hub/package.json)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)](apps/account-hub/tsconfig.json)
[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare%20Pages-F38020?logo=cloudflarepages&logoColor=white)](docs/operations/deployment-setup.md)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)](apps/account-hub/playwright.config.ts)

[![Python](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](apps/cli/pyproject.toml)
[![Typer](https://img.shields.io/badge/Typer-CLI-009688)](https://typer.tiangolo.com)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![V8](https://img.shields.io/badge/V8-embedded-4B8BF5?logo=v8&logoColor=white)](docs/adr/0138-lorenzo-cli-js-host.md)

[![Android](https://img.shields.io/badge/Android-9%2B-3DDC84?logo=android&logoColor=white)](apps/inventory-mobile/README.md)
[![Kotlin](https://img.shields.io/badge/Kotlin-7F52FF?logo=kotlin&logoColor=white)](apps/inventory-mobile/gradle/libs.versions.toml)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-4285F4?logo=jetpackcompose&logoColor=white)](apps/inventory-mobile/app/build.gradle.kts)
[![Gradle](https://img.shields.io/badge/Gradle-02303A?logo=gradle&logoColor=white)](apps/inventory-mobile/gradle/wrapper/gradle-wrapper.properties)

[![iOS](https://img.shields.io/badge/iOS-17%2B-000000?logo=apple&logoColor=white)](apps/inventory-ios/README.md)
[![Swift](https://img.shields.io/badge/Swift-F05138?logo=swift&logoColor=white)](apps/inventory-ios/Package.swift)

Lorenzo tracks the things a game master or worldbuilder actually juggles: where something is — physically, in space, across parallel planes, timelines, or whole multiverses — who knows what about whom, which shared settings ("repositories") a given game draws on, and the text, stats, and secrets attached to every item, being, and place, split by who's allowed to see it.

This repository is the monorepo for the whole project: a multi-tenant REST API ([`apps/api`](apps/api)) and the apps built on it. Each app has its own README; what is decided and why is in the [ADRs](docs/adr/README.md), and what the finished product is meant to do is [v1.0.md](v1.0.md).

The shape is one API, several kinds of client, and shared code:

- **The API**, [`apps/api`](apps/api): the source of truth, on Google Cloud Run. It also says where the apps live (`GET /app-links`, [ADR 0273](docs/adr/0273-app-links-registry.md)).
- **Static web apps** for items, accounts, beings, calendars, sessions, writing and maps, and **Bench**, the authoring app: Astro and plain TypeScript, no component framework, all deployed to Cloudflare Pages through its Git integration.
- **A Discord bot**, on Google Cloud Run, and **the `lorenzo` command line** for bulk work and scripts.
- **Mobile apps** for Android and iOS, installed locally.
- **Shared packages**: the typed API client, the brand CSS, LorenzoScript and its editor, the calendar and map engines, and the other code more than one app uses.

[`apps/README.md`](apps/README.md) lists every app, what it is and where it runs; [`packages/README.md`](packages/README.md) lists every package. The one-time setup of each deployment is in [docs/operations](docs/operations/README.md). Further apps are added only when explicitly scoped ([docs/guides/adding-an-app.md](docs/guides/adding-an-app.md)).

## Quick start

```bash
mise install                                      # fetches the pinned toolchains
docker compose -f infra/docker-compose.yml up -d  # Postgres
uv run --directory apps/api alembic upgrade head   # schema and restricted app role
mise run //apps/api:dev                            # apps/api, with autoreload
```

Then <http://localhost:8000/healthz> and <http://localhost:8000/docs>.

## Installation

See [docs/guides/getting-started.md](docs/guides/getting-started.md).

## Usage

`apps/api` has no UI; it is the backend, with its live reference at `/docs`. Everything else talks to it.

| You want to | Use | Locally |
| --- | --- | --- |
| Manage a library's items and containers | [`apps/inventory-web`](apps/inventory-web) | `mise run //apps/inventory-web:dev`, port 4321 |
| Manage your account, libraries, campaigns, roster, repositories and access tokens | [`apps/account-hub`](apps/account-hub) | port 4322 |
| Read, play or edit a character or NPC | [`apps/beings`](apps/beings) | port 4323 |
| Keep a calendar, its dated notes and Events | [`apps/calendars`](apps/calendars) | port 4325 |
| Prepare a Session, its Scenes and notes | [`apps/sessions`](apps/sessions) | port 4326 |
| Write a standalone manuscript | [`apps/writing`](apps/writing) | port 4327 |
| Find, nest and open the Locations and Maps of a library | [`apps/maps`](apps/maps) | port 4328 |
| Write a repository's entries | [`apps/bench`](apps/bench) | `mise run //apps/bench:dev`, port 4321 (Astro's default, as `apps/inventory-web`: run one at a time) |
| Work from Discord (`/inventory`, `/give`, `/drop` and more) | [`apps/loot-bot`](apps/loot-bot) | see its README for the command list |
| Do bulk work the web apps don't | [`apps/cli`](apps/cli) | `uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"` |
| Carry inventories on a phone | [`apps/inventory-mobile`](apps/inventory-mobile) (Android), [`apps/inventory-ios`](apps/inventory-ios) (iOS) | follow their READMEs, then connect through account hub |

Each app's own README has its command list. With the CLI, `lorenzo tenant create`, `lorenzo seed` and `lorenzo apply` build a repository of standard items from MPMB files, and `lorenzo repo publish` and `lorenzo repo offer` hand it to a table's library (start with its [Before you start](apps/cli/README.md#before-you-start)). `lorenzo calendar import` brings in a calendar ([calendar file guide](docs/guides/calendar-file-format.md)). To bring in a D&D Beyond character's inventory, run [`uvx lorenzo-beyond`](https://github.com/ramsesoriginal/lorenzo-beyond) to write a ledger file, then `lorenzo inventory import` it. How a game master or player uses the apps is in the [guides](docs/guides/README.md).

## Configuration

[Quick start](#quick-start) above needs no `.env`: `apps/api`'s defaults already match `docker-compose`. Copy [.env.example](.env.example) to `.env` only to customize something, for example real Authgear tokens instead of the test suite's fake JWKS server; [docs/guides/getting-started.md](docs/guides/getting-started.md) says where it needs to go (two places, not one). Each web app and the bot reads its own `.env` (copy that app's `.env.example`): the API address and its Authgear client. The apps find each other through the API's `GET /app-links`, whose addresses default to the official ones; changing them is in [deployment-setup.md](docs/operations/deployment-setup.md).

## Architecture

Start with [docs/architecture/overview.md](docs/architecture/overview.md) and the [system context diagram](docs/architecture/diagrams/system-context.md). Every non-obvious decision is recorded as an [ADR](docs/adr/README.md).

## Documentation

- [Documentation index](docs/README.md) — where to look, by what you want to know
- [Domain](docs/domain/README.md) — what Lorenzo actually is, in plain language: the world model, repositories, entities/knowledge/visibility
- [Architecture](docs/architecture/overview.md) — the technical design
- [ADRs](docs/adr/README.md) — why things are the way they are
- [RFCs](docs/rfcs/README.md) — bigger proposals and open questions, before they become decisions
- [Guides](docs/guides/README.md) — task-oriented how-tos, including how to use Calendars and Sessions
- [v1.0](v1.0.md) — what the finished product is meant to do, and how far each row has got
- [Packages](packages/README.md) and [Apps](apps/README.md) — what is shared and what is deployed
- [Operations](docs/operations/README.md) — hosting each app, releasing, GitHub setup, going public
- [Reference](docs/reference/README.md) — API docs, configuration
- [Brand](docs/brand/README.md) — visual identity: logo, mascot, color, type, and voice

## Development

Apps and packages are added only once they are explicitly scoped, not speculatively. See [CONTRIBUTING.md](CONTRIBUTING.md) for the git/branch/commit strategy.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md) for supported versions and how to report a vulnerability.

## Roadmap

Tracked live as [GitHub issues](https://github.com/ramsesoriginal/lorenzo/issues) and [milestones](https://github.com/ramsesoriginal/lorenzo/milestones); [ADR 0070](docs/adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md) says how those relate to the RFC and ADR process. [v1.0.md](v1.0.md) lists, for every part of the system, what is built, what is partial and what is still to do. The API, its auth and REST write surface, the web apps, the bot, the CLI and the mobile apps described above are built and merged to `main`; the open work is mainly repository tooling (the rest of Bench's offline editing and public launch), the remaining clock, branching and historical-state parts of [RFC 0028](docs/rfcs/0028-time-causality-and-calendars.md), and operations, and Writing's joins. [docs/architecture/overview.md](docs/architecture/overview.md#roadmap) has the detailed, ADR-by-ADR history, and its [What's next](docs/architecture/overview.md#whats-next) says what is in flight.

## License

[AGPL-3.0](LICENSE) — if you run a modified version of this as a network service, you must offer its source to your users.
