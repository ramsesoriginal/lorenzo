# Lorenzo — Inventory Web

Static Astro frontend for browsing and managing character inventory, backed
directly by the deployed [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json).
See [ADR 0004](../../docs/adr/0004-static-astro-frontend.md) (why this is a
static Astro app) and [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md).

## What it does

After logging in via Authgear and picking a tenant, a character's inventory
renders as a kanban-style board — columns are the containers they own, cards
are item instances, dragged between columns to move them. Clicking a card
opens its detail view: stats, tags/flags, full prototype ancestry, and
descriptions, rendered as [LorenzoScript](../../packages/lorenzoscript/SPEC.md)
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
(`/item/?tenant=…&id=…`, or `&slug=…` when the instance has one) — usable
for both a catalog item and an instance, with a "Copy link" button. There, a
GM can also write or edit the item's description, in a LorenzoScript editor
with a live preview that lists any links readers won't be able to follow
([ADR 0108](../../docs/adr/0108-lorenzoscript-in-inventory-web.md)).

A GM (anyone holding a `CampaignGm` grant) additionally gets, from `/items`:

- Full catalog CRUD — create/edit/delete items, with multi-parent prototype
  selection and a "used as a prototype by" reverse lookup
- Instantiate a catalog item into a new instance, with an optional owner and
  slug
- Browse/reassign/unassign/delete existing instances
- Browse any being's inventory (not just their own characters) — by
  search, or a raw entity id for a "bare" being with no Character row — and
  browse everyone's unowned/unclaimed loot, both via the same board UI a
  player uses for their own characters

Deliberately not built yet: notes beyond the description (GM/player-written,
visibility-gated text), and naming who may read a private one — see the
tracking issue for what's actually in flight.

## Commands

Run from this directory, or via `mise run //apps/inventory-web:<task>` from the
repo root:

| Command | Action |
| --- | --- |
| `mise run dev` | Start the dev server at `localhost:4321` |
| `mise run lint` | Biome + `astro check` + Prettier (`.astro`) |
| `mise run format` | Autoformat |
| `mise run test` | Run the test suite |
| `mise run build` | Build the static site to `dist/` |

## Deploy

Cloudflare Pages, via its own Git integration (no GitHub Actions step) — see
[docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md#cloudflare-pages-appsinventory-web)
for the one-time setup.
