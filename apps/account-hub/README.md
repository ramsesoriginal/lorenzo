# Lorenzo — Account Hub

Static Astro frontend for a user's own account: profile, notifications,
which tenants/campaigns they belong to, and character/being management —
backed directly by the deployed [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json).
See [RFC 0013](../../docs/rfcs/0013-account-hub-app.md) (scope) and
[ADR 0071](../../docs/adr/0071-account-hub-stack-auth-deploy.md) (stack,
auth, deploy — forked from [`apps/inventory-web`](../inventory-web)).

## Commands

Run from this directory, or via `mise run //apps/account-hub:<task>` from the
repo root:

| Command | Action |
| --- | --- |
| `mise run dev` | Start the dev server at `localhost:4322` |
| `mise run lint` | Biome + `astro check` + Prettier (`.astro`) |
| `mise run format` | Autoformat |
| `mise run test` | Run the unit test suite (Vitest) |
| `mise run test-e2e` | Run the e2e test suite (Playwright) — needs a running `apps/api` and a configured Authgear session, see ADR 0071 |
| `mise run build` | Build the static site to `dist/` |

## Deploy

Cloudflare Pages, via its own Git integration (no GitHub Actions step) — see
[docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md#cloudflare-pages-appsaccount-hub)
for the one-time setup.

## API client and tenant slugs

All requests use `@lorenzo/api-client` and its generated schema (ADR 0122/0136).
Owners and organizers can edit a tenant's slug on the tenants page. The editor
checks for concurrent edits; changing a slug leaves its name unchanged and stops
links using the previous slug from resolving.

## Real API browser tests

Run `mise run //apps/account-hub:test-real-api` with the local Postgres from
`infra/docker-compose.yml` and a Playwright Chromium installation (or
`E2E_BROWSER_CHANNEL=msedge` to use an installed Edge). The suite builds the
site, starts the real API and a fake Authgear, and recreates only
`lorenzo_account_hub_e2e`. It reuses inventory-web's ADR 0114 test launchers;
run the two apps' browser suites separately because they use the same ports.
The existing `test-e2e` task remains the logged-out page smoke suite.
