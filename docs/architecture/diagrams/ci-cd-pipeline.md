# CI/CD pipeline flowchart

```mermaid
flowchart TD
    A["Push / PR opened"] --> B["ci.yml"]
    B --> B0["ci-tools: the discover script's own tests"]
    B --> B1["discover: apps and packages, dependency graph,<br/>which suites are affected"]
    B1 --> B2["test: affected nodes only, shards and batches<br/>(background Postgres where needed;<br/>Android SDK for inventory-mobile, macOS runner for inventory-ios)"]
    B1 --> B5["openapi-diff (PRs only) and client-drift:<br/>breaking API changes, stale generated clients"]
    B1 --> B6["end-to-end suites, each its own job, run when their app<br/>or the API is affected: inventory-web, beings, calendars,<br/>sessions, maps, writing, bench, account-hub real API, cli-e2e"]
    B1 --> B7["native builds: mobile-build (debug APK,<br/>unsigned release bundle), ios-build (unsigned IPA)"]
    A --> B3["security.yml: CodeQL (also weekly)<br/>+ dependency-review (PRs only)"]
    A --> B4["docs.yml: markdownlint + lychee<br/>(Markdown changes only)"]
    B0 --> C
    B2 --> C{"ci-summary<br/>(required check)"}
    B5 --> C
    B6 --> C
    B7 --> C
    B3 --> D
    B4 --> D

    C -->|all required checks pass| D["Merge to main<br/>(real merge commit)"]

    D --> E{"Touches apps/api/**,<br/>packages/calendar-engine/**<br/>or packages/map-engine/**?"}
    E -->|yes| F["deploy-api.yml triggers"]
    D --> EL{"Touches loot-bot or api-client?"}
    EL -->|yes| FL["deploy-loot-bot.yml triggers"]
    D --> G["release.yml triggers<br/>(every push)"]
    D --> CF["Static apps: Cloudflare Pages'<br/>own Git integration builds them<br/>(outside GitHub Actions)"]

    G --> G1["release-please: open/update release PR"]
    G1 --> G2["sync-lockfile: regenerate uv.lock for the five<br/>Python projects on the release PR"]

    F --> F1["verify: lint + test again"]
    F1 --> F2["auth: OIDC via Workload Identity Federation"]
    F2 --> F3["build and push image to Artifact Registry<br/>tagged by commit SHA"]
    F3 --> F4["migrate: alembic upgrade head against Neon"]
    F4 --> F5["deploy: new Cloud Run revision"]
    F5 --> F6{"curl /readyz"}
    F6 -->|200| H["Live"]
    F6 -->|non-200| I["Workflow fails -<br/>revision not confirmed healthy"]

    FL --> FL1["verify: lint + test again"]
    FL1 --> FL2["auth: same OIDC/WIF identity as deploy-api.yml"]
    FL2 --> FL3["build and push image to lorenzo-loot-bot repo<br/>tagged by commit SHA"]
    FL3 --> FL4["migrate: tsx src/migrate.ts against Neon's loot_bot schema"]
    FL4 --> FL5["deploy: new Cloud Run revision"]
    FL5 --> FL6{"curl /livez"}
    FL6 -->|200| H
    FL6 -->|non-200| I
```

`ci-summary` aggregates the CI jobs; the separate security and documentation workflows run alongside it. Which nodes and suites a change reaches is decided by `discover` from the dependency graph, derived from `package.json` and `pyproject.toml` plus the hand-written [`.github/ci-graph.toml`](../../../.github/ci-graph.toml) ([ADR 0148](../../adr/0148-dependency-aware-pr-ci.md)); a push to `main` runs everything. A node CI cannot read (Kotlin, Swift, plain CSS) is declared there, which is why `apps/inventory-mobile`, `apps/inventory-ios` and `apps/brand` have entries of their own. The suites in the graph are `inventory-web-e2e`, `beings-e2e`, `bench-e2e`, `calendars-e2e`, `sessions-e2e`, `maps-e2e`, `writing-e2e`, `account-hub-real-api` and `cli-e2e` (Playwright, or the CLI, against the real API and a fake Authgear), plus `mobile-build` and `ios-build`; `apps/calendars`, `apps/sessions`, `apps/maps` and `apps/writing` are ordinary nodes beside the other web apps, with their shared packages (`packages/map-engine`, `packages/map-renderer`, `packages/entry-preview` and others) declared the same way.

Three independent triggers can fire off the same push to `main`: `release.yml` (always, proposing/updating a version bump and keeping the release PR's lockfiles in step), `deploy-api.yml` (only if the push touches `apps/api/**`, `packages/calendar-engine/**` or `packages/map-engine/**`, which the API image bundles), and `deploy-loot-bot.yml` (only if it touches `apps/loot-bot/**` or `packages/api-client/**`, [ADR 0053](../../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)). None depend on each other — a release PR being merged doesn't itself deploy anything, and a deploy doesn't wait for a release to be tagged. The static web apps have no equivalent job in this repo at all — Cloudflare Pages' own Git integration deploys them independently on the same push, outside GitHub Actions entirely (see [deployment.md](../deployment.md#static-apps-on-cloudflare-pages)), and the Android and iOS apps are built by CI but installed locally, not deployed (see [deployment.md](../deployment.md#native-apps)). See [docs/operations/releasing.md](../../operations/releasing.md) and [docs/architecture/deployment.md](../deployment.md).
