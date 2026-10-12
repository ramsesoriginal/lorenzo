# Lorenzo — Inventory Web

Static Astro frontend for browsing and managing character inventory, backed
directly by the deployed [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json).
See [ADR 0004](../../docs/adr/0004-static-astro-frontend.md) (why this is a
static Astro app) and [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md).

## What it does

After logging in via Authgear and picking a tenant, a character's inventory
renders as a kanban-style board of everything they control ([ADR
0131](../../docs/adr/0131-the-board-on-controlled-by.md)): Equipped and Not
carried first and always, then a column for every container they control,
empty ones included, then read-only columns for whatever else holds
something of theirs. Cards are item instances, dragged between columns to move
them, and a card that isn't the character's own names its owner. The groups
your characters belong to have boards of their own, and can be given things
([ADR 0124](../../docs/adr/0124-groups-own-things-and-moving-is-not-giving.md)). Clicking a card
opens its detail view: every stat group, its tags, pictures, full prototype
ancestry, and descriptions (its own and those it inherits from its prototypes,
labelled), rendered as [LorenzoScript](../../packages/lorenzoscript/SPEC.md)
(Lorenzo's Markdown dialect) with entity links and pictures resolved.

Under the board's search, **Add an item** makes one for the character whose board it is, out of the
catalog the viewer may list (the public one, for a player): pick it, optionally name it, and it
lands in Not carried, with an Undo beside it. A player gets it for their own character while their
GM has self-service on for them, and a note saying so when it's off; a GM gets it on any being's
board; a group's board and the unowned board have none
([ADR 0187](../../docs/adr/0187-inventory-web-adding-an-item-to-a-board.md), [ADR
0186](../../docs/adr/0186-player-self-service-enforcement.md)).

**Not in the list?** The same card takes an item the catalog doesn't have: a name, a description, a
weight in pounds and a value. It is added as an *unsorted* item, with the description kept as notes
for the character, and the card wears an **Unsorted** badge until the GM matches it to a catalog
item ([ADR 0238](../../docs/adr/0238-inventory-web-not-in-the-list-and-the-unsorted-badge.md)).

**Unsorted** (a GM's page) lists every unsorted item grouped by the name the player wrote. Open a
group to see who holds each and their notes, then give the ticked ones to a catalog item (suggested
by how alike the names are, or searched), make a new catalog item from the group, or keep it for
now. The suggestions also know the other ways a name is written ("Seil" for "Rope, hempen"), from the
same table `lorenzo inventory import` uses ([ADR 0242](../../docs/adr/0242-inventory-names-the-spelling-table-shared.md)). The names and notes stay on what is sorted, and its holders are told by the API
([ADR 0241](../../docs/adr/0241-inventory-web-the-unsorted-view.md)).

From that detail view, or when multiple cards are multi-selected:

- **Give** an item (or part of a stack) to another being; a player finds the
  tenant's characters, a GM any being. **Hand it over** to take it out of its
  container and into their hands too; otherwise it stays where it is, theirs
  now ([ADR 0115](../../docs/adr/0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md))
- **Move** it between containers, or into the character's own hands (Equipped):
  a stack keeps its count, and joins an identical one already there ([ADR
  0133](../../docs/adr/0133-merging-what-is-identical.md))
- **Set it down**, out of every container, into Not carried: a stack becomes
  single items, after asking ([ADR
  0132](../../docs/adr/0132-setting-things-down.md))
- **Note** it: add, edit, or delete notes, in LorenzoScript. A note is private
  to the character that owns the item (and the campaign's GMs) unless
  "Everyone can read this"; the item page shows them too
  ([ADR 0113](../../docs/adr/0113-inventory-web-slugs-and-player-notes.md))
- **Unpack** a pack (an item whose description lists its contents) into what it lists,
  in the owner's hands, after a dry run says what that will be; the pack goes. A player may when
  self-service is on and everything in it is public
  ([ADR 0189](../../docs/adr/0189-inventory-web-unpacking-a-pack.md))
- **Split** a stack into two, or **merge** two stacks of the same item back
  together
- **Undo** the last give/move/split/merge (a short-lived, single-slot undo,
  not a history browser — bulk actions and deletes aren't covered)
- **Search** within the currently loaded board by item name
- Multi-select several cards to **give or move them together** in one call
  (the bulk-assign/bulk-move endpoints, not one request per item)

Every item instance also has its own standalone, shareable page
(`/item/?tenant=…&id=…`) — usable
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

Every address takes slugs as well as ids, the library's included, as in
`/board/?tenant=sunken-vale&character=ashfang`, and keeps them as given
([ADR 0135](../../docs/adr/0135-slugs-in-inventory-web-addresses.md)).

Anyone can open a catalog item's page, and `/items` ("Catalog" on the board)
lists what they may browse: for a player, the items the GM put in the public
catalog ([ADR 0116](../../docs/adr/0116-players-read-catalog-items-and-a-public-catalog.md)).

A GM (anyone holding a `CampaignGm` grant) additionally gets, from `/items`:

- Full catalog CRUD — create/edit/delete items, with multi-parent prototype
  selection, a description and display title, a slug (a new item's follows its
  title, so `[[Title]]` links find it), whether it's in the public catalog,
  and a "used as a prototype by" reverse lookup
- Instantiate a catalog item into a new instance, with an optional owner and
  slug
- Edit an item's or instance's stat values on its page (a field per type, its
  own value or inherited again; [ADR
  0263](../../docs/adr/0263-inventory-web-editing-stat-values.md))
- A notification bell in the header: unread count, the latest ten with a link to
  the board they are about, mark one or all as read, and "See all" in the account
  hub, whose address comes from the API's app-links registry ([ADR 0265](../../docs/adr/0265-inventory-web-notification-bell.md),
  [ADR 0273](../../docs/adr/0273-app-links-registry.md)); `PUBLIC_ACCOUNT_HUB_URL` is only the
  fallback when the registry cannot be reached
- Browse/reassign/unassign/delete existing instances
- Browse any being's inventory (not just their own characters) — by
  search, or an entity id or slug for a "bare" being with no Character row — and
  browse everyone's unowned/unclaimed loot, both via the same board UI a
  player uses for their own characters

Deliberately not built yet: naming who may read a private piece of
information (ADR 0109's knowers) beyond a note's own character, showing who
wrote a note, and uploading pictures —
see the tracking issue for what's actually in flight.

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

A test's browser starts out signed in: `as(person)` puts a refresh token from the fake Authgear
where the Authgear SDK keeps one, so the first page it loads is the one the test goes to. One
test (`logInAs`, in `login.spec.ts`) goes through the login button and the fake's PKCE round
trip instead, so that flow stays covered.

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

Servers that are already running are an error rather than reused, since a stale one
serves an old build. `E2E_REUSE_SERVERS=1` reuses them anyway, which speeds up a second
run; stop them to pick up a changed build. CI runs these tests in its `e2e` job.

## Deploy

Cloudflare Pages, via its own Git integration (no GitHub Actions step) — see
[docs/operations/deployment-setup.md](../../docs/operations/deployment-setup.md#cloudflare-pages-appsinventory-web)
for the one-time setup.
