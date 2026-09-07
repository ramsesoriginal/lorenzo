# Lorenzo

> World, campaign, and character bookkeeping for game masters, players, and authors — one tool for a single D&D one-shot or a shared multiverse.

[![CI](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/ci.yml)
[![Security](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml/badge.svg)](https://github.com/ramsesoriginal/lorenzo/actions/workflows/security.yml)
[![License: AGPL-3.0](https://img.shields.io/github/license/ramsesoriginal/lorenzo)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

Lorenzo tracks the things a game master or worldbuilder actually juggles: where something is — physically, in space, across parallel planes, timelines, or whole multiverses — who knows what about whom, which shared settings ("repositories") a given game draws on, and the text, stats, and secrets attached to every item, being, and place, split by who's allowed to see it.

This repository is the monorepo for the whole project. It is currently at the **structure and tooling stage** — no application code exists yet. See [Roadmap](#roadmap).

| Component type | Role | Instances so far |
|---|---|---|
| Backend API | Multi-tenant REST API, source of truth | none yet |
| Web frontend(s) | Static UI, POSH + minimal JS | none yet — can be more than one |
| Discord bot(s) | Talks to the API | none yet — at least one is planned |
| Mobile app(s) | Talks to the API | none yet — can be more than one |

Each app lives under [`apps/`](apps) once it exists — see [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md).

## Quick start

There's nothing to run yet. What does work:

```bash
mise install   # fetches the pinned toolchains (python, node, uv)
```

## Installation

See [docs/guides/getting-started.md](docs/guides/getting-started.md).

## Usage

Not yet — see [Roadmap](#roadmap) and [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) for how the first app gets added.

## Configuration

Copy [.env.example](.env.example) to `.env`. It's currently empty; each app adds its own keys as it's scaffolded.

## Architecture

Start with [docs/architecture/overview.md](docs/architecture/overview.md) and the [system context diagram](docs/architecture/diagrams/system-context.md). Every non-obvious decision is recorded as an [ADR](docs/adr).

## Documentation

- [Domain](docs/domain) — what Lorenzo actually is, in plain language: the world model, repositories, entities/knowledge/visibility
- [Architecture](docs/architecture) — the technical design
- [ADRs](docs/adr) — why things are the way they are
- [Guides](docs/guides) — task-oriented how-tos
- [Operations](docs/operations) — releasing, GitHub setup

## Development

This repo is built structure-and-config-first: an app only gets real code once it's explicitly scoped, not speculatively. See [CONTRIBUTING.md](CONTRIBUTING.md) for the git/branch/commit strategy.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md) for supported versions and how to report a vulnerability.

## Roadmap

Tracked as [GitHub issues](https://github.com/ramsesoriginal/lorenzo/issues) and milestones. Immediate next step: scope and scaffold the first real app.

## License

[AGPL-3.0](LICENSE) — if you run a modified version of this as a network service, you must offer its source to your users.
