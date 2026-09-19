# 0071 - account-hub: stack, auth, deploy, and e2e testing

Status: accepted

## Context

[RFC 0013](../rfcs/0013-account-hub-app.md) scopes `apps/account-hub` — a user's own profile/notifications/tenant/campaign/character/being surface — but deliberately leaves technology choices to be decided and merged one at a time, per [ADR 0070](0070-planning-milestones-issues-and-a-deferred-roadmap.md)'s early-merge convention. This is the first of those: the app's foundation, needed before any real page can be built.

[ADR 0004](0004-static-astro-frontend.md) already decided every web frontend in this repo is a static Astro app, and [`apps/inventory-web`](../../apps/inventory-web) is a real, working, already-deployed proof of that decision against this exact backend and this exact Authgear project — its `src/lib/auth.ts`/`api.ts`/`config.ts`, `astro.config.mjs`, `mise.toml` task contract, and `deploy-inventory-web.yml` workflow are proven, not hypothetical. Per [docs/guides/adding-an-app.md](../guides/adding-an-app.md)'s step 2, the language/framework/scope needed confirming with the user first — done, across a structured multi-option debate (RFC 0013's Context) and follow-up conversation that explicitly favored the *thinnest* viable stack over the debate's own initial framework-heavy first pass.

One gap: this repo has no browser end-to-end test tool today (`apps/api` tests over real HTTP with `pytest`, `apps/loot-bot` uses Vitest+MSW mocking, `apps/inventory-web` has no e2e yet at all). Per the user's own instruction to flag any pattern not already in this repo as its own decision, this ADR decides that too rather than adding it quietly.

## Decision

### App: `apps/account-hub`, forking `apps/inventory-web`'s pattern directly

