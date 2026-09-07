# Contributing

Thanks for the interest — this is currently a solo/early-stage project, but it's built to be contributor-friendly from day one.

## How this repo is built

Structure, tooling, and documentation come first; application code only gets written once something is explicitly scoped — not speculatively, and not ahead of what's actually been decided. If you're proposing a new app, start with [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md), not a pull request full of code.

## Dev environment

```bash
mise install   # pins every language toolchain this repo will use
```

That's genuinely all there is right now — see [docs/guides/getting-started.md](docs/guides/getting-started.md).

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

(Once at least one app exists to lint/test — [ci.yml](.github/workflows/ci.yml) discovers apps automatically, nothing to configure per app.)

## Architectural changes

Non-obvious or hard-to-reverse decisions get an [ADR](docs/adr) — copy [docs/adr/0000-template.md](docs/adr/0000-template.md). Bigger, not-yet-decided proposals go in [docs/rfcs](docs/rfcs) first.

## Adding a new app or package

See [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) (a deployable app under `apps/`) or [docs/guides/adding-a-package.md](docs/guides/adding-a-package.md) (a generic, reusable library under `packages/`).
