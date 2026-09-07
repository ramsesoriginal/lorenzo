# AGENTS.md

Orientation for AI coding agents (and humans in a hurry) working in this repo.

## What this is

Lorenzo: a multi-tenant REST API plus static frontend(s), Discord bot(s), and mobile app(s) for tabletop/worldbuilding campaign management. See [README.md](README.md) for the pitch, [docs/domain](docs/domain/README.md) for what the system actually models (not technical), and [docs/architecture/overview.md](docs/architecture/overview.md) for the system shape.

**`apps/api` exists as infrastructure only** (health/readiness/metrics, DB connectivity, no domain models, no auth) — everything else under `apps/` is still unbuilt, per [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md). Do not add application code speculatively; an app (or a domain feature inside `apps/api`) gets built only once it's explicitly scoped in conversation with the user.

## Map

| Path | Purpose |
| --- | --- |
| `apps/api` | Backend REST API — infrastructure only so far, no domain models |
| `apps/*` (other) | One directory per deployable app, named by purpose (not type) — none exist yet |
| `packages/*` | Extracted generic libraries, each its own small, independently versioned package — none exist yet |
| `docs/adr` | Why things are the way they are — read before proposing an architectural change |

## Commands

```bash
mise install                                        # toolchains
docker compose -f infra/docker-compose.yml up -d    # Postgres, for apps/api
mise run //apps/api:dev                              # apps/api, with autoreload
mise run lint                                          # fans out to every app (currently just apps/api)
mise run test                                           # ditto
```

`apps/api` already owns `dev`/`lint`/`test`/`build` tasks in its own `mise.toml` (see [ADR 0007](docs/adr/0007-apps-layout-and-multiplicity.md) and [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md)); CI discovers them automatically, and the next app just needs the same contract.

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/); a commit-msg hook enforces this.
- Merge PRs with a merge commit, never squash/rebase (see [ADR 0005](docs/adr/0005-git-branching-and-merge-strategy.md)) — branch history is kept deliberately.
- No `utils`/misc grab-bags — generic code becomes its own package under `packages/`.
- Any app that stores tenant data needs a `tenant_id` column and an RLS policy (see [ADR 0002](docs/adr/0002-multi-tenancy-shared-schema-rls.md)) once it's built. Never rely on application-level filtering alone.
- Formatting/linting is enforced by pre-commit + CI, not by convention.

## Before making a change

1. Check [docs/adr](docs/adr/README.md) — is this decision already made, and why?
2. If this is about adding a new app: read [docs/guides/adding-an-app.md](docs/guides/adding-an-app.md) and confirm scope with the user before writing code.
3. Prefer the smallest vertical slice that's actually tested end to end over a broad partial implementation — but only once asked to build, not while still preparing structure.
