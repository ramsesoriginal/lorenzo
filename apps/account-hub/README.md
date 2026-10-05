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

## API client and errors

All requests use `@lorenzo/api-client` and its generated schema (ADR 0122/0136).
A failure reaches a page as one `ApiError` (status plus the problem body), and
`describeError` turns it into a sentence for a person: the API's own text, a
`422` as the fields at fault, an ended session with a "Log in" button that
returns to the same page, and "Lorenzo couldn't be reached" for a network
failure. Pages show errors through `showError`/`errorLine` (ADR 0170).

## Libraries, exits and admin basics

Owners and organizers can edit a library's name, slug and description on the
libraries page. The editor checks for concurrent edits; changing a slug leaves
its name unchanged and stops links using the previous slug from resolving.
Anyone with a membership can leave a library, any GM can step down, and
`/profile` can delete the account (it doesn't delete the Authgear login). A
campaign's manager can remove a player and undo a character's roster link (never
its owner's). All of it is asked first with `window.confirm` (ADR 0170).

## Setting up a table, and GM links

`/setup` (ADR 0180) is the quick way to start: one short form (library name,
campaign name, game system, who runs it) makes the library, the campaign, the
GM and a link for your players, and ends on the links, each shown once. "Who
runs it" is you, someone you find by email or nickname, or a **single-use GM
link** (ADR 0177) for someone who has an account or doesn't. The chain is the
calls `/tenants` already makes; a step that fails stops there, says why, and
"Try again" goes on from it without making anything twice. It is offered only
to an account whose `GET /me` says `capabilities.create_tenant`, from the home
page and the empty states of `/tenants` and `/campaigns`.

A campaign's invite panel also offers "Invite a GM" (one person, one use, at
most a week), and `/join/` says whether a link offers a seat as a player or as
a GM before asking anyone to log in.

## Your campaigns

`/campaigns` (ADR 0179) replaces `/overview` and `/characters`, which forward to
it. **Where you play** lists the campaigns where you hold a seat, with your
characters there and the actions a seat has: create, rename, use one of your
characters from another campaign of the library, stop using a linked one, leave.
**Where you run** lists the campaigns you GM and every campaign of a library you
administer (marked GM or Admin), with its players by name and what each plays,
and its GMs; the names come with the campaign's own lists (ADR 0176), so a GM
who holds no library membership sees them too. It reads `GET /me` and
`GET /me/managed`, for libraries only.

## Repositories

A repository (a tenant of kind `repository`, ADR 0178) is its own noun, not a
library. `/tenants` lists libraries as before and gives repositories a section
of their own: rename and edit, their people and invitations, and whether they
are a draft or published (read-only: publishing stays on the CLI). They have no
campaigns, invite links or characters. `/campaigns` lists libraries only;
`/beings` lists a repository's beings for reading, without the hand-off. "Create a library" and "Create a repository" are shown only when
`GET /me` says `capabilities.create_tenant` (ADR 0175).

## Real API browser tests

Run `mise run //apps/account-hub:test-real-api` with the local Postgres from
`infra/docker-compose.yml` and a Playwright Chromium installation (or
`E2E_BROWSER_CHANNEL=msedge` to use an installed Edge). The suite builds the
site, starts the real API and a fake Authgear, and recreates only
`lorenzo_account_hub_e2e`. It reuses inventory-web's ADR 0114 test launchers;
run the two apps' browser suites separately because they use the same ports.
The existing `test-e2e` task remains the logged-out page smoke suite.
