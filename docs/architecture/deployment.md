# Deployment architecture

How `apps/api` and `apps/loot-bot` actually run, locally and in production, and how commits get from a merged PR to a live revision. The static web apps (account hub, inventory-web, Beings, Bench, Calendars, Sessions and the brand site) deploy a different, much simpler way, and the native iOS and Android apps are installed locally — see [Static apps on Cloudflare Pages](#static-apps-on-cloudflare-pages) and [Native apps](#native-apps) below. For the one-time account/IAM setup this depends on, see [docs/operations/deployment-setup.md](../operations/deployment-setup.md); for why Cloud Run + Neon specifically, see [ADR 0011](../adr/0011-deploy-target-cloud-run-neon.md) (`apps/api`) and [ADR 0053](../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md) (`apps/loot-bot`).

## apps/api

### Local development

- **App**: runs directly on the host, not containerized — `uv run fastapi dev src/lorenzo_api/main.py` (via `mise run //apps/api:dev`), with autoreload on file changes. Listens on `localhost:8000`.
- **Database**: Postgres via `infra/docker-compose.yml`, on port `55432` (not `5432`, deliberately clear of any other local Postgres). `.env` (copied from `.env.example`) points both `DATABASE_URL` (the app's own restricted role) and `MIGRATIONS_DATABASE_URL` (privileged, Alembic-only — [ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)) at it.
- **Nothing else runs locally** — no Authgear, no Redis, no trace collector. Tracing exports to the console; metrics are scraped by nothing (the `/metrics` endpoint is just there to curl or point a local Prometheus at, if you want).

### Production

| Piece | What | Why |
| --- | --- | --- |
| Compute | [Google Cloud Run](https://cloud.google.com/run), service `lorenzo-api`, region `europe-west1` | Scale-to-zero container hosting, genuine permanent free tier — see ADR 0011 |
| Database | [Neon](https://neon.tech), pooled Postgres connection | Permanent free tier, autoscale-to-zero, wakes on next connection |
| Image registry | Google Artifact Registry, `europe-west1-docker.pkg.dev/lorenzo-medici-api/lorenzo-api/api` | Where built images live; Cloud Run pulls from here |
| Auth bridge | Workload Identity Federation (`github-pool`/`github-provider`) | GitHub Actions authenticates as `github-deployer@lorenzo-medici-api.iam.gserviceaccount.com` via a short-lived OIDC token — no long-lived cloud credential ever stored as a GitHub secret |

The deployed container is the same `apps/api/Dockerfile` image whether you build it locally or CI builds it — one artifact, not a separate "prod build."

### The pipeline: commit to live revision

Triggered by `.github/workflows/deploy-api.yml`, on any push to `main` touching `apps/api/**` or `packages/calendar-engine/**` (the API image bundles the calendar engine), or manually via `workflow_dispatch`:

1. **verify** — the same lint + test job as `ci.yml`, against its own ephemeral Postgres service container. A broken push can't reach deploy.
2. **auth** — `google-github-actions/auth@v3` exchanges the workflow's OIDC token for short-lived GCP credentials, scoped to exactly this repo (enforced by the Workload Identity Provider's `attribute-condition`).
3. **build & push** — `docker/build-push-action` builds `apps/api/Dockerfile` and pushes it to Artifact Registry, tagged with the commit SHA (immutable, traceable back to an exact commit — never `latest`).
4. **migrate** — `alembic upgrade head` runs directly from the GitHub Actions runner against Neon, connected as a privileged role (`MIGRATIONS_DATABASE_URL`), *before* anything is deployed. A bad migration stops the pipeline here; it never reaches a live revision.
5. **deploy** — `google-github-actions/deploy-cloudrun` points the `lorenzo-api` Cloud Run service at the freshly-pushed image, passing `DATABASE_URL` as a runtime environment variable — a separate, restricted role RLS actually applies to ([ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)), not the privileged one migrations just ran as — alongside the `AUTHGEAR_*` metadata URLs and `CORS_ALLOWED_ORIGINS` ([ADR 0048](../adr/0048-cors-configuration.md), space-separated allowed origins, defaulting to none if the `CORS_ALLOWED_ORIGINS` GitHub variable isn't set).
6. **verify deployment** — the workflow itself curls the deployed revision's `/readyz` before declaring success, so a broken revision is caught in the same run, not silently.

See this as diagrams: [deployment topology](diagrams/deployment.md), [CI/CD pipeline flowchart](diagrams/ci-cd-pipeline.md).

### Local vs. deployed, at a glance

| | Local | Deployed |
| --- | --- | --- |
| App process | Runs on the host directly, autoreload | Containerized, immutable image per commit SHA |
| Port | Fixed `8000` | Cloud Run's `$PORT` (currently `8080`), read at container start |
| Database | Docker Compose Postgres, plain connection | Neon, TLS required (`ssl=require`) |
| Migrations | Run by hand (`alembic upgrade head`) against the full domain model, dozens of migrations and counting | Applied automatically, pre-deploy, every push |
| Access | Whatever's on your machine | Network access is public/unauthenticated by design (`--no-invoker-iam-check`, Cloud Run's own IAM layer) — app-level auth (Authgear bearer tokens, [ADR 0009](../adr/0009-identity-provider-authgear.md)/[ADR 0023](../adr/0023-authgear-token-verification.md)) is required by every tenant-scoped route regardless |
| Tracing/metrics | Console only; nothing scrapes `/metrics` | Same code path — console output lands in Cloud Logging; still nothing scrapes `/metrics` — see [observability](observability.md) |

The `ssl=require` row is doing real work: Neon's connection strings default to libpq-style query parameters (`sslmode`, `channel_binding`) that asyncpg doesn't understand by name — `apps/api`'s `Settings` normalizes them automatically (see `config.py`), so this isn't something you configure by hand.

## apps/loot-bot

### Local development

- **App**: runs directly on the host — `pnpm exec tsx --env-file=.env watch src/index.ts` (via `mise run //apps/loot-bot:dev`). A plain HTTP service (`/livez`, `/auth/callback`, `/interactions`) — no Gateway connection, no `discord.js` `Client` ([ADR 0053](../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)). Listens on `LOOT_BOT_HTTP_PORT` (default `8090`).
- **Database**: the same Postgres instance `apps/api` uses (`infra/docker-compose.yml`), a separate role/schema (`loot_bot`/`loot_bot`, [ADR 0050](../adr/0050-loot-bot-stack-linking-and-isolation.md)) — never `apps/api`'s own `lorenzo_app`/`lorenzo`.
- **Exercising `/interactions` locally** needs a real Discord signature, which needs a real request from Discord itself - there's no local Discord dev server. In practice this means pointing the Discord application's Interactions Endpoint URL at a public tunnel (e.g. an `ngrok`-style tunnel to `LOOT_BOT_HTTP_PORT`) for local testing, the same real-external-dependency shape `/auth/callback`'s Authgear redirect already has.

### Production

| Piece | What | Why |
| --- | --- | --- |
| Compute | [Google Cloud Run](https://cloud.google.com/run), service `lorenzo-loot-bot`, same project/region as `apps/api` | True scale-to-zero fits now that the bot is a stateless HTTP service, not a persistent Gateway connection — ADR 0053 |
| Database | The same [Neon](https://neon.tech) instance `apps/api` uses, `loot_bot` role/schema | One Postgres to operate, not two |
| Image registry | Google Artifact Registry, `<region>-docker.pkg.dev/<project>/lorenzo-loot-bot/loot-bot` | A dedicated repo, same project as `apps/api`'s own `lorenzo-api` repo |
| Auth bridge | The *same* Workload Identity Federation pool/provider/service account `apps/api` uses | Already project-scoped, not service-scoped — a second Cloud Run service needed no new IAM setup |

### The pipeline: commit to live revision

Triggered by `.github/workflows/deploy-loot-bot.yml`, on any push to `main` touching `apps/loot-bot/**` or `packages/api-client/**` (or manually via `workflow_dispatch`) - the same six-step shape as `apps/api`'s own pipeline above, with one deliberate deviation: the migration step runs `pnpm exec tsx src/migrate.ts` directly rather than through `mise run db-migrate`, since that task's own script hardcodes `--env-file=.env`, which errors when the file doesn't exist - true in this checkout, since `.env` is gitignored.

See [docs/operations/deployment-setup.md](../operations/deployment-setup.md#appsloot-bot-adr-0053) for the one-time setup this depends on, including the real chicken-and-egg step (`LOOT_BOT_PUBLIC_BASE_URL` isn't known until after the first deploy creates the service), and [deployment topology](diagrams/deployment.md#appsloot-bot) for this as a diagram.

## Static apps on Cloudflare Pages

`apps/account-hub`, `apps/inventory-web`, `apps/beings`, `apps/bench`, `apps/calendars` and `apps/sessions` are plain static builds (`astro build` → `dist/`) — no container, no database, no GitHub Actions deploy step at all, per [ADR 0004](../adr/0004-static-astro-frontend.md) and [ADR 0071's addendum](../adr/0071-account-hub-stack-auth-deploy.md#addendum-2026-09-19-cloudflare-pages-git-integration-not-wrangler-action-token-upload). Each has its own Cloudflare Pages project wired to **Cloudflare's own Git integration**, which builds and redeploys directly on every push to `main` that touches the app or one of its watched packages — `ci.yml`'s auto-discovered matrix still covers `mise run lint`/`test` (and, for some, an end-to-end suite) on every PR, but nothing in `.github/workflows/` triggers or gates the Cloudflare deploy itself. `apps/brand`, the static shared-brand preview, uses the same mechanism without a build step; other apps bundle its assets through `packages/brand` ([ADR 0098](../adr/0098-branding-css-app-and-package.md)).

Every one of them needs three things outside the repository: a Pages project, a public Authgear client (PKCE, callback addresses with a trailing slash), and its origin in the API's `CORS_ALLOWED_ORIGINS`. Where each stands:

| App | Pages project | Status and setup |
| --- | --- | --- |
| `apps/account-hub` | `lorenzo-account-hub` | Deployed. [deployment-setup.md](../operations/deployment-setup.md#cloudflare-pages-appsaccount-hub) |
| `apps/inventory-web` | `lorenzo-inventory-web` | Deployed. [deployment-setup.md](../operations/deployment-setup.md#cloudflare-pages-appsinventory-web) |
| `apps/bench` | `lorenzo-bench` | Stack and deployment decision in [ADR 0210](../adr/0210-bench-app-stack-and-workbench-shell.md); setup in [deployment-setup.md](../operations/deployment-setup.md#cloudflare-pages-appsbench) |
| `apps/beings` | `lorenzo-beings` | Built and tested, but its Authgear client and Pages project do not exist yet: [beings-setup.md](../operations/beings-setup.md) |
| `apps/calendars` | `lorenzo-calendars` | [calendars-setup.md](../operations/calendars-setup.md) records the setup and names `https://lorenzo-calendars.pages.dev` as the production app |
| `apps/sessions` | `lorenzo-sessions` | [sessions-setup.md](../operations/sessions-setup.md) is the runbook for the Pages project and Authgear client; Sessions is not deployed by merging its pull request, and the address in the registry is a planned fallback until it is set up |
| `apps/brand` | `lorenzo-brand` | [deployment-setup.md](../operations/deployment-setup.md#cloudflare-pages-appsbrand) |

The apps' addresses, and the links between them, come from the API's registry of app links, `GET /app-links` ([ADR 0273](../adr/0273-app-links-registry.md)): an address set through `ACCOUNT_HUB_URL`, `INVENTORY_WEB_URL`, `BEINGS_URL`, `BENCH_URL`, `CALENDARS_URL` or `SESSIONS_URL` wins, otherwise the official `https://lorenzo-<app>.pages.dev` is used. The topology is in the [static apps diagram](diagrams/deployment.md#static-apps-on-cloudflare-pages).

## Native apps

Neither native app is deployed to a store or a server.

- **`apps/inventory-mobile`** is a native Kotlin/Compose Android app, distributed in this slice by installing a locally built debug APK. It calls the same REST API and connects through account hub's device-code flow or a personal access token. There is no mobile deployment workflow, store publishing or release-signing setup in this slice; see its [README](../../apps/inventory-mobile/README.md) and [ADR 0291](../adr/0291-inventory-mobile-native-android-app.md).
- **`apps/inventory-ios`** is a native SwiftUI app for iOS 17 and later ([ADR 0307](../adr/0307-inventory-ios-and-altstore-testing.md)). CI builds it on a macOS runner (`ios-build`) and uploads an unsigned device IPA as a short-lived artifact; it is signed locally and installed with AltStore Classic on a free Apple account. TestFlight and App Store publishing are outside this slice. The steps, and what needs a physical device, are in its [README](../../apps/inventory-ios/README.md).
