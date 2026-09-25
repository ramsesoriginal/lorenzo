# Lorenzo — Inventory Web

Static Astro frontend for browsing and managing character inventory, backed
directly by the deployed [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json).
See [ADR 0004](../../docs/adr/0004-static-astro-frontend.md) (why this is a
static Astro app) and [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md).

## What it does

After logging in via Authgear and picking a tenant, a character's inventory
renders as a kanban-style board — columns are the containers they own, cards
are item instances, dragged between columns to move them. Clicking a card
opens its detail view: every stat group, its tags, pictures, full prototype
ancestry, and descriptions (its own and those it inherits from its prototypes,
labelled), rendered as [LorenzoScript](../../packages/lorenzoscript/SPEC.md)
(Lorenzo's Markdown dialect) with entity links and pictures resolved.

From that detail view, or when multiple cards are multi-selected:

- **Give** an item (or part of a stack) to another being
- **Split** a stack into two, or **merge** two stacks of the same item back
  together
- **Undo** the last give/move/split/merge (a short-lived, single-slot undo,
  not a history browser — bulk actions and deletes aren't covered)
- **Search** within the currently loaded board by item name
- Multi-select several cards to **give or move them together** in one call
  (the bulk-assign/bulk-move endpoints, not one request per item)

Every item instance also has its own standalone, shareable page
(`/item/?tenant=…&id=…`, or `&slug=…` when it has one) — usable
for both a catalog item and an instance, with a "Copy link" button. There, a
GM can also write or edit the item's description and its display title, in a
LorenzoScript editor with a live preview that lists any links readers won't be
able to follow
([ADR 0108](../../docs/adr/0108-lorenzoscript-in-inventory-web.md));
set its tags (inherited, on, or off); add, edit, or delete any of its
information ([ADR 0112](../../docs/adr/0112-inventory-web-the-whole-item.md));
and set its slug, the name links use, prefilled with the first free one its
title suggests
([ADR 0113](../../docs/adr/0113-inventory-web-slugs-and-player-notes.md)).
The page also lists, under "Mentioned in", the entities whose descriptions link
to the item, as far as the viewer may read them
([ADR 0110](../../docs/adr/0110-lorenzoscript-content-references-and-backlinks.md)).

A GM (anyone holding a `CampaignGm` grant) additionally gets, from `/items`:

- Full catalog CRUD — create/edit/delete items, with multi-parent prototype
  selection, a description and display title, a slug (a new item's follows its
  title, so `[[Title]]` links find it), and a "used as a prototype by"
  reverse lookup
- Instantiate a catalog item into a new instance, with an optional owner and
  slug
- Browse/reassign/unassign/delete existing instances
- Browse any being's inventory (not just their own characters) — by
  search, or a raw entity id for a "bare" being with no Character row — and
  browse everyone's unowned/unclaimed loot, both via the same board UI a
  player uses for their own characters

Deliberately not built yet: naming who may read a private piece of
information (ADR 0109's knowers), editing stat values other than tags, and
uploading pictures — see the tracking issue for what's actually in flight.

## Commands

Run from this directory, or via `mise run //apps/inventory-web:<task>` from the
repo root:

| Command | Action |
| --- | --- |
| `mise run dev` | Start the dev server at `localhost:4321` |
| `mise run lint` | Biome + `astro check` + Prettier (`.astro`) |
| `mise run format` | Autoformat |
| `mise run test` | Run the unit tests (Vitest, `src/lib/`) |
| `mise run test-e2e` | Run the end-to-end tests (Playwright) |
| `mise run build` | Build the static site to `dist/` |

## End-to-end tests

`tests/e2e/` drives the built site in Chromium against the real `apps/api`
and a fake Authgear ([ADR 0114](../../docs/adr/0114-inventory-web-end-to-end-tests.md)).
Playwright starts all three:

- the fake Authgear (`tests/e2e/support/fake-authgear.ts`), which signs in
  whoever a test names, with no login form;
- the API on its own database, `lorenzo_e2e`, which is dropped, recreated, and
  migrated on every run;
- the site, built against the two.

Each test builds its own tenant through the API (`tests/e2e/support/world.ts`),
so tests run in parallel and never share data.

Locally, start Postgres first
(`docker compose -f infra/docker-compose.yml up -d`). Then run:

```bash
mise run test-e2e
```

Environment variables, all optional:

- `E2E_POSTGRES_URL` and `E2E_APP_POSTGRES_URL`: another Postgres, as its
  privileged and restricted roles.
- `E2E_BROWSER_CHANNEL`: an installed browser, such as `msedge` or `chrome`,
  instead of Playwright's own download (`pnpm exec playwright install
  chromium`).

Servers that are already running are reused, which speeds up a second run.
Stop them to pick up a changed build. CI runs these tests in its `e2e` job.

## Deploy

Cloudflare Pages, via its own Git integration (no GitHub Actions step) — see
[docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md#cloudflare-pages-appsinventory-web)
for the one-time setup.
