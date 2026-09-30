# 0148 - Dependency-aware PR CI: test what a change can affect, never what it can't

Status: accepted (decided with the maintainer on 2026-09-30); implementation follows, in the order under [Decision](#decision)

## Context

Every PR runs the whole suite. On the two most recent full runs that was about 6-8 minutes of wall time and about 25 runner-minutes across 14 jobs:

| Job | Time |
| --- | --- |
| `test (apps/cli)` | 300-370 s (its end-to-end tests start the real API and Postgres) |
| `e2e` (inventory-web, Playwright against the real API) | 250-260 s |
| `test (apps/api)` | 155-160 s |
| every other `test (...)` leg | 40-65 s, of which about 30 s is fixed overhead (service container, `mise`, checkout) |

Two things follow. A PR that changes one app's own code, or only documentation (69 of the repo's first 238 PRs were documentation-only), still pays for everything, including a Postgres container that most legs never use. And the critical path is three jobs, so skipping small ones saves runner time but not wall time: the API and CLI suites are what need to get faster.

The repo already has the structure this needs. `packages/api-client` sits between `apps/api` and its TypeScript consumers ([ADR 0122](0122-api-client-package.md)); the CLI carries a generated Python client of its own ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)); the generated schema in each is committed and `client-drift` fails a PR that lets it fall behind `apps/api`. A change to the API's contract therefore always shows up as a diff in a client package, which is a usable signal for "downstream is affected".

One obstacle: the `main` ruleset requires `test (apps/api)`, `test (apps/cli)`, and `test (apps/loot-bot)` by name. A matrix leg that is skipped never reports, so the PR could never merge. That has to change before any job is skipped.

## Decision

**1. Changes propagate downstream, never upstream.** Every directory with a `mise.toml` under `apps/` or `packages/` is a node ([ADR 0007](0007-apps-layout-and-multiplicity.md), unchanged). A node that *uses* another depends on it. A PR's affected set is the nodes whose files changed plus everything that depends on them, transitively. Nothing upstream is added: a `loot-bot` change runs `loot-bot`'s checks and not `apps/api`'s, because a consumer cannot break the thing it consumes. A change to `apps/api` reaches `packages/api-client` and the CLI, and through the client's changed schema its TypeScript consumers; a change to a shared package (an `auth` package, say) reaches every app that lists it.

**2. Where the edges come from.**

- **Derived, so they can't drift:** JS/TS edges from each `package.json`'s workspace dependencies (`workspace:*`), and Python edges from `[tool.uv.sources]` path dependencies in `pyproject.toml`.
- **Declared, in one file:** `.github/ci-graph.yml` holds every edge no package manager sees, today `apps/api` -> `packages/api-client` and `apps/api` -> `apps/cli` (generated from its OpenAPI schema, and the CLI's e2e runs the real API), and any edge in a language the script can't read.
- **A node the script can't read must be declared.** A node with no `package.json` and no `pyproject.toml` (Kotlin, C#, ...) that is missing from `.github/ci-graph.yml` fails the `discover` job with a message saying so, rather than being skipped or silently always run. That is what makes registering it impossible to forget; the PR that adds the node is also the PR that adds its entry.

**3. Some changes affect everything.** A change to the root `mise.toml`, `.github/workflows/ci.yml`, `.github/ci-graph.yml`, the discovery script, `pnpm-workspace.yaml`, the root `package.json`, or the toolchain pins runs every node. The root `pnpm-lock.yaml` runs every pnpm node (per-importer filtering of the lockfile is a later refinement if Dependabot PRs make it worth it). Documentation-only changes run no test leg.

**4. Jobs follow the graph, not hardcoded names.**

- `test`: one leg per affected node.
- `client-drift`: one check per node that has a `check-schema` task, run when that node or `apps/api` is affected. It replaces the two hardcoded steps, so a new generated client joins by having the task.
- `openapi-diff`: when `apps/api` is affected.
- Slow integration suites are their own jobs, named after a node's `test-e2e` task, affected the way the node is (so inventory-web's e2e runs when `apps/api`, `packages/api-client`, or `apps/inventory-web` is). The CLI's end-to-end tests move out of its `test` task into a `test-e2e` task for the same reason.
- Postgres starts only for the jobs that declare they need it (`apps/api`, the CLI and inventory-web e2e suites, `apps/loot-bot`).

