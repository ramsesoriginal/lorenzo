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
| `mise run test-e2e` | Playwright smoke tests of logged-out pages; starts the dev server |
| `mise run test-real-api` | Browser tests against the real API and a fake Authgear; needs local Postgres and Chromium, see below |
| `mise run build` | Build the static site to `dist/` |

## Pages

| Page | What it is |
| --- | --- |
| `/` | Home: where to start |
| `/profile` | Your profile, personal access tokens, account deletion |
| `/notifications` | Your notifications |
| `/tenants` | Your libraries and their campaigns, People and invite links |
| `/campaigns` | Where you play and where you run |
| `/beings` | Each library's beings, linking to Lorenzo Beings |
| `/setup` | Start a table in one form |
| `/join` | Accept an invite link |
| `/repositories`, `/studio`, `/discover` | Shelf, Studio and Discover, below |
| `/device` | Approve a device code |

## Environment

[`.env.example`](.env.example) lists the `PUBLIC_*` variables the build reads: the Authgear endpoint and client id, and optional overrides for the API, shared branding and Lorenzo Beings addresses.

## Deploy

Deployed at <https://lorenzo-account-hub.pages.dev/> on Cloudflare Pages, via its own Git integration (no GitHub Actions step); see
[docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md#cloudflare-pages-appsaccount-hub)
for the setup procedure.

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

A repository is its own noun, distinct from a library. **Shelf** (`/repositories`) shows what a library can copy, with a repository page, built-on outline, copy wizard and row-by-row update inbox (ADR 0196, 0201, 0203). **Studio** (`/studio`) manages repositories: create, People and role/library-access invite links, libraries using it, dependencies, activity, publishing and releases (ADR 0202 to 0213, 0220). Its test-library action lets an Owner view a copy as a subscriber (ADR 0261).

The API stores a repository's profile and cover (ADR 0213); the full Studio profile editor remains RFC 0036 T5. Studio composes a release and offers guarded public/private switches with blocker and revocation warnings (ADR 0209, 0213, 0290). Showcase entries and the preview choice control what people can look inside (ADR 0293). These controls do not bypass the API's public-repository feature switch: public repositories are built and off by default, switched on with `PUBLIC_REPOSITORIES_ENABLED` (see [docs/operations/public-launch.md](../../docs/operations/public-launch.md)).

**Discover** (`/discover`) lists public repositories for signed-in users with search, tags, system and language filters, and a storefront showing the current release. “Look inside” reads the release's permitted preview, not the repository's live authored rows (ADR 0292, 0293).

Libraries and repositories have People with Owner, Organizer and Author roles (ADR 0212, 0219). An Author edits content without administering the library. A repository has no campaigns or player roster. “Create a library” and “Create a repository” require `GET /me`'s `capabilities.create_tenant`.

## Personal access tokens and connecting a device

`/device` approves a device code with a token name and optional expiry; `/profile` lists tokens, last use and revocation. Issued secrets are shown only when issued, not recovered from the list (ADR 0268, 0269). The CLI and Android companion can connect with these tokens. Library and repository deletion is available to an Owner after typing its name (ADR 0267).

## Real API browser tests

Run `mise run //apps/account-hub:test-real-api` with the local Postgres from
`infra/docker-compose.yml` and a Playwright Chromium installation (or
`E2E_BROWSER_CHANNEL=msedge` to use an installed Edge). It recreates only
`lorenzo_account_hub_e2e`; run it and inventory-web's browser suite separately,
since they use the same ports. CI runs the smoke suite and every real-API spec
through `test:real-api:ci`. See [tests/real-api/README.md](tests/real-api/README.md).
