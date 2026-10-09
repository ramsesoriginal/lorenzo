# 0210 - Bench: the app, its stack, and the workbench shell first

Status: accepted, decided with the maintainer on 2026-10-09. Slice B1 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md), and the first slice (W-A) of [RFC 0042](../rfcs/0042-bench-workbench-interface.md). Builds on [ADR 0004](0004-static-astro-frontend.md) and [ADR 0071](0071-account-hub-stack-auth-deploy.md).

## Context

[RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) decided what Bench is; [RFC 0042](../rfcs/0042-bench-workbench-interface.md) what it looks like, from a prototype under [docs/design/bench](../design/bench/README.md). Authgear's client and a Pages project are the maintainer's to create, so the app starts with the part that needs neither.

## Decision

- **`apps/bench`** is a static Astro app, as [ADR 0004](0004-static-astro-frontend.md): one page, a bundle of own small TypeScript, no component framework. Biome, `astro check`, Prettier for `.astro` and Vitest, as `apps/inventory-web`.
- **Logic is pure and tested without a DOM.** The workspace (groups, splits, floating windows, moves, resize, hit test) is plain data and functions under `src/workspace/`; rendering and pointer handling are a thin layer over it.
- **The shell starts on stub data**, with no API, no sign-in and no deployment. The first slice is the workspace model, its tests, and a shell that docks, splits, floats, resizes and persists the layout, with a palette and an explorer over a stub list. Sign-in, the repository picker and the command layer are B2 and B3.
- **Service worker for Bench only** is still to come with B4, as an addendum to [ADR 0071](0071-account-hub-stack-auth-deploy.md); this ADR adds none.
- **Layout is saved on the device**, per browser, with a version number so a changed shape is dropped rather than misread.
- **Scope label** `app:bench` exists. Deployment (a Cloudflare Pages project) waits for the maintainer; until then the app builds and tests in CI only.

## Consequences

- The shell can be reviewed and used before the API work it will sit on.
- Pointer and keyboard handling is the part not covered by pure tests; it is covered by Playwright against the built static page, with no API.
- If the workspace model turns out to be useful to another app it is extracted to `packages/` then, not before.
