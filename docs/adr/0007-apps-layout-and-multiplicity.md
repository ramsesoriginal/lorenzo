# 0007 - apps/ layout: one directory per deployable app, multiplicity per type

Status: accepted

## Context

The first pass at this foundation treated `apps/api`, `apps/web`, `apps/bot`, `apps/mobile` as four fixed, singular slots. That's wrong for this project: there may be one or many web frontends (e.g. a GM console and a separate player-facing view), multiple mobile apps, and at least one Discord bot, possibly more than one. A fixed slot per type can't represent that, and nothing recorded it as an open question the first time.

## Decision

`apps/` holds one directory per deployable application, named by its actual purpose, not its type: `apps/gm-console`, `apps/player-companion`, `apps/loot-bot` — not `apps/web`, `apps/web2`, `apps/bot`. Any number of apps of the same "kind" (web, mobile, bot) can coexist side by side; nothing about the layout caps this at one.

The one thing every real app provides, regardless of language, is a small task contract in its own `mise.toml`: `dev`, `lint`, `test`, `build`. This is what lets CI (`ci.yml`) and mise's monorepo task fan-out treat every app uniformly and *discover* them (by finding `apps/*/mise.toml`) instead of hardcoding names — adding the Nth app of any type needs zero edits to shared tooling config.

`packages/` is unaffected: it keeps its own convention (extracted generic libraries, own version/tests, no relation to how many apps exist) — see [docs/guides/adding-a-package.md](../guides/adding-a-package.md).

## Consequences

- `apps/api` is the first real example of this convention (named by purpose - it's the one singular backend, not one of many - with the `mise.toml` task contract in place). Everything else under `apps/` is still unbuilt. See [docs/guides/adding-an-app.md](../guides/adding-an-app.md) for the concrete steps for the next one.
- Naming discipline matters more than usual: a purpose-driven name (`gm-console`) has to be chosen deliberately, unlike a type-based name (`web`) that would have been obvious but wrong.
- Anything that assumed "the" web app or "the" mobile app (issue templates, docs, future code) needs to think in terms of categories with multiplicity, not singletons.
