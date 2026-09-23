# 0098 - Branding CSS: apps/brand + packages/brand, same-origin default

Status: accepted

## Context

[Discussion #133](https://github.com/ramsesoriginal/lorenzo/discussions/133)'s third proposal named a real, confirmed problem: `apps/inventory-web` and `apps/account-hub` already carry a byte-identical, independently-copied `tokens.css`/`base.css`, and a third frontend is a named possibility (ADR 0007). `docs/brand/identity.md` §6.6 is now the authored source of truth for the actual semantic color/spacing/radius/shadow values (see the `feat/branding-refinement` work, merged in PR #176) — this ADR is about how those values actually reach running apps instead of being hand-copied into each one.

The discussion also named the real tradeoff up front: a build-time npm dependency is safe and independent but needs every consumer redeployed to see a change; a runtime-hotlinked stylesheet propagates instantly but creates a live uptime coupling between every frontend and wherever it's served from. This project is AGPL-3.0 — self-hosting is a first-class use case (README, LICENSE) — so a design that only works by pointing every deployment at one centrally-run host is a real regression for anyone who forks and runs their own copy.

Prior art for exactly this shape of problem: [stoatchat/for-web#1356](https://github.com/stoatchat/for-web/issues/1356) hit a hardcoded-CDN-breaks-self-hosting bug and fixed it with a `VITE_STATIC_URL` build-time env var defaulting to the official host, overridable to a self-hoster's own mirror. BentoPDF (also AGPL) uses the same family of build-time URL-override flags.

## Decision

Two new things, one hand-edited source:

- **`apps/brand`** — a plain static site, no framework and no build step: `tokens.css` (the real, hand-edited file) plus `preview/*.html` pages that `<link>` to it via a relative path, so they open and render correctly straight off disk via `file://` with no server running, the same way `docs/brand/assets/showcase/index.html` already does. Deployed to Cloudflare Pages via Git integration (no GitHub Actions workflow needed — same exception already used for `inventory-web`/`account-hub`, see [docs/guides/adding-an-app.md](../guides/adding-an-app.md)).
- **`packages/brand`** — a thin npm package (`@lorenzo/brand`) whose only job is making `apps/brand/tokens.css` `pnpm add`-able by other apps in the workspace for build-time bundling. Its `mise.toml` `build` task copies `../../apps/brand/tokens.css` into itself; that copy is `.gitignore`d (never hand-edited, never committed) and removable on demand via a separate `mise run //packages/brand:clean` task. Consuming apps that need the file present just need `packages/brand:build` to have run first (a `depends` relationship, same mechanism `install` already is for `lint`/`test`/`build` in the existing app `mise.toml`s) — deleting it automatically on every build was considered and rejected: the file has to still exist when a *consumer's* build reads it through the pnpm workspace symlink, so "delete right after copying" would delete it before anything downstream ever saw it.

Consuming apps read a `PUBLIC_BRANDING_CSS_URL` config value (Astro's `PUBLIC_`-prefixed env var convention, so it's available client-side) that defaults to a same-origin path, `/branding/tokens.css` — that app's own build copies its `packages/brand`-sourced file to `public/branding/tokens.css` so the default requires zero new runtime dependency and works out of the box for any self-hoster. Setting the var to an absolute URL (e.g. `apps/brand`'s own deployed Cloudflare Pages URL) opts a given deployment into the runtime-hotlinked, instant-propagation behavior across every app pointed at it — this project's own reference deployment is expected to do exactly that once this lands, but nothing forces it.

## Not in scope

- Actually wiring `PUBLIC_BRANDING_CSS_URL` into `inventory-web`/`account-hub` and dropping their own hand-copied `tokens.css` — a follow-up sub-slice once `apps/brand`/`packages/brand` exist and the content in them is proven.
- A DTCG-format token source + Style Dictionary build step. Deliberately deferred until a second, non-CSS consumer of the same token values actually exists (e.g. a future native mobile app) — building that pipeline now would be speculative given every current and named-future consumer is CSS.
- An immutable, version-pinned URL path (e.g. `/v/2026-09-23/tokens.css`) that could carry Subresource Integrity — real prior-art tension (SRI hash-pinning and "this URL updates instantly" are mutually exclusive on the same URL), deferred until a self-hoster actually asks for that guarantee.
- Publishing `packages/brand` to a public npm registry. It's consumed inside this monorepo via the pnpm workspace's own `workspace:*` protocol only, for now.
- The one-time Cloudflare Pages project setup itself (tracked the same way as the existing `inventory-web`/`account-hub` one-time setup, in `docs/operations/deployment-setup.md`, once there's something real to deploy).

## Consequences

- Editing the actual design tokens is editing one plain CSS file with no build step and an instant local preview — no framework, no dev server, no compile step between a change and seeing it.
- `apps/brand` and `packages/brand` both trace to that one file, so there's exactly one thing to keep in sync with `identity.md` §6.6, not two.
- `packages/brand`'s working tree is only "clean" (no generated file present) right after an explicit `clean` run, or before the first `build` — this is a deliberate, documented manual step, not automatic, since automatic deletion on every build would need to run *after* every possible consumer's build too, which isn't something `packages/brand` itself can know about or trigger.
- Adds `packages/*` to `pnpm-workspace.yaml` for the first time (already anticipated there, per `docs/guides/adding-a-package.md`'s own comment placeholder).
- A self-hoster's default deployment gains zero new runtime dependencies; only a deployment that deliberately points multiple apps at one shared `apps/brand` host takes on the uptime coupling the original discussion flagged, and does so by explicit choice rather than by default.
