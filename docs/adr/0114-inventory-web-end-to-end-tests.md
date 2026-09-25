# 0114 - inventory-web end-to-end tests: Playwright against the real API and a fake Authgear

Status: accepted

## Context

inventory-web's tests are Vitest unit tests of the pure functions in `src/lib/`. The pages have none, and most of the app's behaviour lives in them. The board page's script alone is over 1,300 lines, and the Manage items page's nearly 900. Recent bugs were found by hand, and each sat between the page and the API rather than inside a pure function:

- instances not showing their prototypes' descriptions;
- writing a description renaming the item "Description";
- the edit panel copying the display title onto the name.

[ADR 0071](0071-account-hub-stack-auth-deploy.md) already brought Playwright into the repo for account-hub, to run "against a real (or locally-run) `apps/api` rather than mocking the thing under test". Its tests only load pages while logged out, though, and they don't run in CI: nothing supplies a session. The API's tests and loot-bot's already settle the auth question. Each runs a local fake issuer with a real key and real verification: `apps/api/tests/_fake_jwks.py` and `apps/loot-bot/tests/fake-authgear-server.ts`.

## Decision

### Three real servers and a fake issuer

`apps/inventory-web/tests/e2e/` holds Playwright tests (Chromium only). They drive the real app against a real stack:

- **The built site.** `astro build`, served by `astro preview`, with `PUBLIC_API_BASE_URL` and `PUBLIC_AUTHGEAR_ENDPOINT` pointing at the two servers below.
- **The real `apps/api`,** under uvicorn. It uses a database of its own (`lorenzo_e2e` by default), dropped, recreated and migrated with Alembic at the start of each run. The API verifies tokens exactly as in production, through `AUTHGEAR_ISSUER`, `AUTHGEAR_JWKS_URL`, `AUTHGEAR_AUDIENCE` and `AUTHGEAR_USERINFO_URL`, and allows the site's origin via `CORS_ALLOWED_ORIGINS`.
- **A fake Authgear,** `tests/e2e/support/fake-authgear.ts`. It serves:
  - the discovery document;
  - an authorize endpoint that redirects straight back with a code for the subject named in a cookie on its own origin, so there's no login form;
  - a token endpoint that checks PKCE and handles refresh grants;
  - JWKS, userinfo, revocation, and end-session.

  Tokens are RS256, signed with a key made for the run. Only the issuer is fake, as in the two precedents. The real `@authgear/web` SDK runs unmodified, and the app has no test hooks.

Playwright's `webServer` starts and stops all three.

### Each test builds its own world

A test creates what it needs through the API itself, with a typed client over the same generated schema (`src/lib/lorenzo-schema.d.ts`). Tokens are minted by the fake Authgear for fresh subjects, and the new users are provisioned the way real ones are.

A fixture builds the usual world:

- a tenant and a campaign;
- a GM holding a GM grant;
- players with characters and containers;
- catalog items with prototypes, descriptions, and instances.

Every test gets its own tenant and users, so tests can't see each other, and they run in parallel.

The browser logs in through the app's real login button and redirect page. Tests find elements by role and label, the way a user or a screen reader does, rather than by test ids. A control a test can't name is a finding in itself.

### What the tests cover

Every page, as the player or GM who uses it:

- logging in, and picking a tenant and a character;
- **the board:** columns and cards, the detail panel, give, move, split, merge, undo, search, and multi-select bulk moves;
- **the item page:** the whole-item view with inherited descriptions, copy link, and "Mentioned in";
- **GM editing on the item page:** the description with its display title, tags, the information manager, and slugs;
- **Manage items:** creating and editing items with parents, a description and a slug; deleting; instantiating; and reassigning, unassigning and deleting instances;
- **notes ([ADR 0113](0113-inventory-web-slugs-and-player-notes.md)):** a player adds, edits and deletes their own; a private note stays hidden from another player; a public one is shown to them;
- **gating:** GM-only pages and controls stay hidden from players.

Bugs the tests find are fixed in the same change.

### Running them

- **Locally,** `mise run //apps/inventory-web:test-e2e` against the compose Postgres from `infra/docker-compose.yml`. `E2E_POSTGRES_URL` points elsewhere.
- **In CI,** a new `e2e` job in `ci.yml` runs the same task:
  - with the same Postgres service as `test`;
  - after `playwright install --with-deps chromium`;
  - uploading Playwright's report and traces when it fails.
- **Gate.** `ci-summary` counts it, so it gates merges like the other jobs.
- **Kept apart.** It isn't part of `mise run test`, which stays free of Postgres and Python for this app. Vitest ignores `tests/e2e/`, as in account-hub.

## Not in scope

- Firefox and WebKit. One engine catches the integration bugs this is for, at a third of the time.
- account-hub's tests. They can adopt the fake Authgear later. It moves to `packages/` once a second app uses it, not before (AGENTS.md: no speculative shared code).
- Visual regression screenshots.

## Consequences

- inventory-web's pages are tested against the API they actually talk to, so a contract drift fails CI rather than a GM's session.
- CI gains its slowest job: an API environment, a site build, and a browser. It runs in parallel with the others, so it lengthens a PR's wait only when it's the last to finish.
- A test's world is built through the public API. Seeding therefore breaks when the API breaks, which is a signal worth having rather than a cost.