| Concern | Choice | Why |
| --- | --- | --- |
| Framework | Astro 7.3.x, `output: 'static'` | ADR 0004, unchanged; identical `astro.config.mjs` to `apps/inventory-web` |
| Language | TypeScript | ADR 0004; consistent with every other TS app in the monorepo |
| Client-side interactivity | Plain inline `<script>` / vanilla TS — **no component framework** (no Preact, no React) | ADR 0004's own preference ("plain inline script... over reaching for a component framework at all"); `apps/inventory-web` itself has zero framework dependency, confirming this isn't a new departure but the existing norm; the one genuinely dynamic piece (the being stat editor's key/value rows) is ordinary controlled-array DOM manipulation, not complex enough to need one |
| Installability | None for v1 — no `vite-pwa`/service worker | No offline use case exists (pure CRUD-over-REST); a manifest+service-worker can be hand-added later in a few lines if wanted, not a dependency |
| Auth | `@authgear/web` ^6.0.0, forked from `apps/inventory-web/src/lib/auth.ts` near-verbatim | Already proven end-to-end against the real Authgear Cloud project (ADR 0009/0023/0027); a new client needs its own registered Authgear application (different redirect origin) — see Consequences |
| API client | Forked from `apps/inventory-web/src/lib/api.ts`, plus a new `apiPatch` (that file has no PATCH helper, needed for `PATCH /me`) | Same typed-fetch-with-bearer-token shape, no reason to diverge |
| Styling/brand | Forked `styles/*.css`, `layouts/Base.astro`, `public/` brand assets | Already tokenized per [docs/brand/identity.md](../brand/identity.md); this app has no reason to re-derive the palette/type system |
| Lint/format | Biome + `astro check` + Prettier (`.astro`) | Identical to `apps/inventory-web`, per ADR 0004 |
| Unit tests | Vitest | Matches `apps/inventory-web` and `apps/loot-bot` |
| **E2E tests** | **Playwright** — new to this repo, decided here explicitly | This app's core scenarios (login round-trip, profile edit, character/being creation) are real browser flows over a real API, closer in spirit to `apps/api`'s own "real HTTP, no reimplemented behavior" testing culture than to `apps/loot-bot`'s mocked-HTTP unit style; Playwright is the current, actively-maintained standard for this, run against a real (or locally-run) `apps/api` rather than mocking the thing under test |
| Deploy | Cloudflare Pages via `wrangler-action`, forked from `deploy-inventory-web.yml` | Same static-build-and-push shape; new Cloudflare Pages project name (`lorenzo-account-hub`) |

### A new Authgear application is required (manual, outside this repo)

Authgear redirect URIs are exact-match per registered client, so `apps/account-hub` cannot reuse `apps/inventory-web`'s client ID once deployed to its own origin. A new OIDC client (public, PKCE, no secret) must be registered in the same Authgear Cloud project, with its redirect URI(s) pointing at this app's own dev and production origins. This is a one-time, human-driven console step (same category ADR 0023 already named for the original Authgear setup) — not something this ADR's implementation can do itself.

### `apps/inventory-web`'s domain code is not reused

Its `lib/types.ts`, `lib/characters.ts`, `lib/items.ts`, `lib/tenants.ts`, and pages are all shaped around one tenant's inventory board. `apps/account-hub`'s data shape (the caller's own account, across every tenant/campaign) is different enough that only the auth/api/config/styling *infrastructure* is forked — new domain types and pages are written fresh per RFC 0013's sub-slices.

## Consequences

- Mechanical checklist from [docs/guides/adding-an-app.md](../guides/adding-an-app.md) — `apps/account-hub/mise.toml` task contract, root `mise.toml`'s `config_roots`, `release-please-config.json` entry, `.github/dependabot.yml` npm entry, `.pre-commit-config.yaml` local hooks (mirroring the three `*-inventory-web` hooks), `deploy-account-hub.yml`, a new `app:account-hub` label — lands together with the Foundation slice's implementation, not as a separate step.
- `pnpm-workspace.yaml` needs no change (`apps/*` already covers it).
- Registering the new Authgear application, and setting `PUBLIC_AUTHGEAR_ENDPOINT`/`PUBLIC_AUTHGEAR_CLIENT_ID` (locally in `.env` and as Cloudflare Pages build variables), blocks any real end-to-end auth testing until done — flagged to the user as an explicit manual dependency, not assumed complete.
- Playwright's real browser dependency (a Chromium/Firefox/WebKit download) is a genuinely heavier CI dependency than anything `apps/inventory-web`/`apps/loot-bot` currently install — acceptable, but worth naming: `ci.yml`'s `test` job for this app will take longer than the others.

## Addendum (2026-09-19): Cloudflare Pages Git integration, not `wrangler-action` token upload

Surfaced trying to actually set this up: Cloudflare's current Pages onboarding leads with **Connect to Git**, not the direct-upload flow `deploy-inventory-web.yml`/`deploy-account-hub.yml` were forked around — `CLOUDFLARE_ACCOUNT_ID` isn't surfaced in that flow the way this ADR's own Decision table assumed. Neither app had actually completed Cloudflare setup at the time this was found (`CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` didn't exist as GitHub secrets/variables, and `deploy-inventory-web.yml`'s one real run failed before reaching the deploy step at all, on an unrelated missing-`corepack enable` bug) — so this is a revision to an undeployed plan, not a migration of a working one.

**Revised deploy mechanism for `apps/account-hub`**: Cloudflare Pages' own Git integration builds and deploys directly from pushes to `main`, independent of GitHub Actions. `deploy-account-hub.yml` is removed - its `verify` job duplicated `ci.yml`'s own auto-discovered per-app matrix (already covers `mise run lint`/`test` for `apps/account-hub` on every PR and push to `main`), and its `deploy` job's job disappears along with the mechanism it drove.

**Why the monorepo/pnpm-workspace shape isn't a problem**: Cloudflare's "Root directory" build setting still clones the full repository, only changing the working directory build commands run from — `pnpm install --frozen-lockfile` from `apps/account-hub` still discovers the true workspace root's `pnpm-workspace.yaml` (pnpm walks up looking for it, unlike npm/yarn), so the root's `allowBuilds`/`minimumReleaseAgeExclude` config still applies. No `--filter`/root-level install trick needed - the build command is exactly `mise.toml`'s own `install`→`build` task chain, just invoked directly (`corepack enable && pnpm install --frozen-lockfile && pnpm run build`) since Cloudflare's build environment has no reason to install `mise` itself for a plain static build.

**Where `PUBLIC_AUTHGEAR_ENDPOINT`/`PUBLIC_AUTHGEAR_CLIENT_ID` actually go**: each Cloudflare Pages project has its own isolated **Settings → Environment variables** page - so this ADR's own Consequences section ("as Cloudflare Pages build variables") was directionally right, just written before it was clear *how* those variables would reach the build. Because each Pages project's variables are scoped to that project alone, `apps/inventory-web`'s and `apps/account-hub`'s own same-named `PUBLIC_AUTHGEAR_*` variables never collide - no GitHub-Actions-variable app-prefixing scheme is needed the way it would have been under the old token-upload mechanism (where both apps' builds ran in the same GitHub Actions/`vars.*` namespace).

See [docs/operations/deployment-setup.md](../operations/deployment-setup.md) for the concrete one-time setup steps this implies.

## Addendum (2026-09-19, later): Cloudflare Pages' trailing-slash redirect breaks login - fix is in `auth.ts`, not `astro.config.mjs`

Surfaced by the first real login attempt against the deployed `apps/account-hub`: the token exchange failed with `400 {"error":"invalid_request","error_description":"invalid redirect URI"}`, even though the Authorized Redirect URI was registered correctly.

**Root cause, confirmed against the live deploy**: Cloudflare Pages 308-redirects *any* extensionless path to add a trailing slash (`/auth/redirect` → `/auth/redirect/`) - **this is a fixed platform behavior independent of the underlying file layout**, not a directory-vs-flat-file artifact as first assumed. Proven directly: `curl` against `/auth/redirect.html` (a literal file) returns `200` immediately with no redirect, while `curl` against `/auth/redirect` still 308s even when the deploy's `dist/` only contains a flat `auth/redirect.html` (no `index.html` directory at all). The first attempted fix (`build.format: 'file'` in `astro.config.mjs`, to avoid Astro's default `page/index.html` directory output) was reverted - it didn't change Cloudflare's redirect behavior at all, because that behavior isn't derived from the file layout to begin with.

Because the browser is forced to the slash form before this app's own JS runs, `@authgear/web`'s `finishAuthentication()` reconstructs the token exchange's `redirect_uri` from the now-slash-suffixed `window.location` - which no longer exact-matches a no-slash Authorized Redirect URI.

**Actual fix**: match Cloudflare's canonical form instead of fighting it. `auth.ts`'s `REDIRECT_PATH` is now `/auth/redirect/` (trailing slash) in both `apps/account-hub` and `apps/inventory-web` (identical bug, same pattern, fixed proactively rather than waiting to hit it twice) - so the *initial* `startAuthentication` call already requests the slash form, matching what the browser will end up at either way. The Authorized Redirect URI registered in each app's Authgear application must also include the trailing slash (`docs/operations/deployment-setup.md` updated accordingly). Astro's dev server handles both forms transparently for a page defined at `src/pages/auth/redirect.astro` (confirmed locally), so this needed no route-file change.
