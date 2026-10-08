# 0148 - Dependency-aware PR CI: test what a change can affect, never what it can't

Status: accepted (decided with the maintainer on 2026-09-30); implemented the same day, see the addenda at the end. Not built, on purpose: the Playwright browser cache (measured, about 10 s per shard) and the items under "Not in scope"

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
- **Declared, in one file:** `.github/ci-graph.toml` holds every edge no package manager sees, today `apps/api` -> `packages/api-client` and `apps/api` -> `apps/cli` (generated from its OpenAPI schema, and the CLI's e2e runs the real API), and any edge in a language the script can't read.
- **A node the script can't read must be declared.** A node with no `package.json` and no `pyproject.toml` (Kotlin, C#, ...) that is missing from `.github/ci-graph.toml` fails the `discover` job with a message saying so, rather than being skipped or silently always run. That is what makes registering it impossible to forget; the PR that adds the node is also the PR that adds its entry.

**3. Some changes affect everything.** A change to the root `mise.toml`, `.github/workflows/ci.yml`, `.github/ci-graph.toml`, the discovery script, `pnpm-workspace.yaml`, the root `package.json`, or the toolchain pins runs every node. The root `pnpm-lock.yaml` runs every pnpm node (per-importer filtering of the lockfile is a later refinement if Dependabot PRs make it worth it). Documentation-only changes run no test leg.

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
2. Its dependencies on other nodes: a JS node lists them in `package.json`, a Python node as a uv path source; both are then derived. **Any other language declares them in `.github/ci-graph.toml`, and must be declared there even with no dependencies, or `discover` fails.**
3. A node that consumes generated code from another (a client generated from `apps/api`'s OpenAPI schema) declares that edge in `.github/ci-graph.toml` and gets a `check-schema` task so `client-drift` picks it up.
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
- `.github/ci-graph.toml` is a new file to keep right. Most of it is derived on purpose; the hand-written part is short and validated (`discover` fails on a node it can't place).
- Changing the required checks is a repo-settings change and happens as step (a), before any job can be skipped.
- Every job that gates a merge must be a dependency of `ci-summary`; a new one left out would never block a PR.

## Addendum (2026-09-30): what the implementation of step (b) settled

- **The graph file is TOML** (`.github/ci-graph.toml`), not YAML as written above. The discovery script is standard-library Python so the job every other job waits on needs no toolchain; Python reads TOML (`tomllib`) but not YAML, and the repo already uses TOML for `mise.toml`.
- **Three relations, not one.** `depends_on` (derived from `package.json` and uv path sources, or declared) runs a node's tests when something it uses changes. `generated_from` (declared) runs a node's `check-schema` task when its source changes but **not** its tests: they run only if the regenerated code, or anything else in the node, changed. That is what makes an API change that leaves the OpenAPI schema alone skip the TypeScript apps. A suite (`[suites.<name>]`) runs when its node, or any node it runs against, is affected. `packages/api-client` is `generated_from` the API; `apps/cli` is both `depends_on` and `generated_from` it, until step (c) splits its end-to-end tests out.
- **`mise` task references are not edges.** `check-schema` tasks call `//apps/api:openapi-schema`, which would turn the generated-from relation into a test-propagating one.
- **What `discover` emits:** the `test` matrix (with each leg's `postgres` flag, replacing the hard-coded list in `ci.yml`), the `client-drift` matrix (every affected node with a `check-schema` task), the suites to run, and whether `openapi-diff` runs. It also writes a table to the job summary saying what ran and why. `ci-tools` runs the script's own unit tests on every PR.
- **The graph is checked against the repository** by those tests: every discovered node is placed, and a `loot-bot` change runs `loot-bot` only, an `api-client` change runs the three apps, an API change runs `apps/api` and `apps/cli` (drift-checking the clients and running the inventory-web suite), and documentation runs nothing.

## Addendum (2026-09-30): step (c), speed-ups

- **`apps/cli` is two things now.** `test` is its unit tests (about 40-60 s, no database, no API); `test-e2e` is `tests/e2e/`, the `cli-e2e` suite in `.github/ci-graph.toml`, which runs when the CLI or the API is affected. The CLI no longer `depends_on` the API, so an API change drift-checks its generated models and runs `cli-e2e` but not its unit tests.
- **Sharding.** A node can set `shards = N` in the graph: `discover` emits N legs with `TEST_SHARD=i/N` and the node's tests select their share. `apps/api` has `shards = 2` (1084 tests, 542 each); its `conftest.py` assigns test files to the lightest group by test count, largest first, and the split is the same on every runner. The `cli-e2e` job (three runners, the same hook in `apps/cli/tests/e2e/conftest.py`) and the inventory-web Playwright job (`--shard=i/3`) each give every shard its own Postgres. Linting runs once per sharded node.
- **Caching was measured and left out.** The small legs spend 3-4 s in their test step and `mise` is already cached by its action; a pnpm or uv cache would save seconds. Playwright's browser download (about 26 s on each inventory-web shard) is the one candidate left, and it would still need `playwright install-deps`, so the saving is about 10 s per shard. Revisit with real numbers from the sharded runs.

## Addendum (2026-09-30): Dependabot and the root lockfile

Dependabot's npm PRs changed only a member's `package.json` and never the shared `pnpm-lock.yaml`, because `dependabot.yml` had one npm entry per workspace member and none for the root; CI's `pnpm install --frozen-lockfile` then failed on each of them. `.github/dependabot.yml` now has one npm entry whose `directories` list the root and every JS member (including `packages/lorenzoscript` and `packages/lorenzoscript-editor`, which had no entry at all). Every ecosystem's updates are split into a `<eco>-minor-patch` group and a `<eco>-major` group, so a breaking major can't hold up the routine bumps. A Dependabot PR therefore touches the root lockfile, which this ADR's graph already treats as "run every pnpm node" (decision 3).

## Addendum (2026-10-01): an ignore for TypeScript 7

Working through the grouped major PR (#352) one package at a time showed that one major can't be taken yet: TypeScript 7. `astro check` refuses it in `account-hub` and `inventory-web`, and `openapi-typescript` crashes on it in `packages/api-client`, so every Dependabot PR that carried it failed. The npm entry in `dependabot.yml` now has an `ignore` for `typescript` `>=7` (TypeScript 6 is not ignored), with a comment saying how to lift it. The other majors in that group (Biome 2 for `loot-bot`, vitest 5, zod 4, pino 10, `prettier-plugin-astro` 1, and Node 26 with `@types/node` 26) were done by hand, each as its own PR, which is what the separate `npm-major` group makes possible.

## Addendum (2026-10-08): where the end-to-end suites spent their time

A PR run took about 6.5 minutes (median of the last 48 successful PR runs; 90th percentile about 8), and its critical path was `cli-e2e`, 3.5 to 6.6 minutes depending on the shard, not the Playwright job. Profiling the CLI's end-to-end suite and probing the API found where that time went, and a first change was measured in CI against the `main` run before it (395 s from the first job's start to the last job's end, 341 s after).

- **A full `lorenzo seed` is 167 sequential API requests, and the API's own time accounted for all of the seed's wall time.** The time was in the requests, not in the CLI, the JS host, or the disk: `fsync=off`, `synchronous_commit=off` and `full_page_writes=off` on the suite's Postgres made no difference (a seed took 18.6 s with durability and 18.3 s without).
- **Every request also did something it did not need to.** While `user.email` is empty, `_sync_email_from_claims` ([ADR 0075](0075-sync-email-via-userinfo-not-access-token.md)) asks Authgear's UserInfo endpoint, and it builds a new `httpx.AsyncClient` to do so. The docstring's "at most once per user" holds only for a user who gets an email. The CLI's fake Authgear answered `/userinfo` with a 404, so no test user ever had one and every request of every test paid it; inventory-web's fake already answered with a verified email.
- **The change:** the CLI's fake Authgear answers `/oauth2/userinfo` with a verified email of its own per subject. In CI the `cli-e2e` test time went from 931 s to 693 s over the three shards (-26%), each test file 18 to 38% faster. A first profile on a Windows-mounted checkout (WSL) suggested far more, 60% and a client costing 72 ms to build; that was the CA bundle being read over the cross-OS file system (2.6 ms on a native one), so those figures were wrong for a runner and are not used here.
- **What this does not change:** the API itself. A real user with no verified email still makes a UserInfo call, and builds a client for it, on every request. Reusing one client, or remembering for a while that a user has no email, would change what ADR 0075 decided, so it is a separate decision.
- **The same default in `apps/api`'s `_fake_jwks.py`, with one shared `PyJWKClient` in `raw_client`, was tried and dropped:** on the five heaviest real-token test files it took 23.0 s to 21.2 s, which does not pay for a flag and an opt-out in `test_auth.py`.

Two fixed costs that the faster tests leave as a larger share:

- **Postgres starts first, in the background, and is waited for before the tests.** `docker run -d` goes in the first step, before the checkout, with its output in a file, and a later step polls `pg_isready` over TCP (a server that only listens on its socket answers too while the image first starts, and is then restarted). The pull and boot overlap the checkout, `mise` and `pnpm install`. This replaces the `services:` container of the two Playwright jobs, which held the job for 12 to 16 s before its first step, and the blocking `docker run` of the `test` and `cli-e2e` jobs (5 to 10 s); in CI the container steps now take under 2 s.
- **Playwright's browser is cached, and installed without `--with-deps`.** The cache (`~/.cache/ms-playwright`) is keyed by Playwright's version and holds the headless shell; a miss runs `playwright install chromium-headless-shell`. The runner image already carries the system libraries `--with-deps` would install, which was 21 to 33 s on every shard. This supersedes "left out" in the caching addendum above and the "after `playwright install --with-deps chromium`" line of [ADR 0114](0114-inventory-web-end-to-end-tests.md) for CI.

**What the runner's own Chrome showed, and why it was not kept.** The first version of this change set `E2E_BROWSER_CHANNEL=chrome`, which both Playwright configs read, to skip the browser install altogether. Measured in CI it saved the install but made the test steps 28 to 43 s longer (inventory-web's 84 s to 127 s, account-hub's 31 s to 59 s), because Chrome's new headless mode is a full browser where the headless shell is a stripped one, so inventory-web's job did not get faster. It also failed one test the shell passes: account-hub's Studio phone test found 8 px of horizontal overflow on the People tab. That is a real bug the shell had been hiding: below 720 px `.with-sidebar` was `grid-template-columns: 1fr`, which is `minmax(auto, 1fr)`, so the column would not shrink below the intrinsic width of a form control in it and the page scrolled sideways on a phone. It is now `minmax(0, 1fr)`, which passes in both headless modes.

## Addendum (2026-10-08): a profile of the end-to-end suites, and what it led to

The first changes left the CLI's end-to-end suite as the longest job, so the three suites were profiled from the inside: every API request (route and duration), every CLI command and every test, timestamped and joined. On a checkout on a native file system (a clone under WSL's home, where the suite took 704 s against CI's 708 s summed), because a checkout mounted from Windows distorted the first profile.

- **CLI end-to-end, 704 s for 129 tests.** 95% of it is the API serving requests, 18,329 of them at 36.6 ms on average. `lorenzo seed` is 68% of the suite (141 commands, about 126 sequential requests for a full seed, 4.7 s) and `apply` 15%. 71 of the 129 tests seed, 65 of them in full and 76 more by layer.
- **Why a request costs what it does.** A read of one item runs about 32 SQL statements, half the time in SQL and half in Python, with the same lookups repeated inside one request (membership three times; the campaign GM grants, information, prototypes and tenant twice each), and every authenticated request writes an `app_user` upsert. Changing that is a change to the API and to what [ADR 0075](0075-sync-email-via-userinfo-not-access-token.md) decided about the user row; it is not part of this change.
- **`seed` read what it found one item at a time.** Its plan asked for every node a tenant already had with its own `GET /items/{id}`: 10 to 25 of them for a layered seed, a second run or a dry run.
- **Playwright (inventory-web), 281 s on one worker.** Building a world 14%, building a scene 31% (the same `packed()` in 57 tests), the browser and the test's own calls 55%.
- **apps/api's tests, 185 s for 1,295 tests.** A median test takes 60 ms; the slowest tenth takes 57% of the time and fixtures 3%.

What changed, in `apps/cli`:

- **A copy, not a seed, as the start state.** A copy of a seeded repository (a grant and a copy, about 10 requests, 0.2 to 0.3 s) is how a table gets the seed ([ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)); a seed is 4 to 5 s. The tests of what the importer does with a seeded tenant (plan, apply, packs, the titles of imported items) start from a copy of one seeded, published repository that the session builds when something first asks (`helpers.golden_repository`, `copy_of_seeded`). The tests of the seed itself, and the `unseed` ones, still run it.
- **One world for tests that only read or add.** `test_split`'s first four tests and `test_setup`'s first two build their four-repository world once per module. The tests that rename or publish in the repositories keep their own.
- **Parallel workers, a stack each** (pytest-xdist, `E2E_WORKERS`, four by default, `--dist loadfile`). Each worker has its own API process and its own database, cloned from a template one of them migrates: the migrations create a role that belongs to the whole server, so running them side by side races. An advisory lock serialises the template and the clones, and the template is named after the migrations, so a changed one makes a new template. A run's databases are named after the run and the worker and dropped at the end, because two sessions on one Postgres, each with a fixed name, dropped each other's tables (two of nine benchmark runs).
- **`seed` reads in bulk** (`read_items`): one page of the item listing, 100 a request, instead of a request per node. A page costs about 40 ms and under a millisecond a row, and a request for one item about 30 ms, so a tenant of up to ten pages is read from the listing and a bigger one node by node; what the listing does not hold is still asked for by id, so the answer is the same. A layered seed went from 2.1 s to 1.3 s and a dry run from 1.2 s to 0.16 s.

Measured with the tests and Postgres pinned to four cores, a shard at a time, as CI splits them (a 16-core machine standing in for a four-vCPU runner, so the ratios carry over and the seconds may not):

| Shard | Baseline, serial | Copies and shared worlds, serial | And three workers |
| --- | --- | --- | --- |
| 1 of 3 | 169 s | 173 s | 88 s |
| 2 of 3 | 274 s | 161 s | 97 s |
| 3 of 3 | 247 s | 152 s | 75 s |

The slowest shard with two, three and four workers took 105, 97 and 78 s; the whole suite on one runner with four workers 168 s, and 147 s with the bulk read in. Shard 1 did not gain from copies: it is the seed's own tests.

Still open, in this order: the API's per-request SQL and the `app_user` upsert (a decision on ADR 0075); how many runners `cli-e2e` needs now that a shard takes about a minute and a half, with two probably enough; shards balanced by recorded duration; `unseed`'s own item-by-item reads.

## Addendum (2026-10-08): apps/api's tests on parallel workers

The API's 1,295 tests are many small, independent ones (a median of 60 ms; the slowest tenth takes 57% of the time and fixtures 3%), so parallel workers help directly. `pytest-xdist` runs them on `TEST_WORKERS` workers (four by default, 0 for one process), each with a database of its own cloned from a migrated template, as for the CLI's end-to-end tests: `tests/_workers.py`, imported first by `conftest.py` because the settings are read at import, with `asyncpg` since `psycopg` is not a dependency of the API. A run without workers uses the database it is given, as before.

One test read the whole `information` table, so on a shared database it failed on rows other runs had left; with a database per worker it sees only its own.

Measured with the tests and Postgres pinned to four cores, coverage on:

| Run | Time |
| --- | --- |
| One process, shard 1 of 2 / shard 2 of 2 (today's two runners) | 97 s / 65 s |
| Four workers, shard 1 / shard 2 | 36 s / 27 s |
| Whole suite on one runner, two / three / four workers | 85 / 61 / 51 s |
| Four workers, `loadfile` / no coverage | 53 s / 48 s |

So `apps/api` is one `test` leg now (`shards = 2` is gone from `.github/ci-graph.toml`): 51 s on one runner against 97 s for the longer of two. `deploy-api.yml` runs `mise run test` too, so its verify job uses the workers as well. CI's own timings are the check.

## Addendum (2026-10-08): inventory-web's end-to-end tests

The suite is 109 Playwright tests, and CI runs them as three shards of two workers each (Playwright's default on a four-vCPU runner). Measured the same way as the others, on four pinned cores:

- **More workers do not help.** The whole suite took 197 s on two workers, 189 s on three and 197 s on four: two already keep the four cores busy (Chromium 216 core-seconds, the API 145, Postgres 124, of about 650), so what is left to take out is work, not waiting.
- **Half of a worker's time is building worlds.** Every test builds its own world through the API (a tenant, three people, a campaign, two players, the stat definitions: 71 s over the run) and 57 of them the same `packed()` scene on top (135 s, with the catalog inside it), which is about 50% of the 438 worker-seconds. The browser takes the rest.
- **Two things that did nothing.** Postgres with `fsync`, `synchronous_commit` and `full_page_writes` off (184 s against 182 s) and Chromium with `--disable-gpu` (184 s): the suite is not waiting on a disk or a GPU. They are not in the workflow.

What changed, in `apps/inventory-web`:

- **Tests that only look share a world.** 23 tests open a page and read it (the board's columns and search, an item's page, the notes on hover, the catalog's search, the login). They use `readOnly` in `tests/e2e/support/fixtures.ts`, which builds one world per worker, with Pia carrying the `packed` scene, and hands it to each; `scene` has its ids. The helpers of the world that write (`item`, `instance`, `slug`, `setStat`, `stack`, `group`, `describe`) throw there, so a test that grows a write fails at once and moves to `test`, which still gives every test a world of its own, as the other 86 need: they move, give, edit and slug what is in it, or count on it being empty. Whole suite, two workers, four pinned cores: 182 s to 167 s, the API's CPU 115 to 104 core-seconds and Postgres's 107 to 92.
- **The API's environment is built while pnpm installs.** Playwright starts the API with `uv run`, which first fetched Python, made the virtual environment and installed the dev tools, about 5 s of a shard's start, inside its sequential web-server start. The `e2e` and `account-hub real-api` jobs now run `uv sync --frozen --no-dev` in the background after mise, wait for it with Postgres, and set `UV_NO_DEV` for the run, so `uv run` finds it ready (0.8 s).

Still open for these tests: shards balanced by recorded duration (shard 2 of 3, with the board and hand-over specs, takes 133 s and the others 109 and 104 s: Playwright splits by test count), and the API's per-request cost that every seeding call and every page pays (the decision on ADR 0075 above).
