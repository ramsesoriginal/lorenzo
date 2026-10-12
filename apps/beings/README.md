# Lorenzo Beings

Static Astro frontend for the characters and NPCs of a library, backed directly by the [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json). See [ADR 0270](../../docs/adr/0270-beings-app.md) (what this app is and why), [ADR 0271](../../docs/adr/0271-beings-the-page-and-its-notes.md) (the list, the page, notes), [ADR 0272](../../docs/adr/0272-beings-editing-stats-and-handing-over.md) (editing, stats, handing over), [ADR 0004](../../docs/adr/0004-static-astro-frontend.md) (why static Astro) and [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md).

## What it does

After logging in through Authgear and choosing a library:

- **Beings** (`/beings/?tenant=`): the beings the viewer may list, with a search and filters for campaign, kind (characters or NPCs) and Mine. The filters are in the address. Those who run a campaign (or the library) can make a new being here; it starts as an NPC.
- **A being** (`/being/?tenant=&slug=` or `&id=`): name, kind, link name, picture, description (LorenzoScript), tags and stats; who plays it; what it carries, with a link to its board in inventory-web; its notes.
- **Notes** are written in one of four audiences: GM only, Everyone, Some characters, Player note; they can be edited, deleted and put in order.
- **Editing** (for GMs, Owners, Organizers and the being's players; the API decides): name, description, picture, link name, tags, stats.
- **Hand over to a player** (for a GM of a campaign in the library): pick the campaign and the player.

Who can see or do what is always the API's answer; the page shows the controls it expects to work and the API's message when it does not. Words follow [identity §14.3](../../docs/brand/identity.md#143-terminology).

## Run it

```bash
mise run //apps/beings:dev        # http://127.0.0.1:4323
mise run //apps/beings:lint
mise run //apps/beings:test       # Vitest
mise run //apps/beings:test-e2e   # Playwright against the real API; needs Postgres and uv
```

Copy `.env.example` to `.env` and fill in the Authgear endpoint and client id (see [docs/operations/beings-setup.md](../../docs/operations/beings-setup.md); it needs an Authgear client of its own, with `http://127.0.0.1:4323/auth/redirect/` as a redirect address). `PUBLIC_API_BASE_URL` defaults to the deployed API. Where inventory-web lives comes from the API's app-links registry ([ADR 0273](../../docs/adr/0273-app-links-registry.md)); `PUBLIC_INVENTORY_WEB_BASE_URL` is only the fallback.

The end-to-end tests start a fake Authgear (4410), the real API on a fresh database (8775, database `lorenzo_beings_e2e`, `E2E_DATABASE` overrides it; the name must end in `_e2e`) and the built site (4341), so they can run beside inventory-web's. Playwright's `E2E_REUSE_SERVERS=1` reuses servers already running.

## Shape

`src/pages/` has the pages; `src/components/<Name>/` is a `<Name>.astro` of markup and `data-*` hooks with a `renderer.ts` that finds them; `src/lib/` is the API reads and writes and the pure rules, each with a `.test.ts` where it has logic. The stat logic is `packages/stat-values`, shared with inventory-web.
