# 0004 - Web frontends are static Astro sites

Status: accepted

## Context

Web frontend(s) must ship as static files only — no server-side rendering at request time — and should use as little JavaScript as the UI genuinely needs, while still being composed of reusable parts. There may be more than one web frontend (see [ADR 0007](0007-apps-layout-and-multiplicity.md)) — e.g. a GM-facing console and a simpler player-facing view could reasonably be separate apps rather than one app with role-based branching.

## Decision

Each web frontend, whenever it's built, is an Astro app with `output: 'static'`. Pages/components are authored in `.astro` + TypeScript; nothing hydrates unless a component explicitly needs client-side interactivity (an "island"). Where a plain inline script suffices, that's preferred over reaching for a component framework at all.

## Consequences

- Deploys as plain files to any static host — not decided yet which one, and it can differ per app.
- Biome is the intended linter/formatter for `.ts`/`.js`/`.json`/`.css`; Biome's `.astro` support is still experimental as of this decision, so Prettier + `prettier-plugin-astro` are the intended fallback specifically for `.astro` files. Neither is wired up yet — see [ADR 0003](0003-polyglot-monorepo-tooling.md).
- Any future requirement for server-side rendering or secrets at request time means either a different kind of app entirely, or revisiting this ADR — not quietly bolting SSR onto a static one.

Nothing here is implemented yet.
