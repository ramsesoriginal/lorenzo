# 0270 - Lorenzo Beings: an app for characters and NPCs

Status: accepted, decided with the maintainer on 2026-10-11.

## Context

The v1.0 checklist has a row for beings' pages and notes on them. A being (a character a player plays, or an NPC) is an entry like an item: it has stats, tags, a description, notes, a picture and owners. Today the places that touch one are narrow:

- account-hub's `/beings` page lists and renames them and hands one to a player ([RFC 0014](../rfcs/0014-account-hub-tenant-admin-and-roster-management.md), [ADR 0079](0079-account-hub-roster-reuse-and-being-handoff.md)); it shows nothing else about a being.
- inventory-web shows a being only as a board of what it carries ([ADR 0131](0131-the-board-on-controlled-by.md)).
- Bench edits entries of a repository, offline, for authors ([ADR 0210](0210-bench-app-stack-and-workbench-shell.md)); it is not for a table's play.

Nobody can read a character's description, see who plays it, write notes on it, or set its stats from a table's side. [ADR 0007](0007-apps-layout-and-multiplicity.md) says each deployable gets its own app named by purpose, and an app is worth having when it can be described by what it is *for*. This one is for **looking at and managing beings**.

## Decision

- **A new app, `apps/beings`, product name "Lorenzo Beings"**, parallel to inventory-web, account-hub and Bench. It is a static Astro site in plain TypeScript, the same stack as inventory-web ([ADR 0004](0004-static-astro-frontend.md), [ADR 0071](0071-account-hub-stack-auth-deploy.md)): `@lorenzo/brand` for the look, `@lorenzo/api-client` for the API, `@lorenzo/lorenzoscript` and its editor for text, Authgear sign-in with the same PKCE pattern and trailing-slash redirect address ([ADR 0211](0211-bench-sign-in-and-the-repository-picker.md)), Vitest for units and Playwright against the real API for the user-facing flows ([ADR 0114](0114-inventory-web-end-to-end-tests.md)). It copies the shape of those apps, not their features; its components are the same pairs of `.astro` markup with `data-*` hooks and a `renderer.ts`.
- **Scope of the first slice**, in three ADRs: the list and a page per being, and notes on beings ([ADR 0271](0271-beings-the-page-and-its-notes.md)); editing a being, its stats, and creating and handing over beings ([ADR 0272](0272-beings-editing-stats-and-handing-over.md)). Everything else about a being (its groups, containers, scenes, the ancestry graph) is for a later slice.
- **Pages.** `/` chooses a library (and opens the only one); `/beings/?tenant=` is the list; `/being/?tenant=&slug=` or `&id=` is one being. A library and a being are addressed by slug or by id ([ADR 0135](0135-slugs-in-inventory-web-addresses.md)). Terminology is [identity §14.3](../brand/identity.md#143-terminology): library, link name (slug), GM only / Everyone / Some characters / Player note, hand over.
- **Permissions come from the API.** The app reads `/me` only to decide which controls to show (a GM of a campaign in the library, a member of it, or a player of the being), the same convenience check inventory-web has; every write is refused or allowed by the API and its message is shown. The app invents no rule of its own.
- **Hosting is not set up yet, and needs no workflow.** The Authgear client and the Cloudflare Pages project do not exist yet. Like its two sibling static apps, the app deploys through Cloudflare's own Git integration ([ADR 0071's addendum](0071-account-hub-stack-auth-deploy.md#addendum-2026-09-19-cloudflare-pages-git-integration-not-wrangler-action-token-upload)): Pages builds and publishes every push to `main` by itself, so there is no `deploy-beings.yml` and no switch to turn on. The build reads the same variables as its siblings (`PUBLIC_AUTHGEAR_ENDPOINT`, `PUBLIC_AUTHGEAR_CLIENT_ID`, `PUBLIC_API_BASE_URL`, `PUBLIC_BRANDING_CSS_URL`). Where the other apps live comes from the API's app-links registry ([ADR 0273](0273-app-links-registry.md)), not from variables of this project. Not signed in or not configured, a page says so instead of failing. [docs/operations/beings-setup.md](../operations/beings-setup.md) is the order of the one-time steps: the Pages project, the Authgear client with its redirect addresses, the variables, CORS.
- **Registered like any app** ([docs/guides/adding-an-app.md](../guides/adding-an-app.md)): its `mise.toml` (`dev`, `lint`, `test`, `build`, `test-e2e`), the root `config_roots`, release-please, Dependabot, pre-commit hooks, and the `app:beings` label in [the labels guide](../guides/labels-milestones-and-metadata.md). It needs nothing in `.github/ci-graph.toml` for its unit tests (its `package.json` says what it uses), and a `beings-e2e` suite there, depending on `apps/api`, gives it a CI job (`e2e-beings`) of its own.
- **End-to-end tests have a launcher of their own.** Unlike account-hub, which borrows inventory-web's launchers and so cannot run beside it, the app has its own fake Authgear, API launcher and site server on ports of its own (4410, 8775, 4341) and its own database name, so both suites can run on one machine, and one CI job cannot disturb the other. The launchers are copies of inventory-web's; the cost is a second copy to keep in step.
- **Local development** runs on port 4323 (inventory-web has 4321, account-hub 4322).

## Consequences

- Beings have a home that grows with them; inventory-web stays about what a being carries and account-hub about the person and the roster.
- A fourth static app to host: another Authgear application (check the free tier's cap), another CORS origin, another Pages project.
- Until the placeholders are filled, the app builds, passes its tests in CI and is deployable by one variable, but is not reachable.
- The launcher copies and the near-copies of inventory-web's components (the information form, the tag, slug and stat editors) are the price of not extracting UI before a second consumer needs it ([ADR 0098](0098-branding-css-app-and-package.md)'s rule); only the stat logic was big and clean enough to extract ([ADR 0272](0272-beings-editing-stats-and-handing-over.md)).