**5. Required checks shrink to the aggregate.** The ruleset requires `ci-summary` and the two CodeQL checks. `ci-summary` depends on every job, reports green when a job was skipped, and red when any job failed or was cancelled. The ruleset file, the live ruleset, and [docs/operations/github-setup.md](../operations/github-setup.md) change together.

**6. The full suite runs on `main`.** A push to `main` marks every node affected; there is no nightly run and no merge queue. Full CI on `main` is the safety net.

**7. Speed-ups that don't depend on the graph.** Shard `apps/api`'s tests across a matrix (or `pytest-xdist` with a database per worker; measured first, then chosen); split the CLI's unit tests from its e2e stack; cache the `mise` toolchains, the uv cache, the pnpm store, and Playwright's Chromium.

**Order.** (a) `ci-summary` and the ruleset, with the Postgres and caching cuts: no job is skipped yet, so nothing can block. (b) The discovery script, the graph file, and the graph-driven jobs. (c) Sharding and the CLI split.

### Registering a new node

This is the checklist [docs/guides/adding-an-app.md](../guides/adding-an-app.md) and [docs/guides/adding-a-package.md](../guides/adding-a-package.md) carry:

1. A `mise.toml` with `dev`/`lint`/`test`/`build` makes the directory a node.
2. Its dependencies on other nodes: a JS node lists them in `package.json`, a Python node as a uv path source; both are then derived. **Any other language declares them in `.github/ci-graph.yml`, and must be declared there even with no dependencies, or `discover` fails.**
3. A node that consumes generated code from another (a client generated from `apps/api`'s OpenAPI schema) declares that edge in `.github/ci-graph.yml` and gets a `check-schema` task so `client-drift` picks it up.
4. A slow integration suite gets a `test-e2e` task (and keeps `test` fast); say in the graph file if it needs Postgres.
5. A compiled language's CodeQL support, and its toolchain in the root `mise.toml` (`security.yml` has the marker comment).

A future `packages/python-api-client` is node + derived edge (the CLI points a uv path source at it) + declared edge from `apps/api` + a `check-schema` task. A Kotlin mobile app with its client package is two declared nodes: the client depends on `apps/api` (generated, with `check-schema`), the app depends on the client. The app's Gradle build is not read, so its edges are always written down.

### Not in scope

- **A `contract` suite** running each client against the real API (auth, errors, pagination, serialization). Worth having once the broad e2e suites are no longer run on every PR; not needed to make this change safe, since the full suite runs on `main`.
- **A `ci:full` label** to force a full PR run.
- **A lint check that apps reach the backend only through a client package.** The convention holds today (loot-bot, inventory-web and account-hub use `@lorenzo/api-client`, the CLI its own generated client), but nothing enforces it, and this ADR's skip logic relies on it: an app calling the API by hand would not be caught by a schema change. Enforcing it is the natural next ADR.
- **Extracting the CLI's client into a `packages/python-api-client`.** Independent of this change; the registration steps above cover it when it happens.

## Consequences

- PR CI gets cheaper (a docs-only PR runs no tests; a single-app PR runs that app and its dependents) and, with sharding and the e2e split, shorter on the API path too.
- **A gap, accepted:** an API change that alters behavior without changing its OpenAPI schema runs the API's own tests on the PR, not its downstream apps'. The push to `main` runs everything and catches it there.
- `.github/ci-graph.yml` is a new file to keep right. Most of it is derived on purpose; the hand-written part is short and validated (`discover` fails on a node it can't place).
- Changing the required checks is a repo-settings change and happens as step (a), before any job can be skipped.
- Every job that gates a merge must be a dependency of `ci-summary`; a new one left out would never block a PR.
