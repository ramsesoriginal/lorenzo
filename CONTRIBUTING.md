# Contributing

Thanks for the interest — this is currently a solo/early-stage project, but it's built to be contributor-friendly from day one.

## How this repo is built

Structure, tooling, and documentation come first; application code only gets written once something is explicitly scoped — not speculatively, and not ahead of what's actually been decided. If you're proposing a new app, start with [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md), not a pull request full of code.

## Dev environment

```bash
mise install                                        # pins every language toolchain this repo uses
docker compose -f infra/docker-compose.yml up -d    # Postgres, for apps/api
```

See [docs/guides/getting-started.md](docs/guides/getting-started.md) for the full from-clone walkthrough.

## Git strategy ([ADR 0005](docs/adr/0005-git-branching-and-merge-strategy.md))

- Branch off `main`: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`.
- Commit early and often. Messages follow [Conventional Commits](https://www.conventionalcommits.org/) (enforced by a commit-msg hook) — this drives changelogs and version bumps via release-please.
- Open a PR into `main` even for solo work — it's the CI gate.
- PRs merge with a **real merge commit** (not squash, not rebase), so `git log --graph` keeps showing actual branch history. Branches are not auto-deleted after merge.

## Before you open a PR

```bash
mise run lint
mise run test
```

[ci.yml](.github/workflows/ci.yml) discovers apps automatically — nothing to configure per app, including the next one.

## Architectural changes

Non-obvious or hard-to-reverse decisions get an [ADR](docs/adr/README.md) — copy [docs/adr/0000-template.md](docs/adr/0000-template.md). Bigger, not-yet-decided proposals go in [docs/rfcs](docs/rfcs/README.md) first.

## Adding a new app or package

See [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) (a deployable app under `apps/`) or [docs/guides/adding-a-package.md](docs/guides/adding-a-package.md) (a generic, reusable library under `packages/`).
