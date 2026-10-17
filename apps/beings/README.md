# Lorenzo Beings

Static Astro frontend for the characters and NPCs of a library, backed directly by the [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json). See [ADR 0270](../../docs/adr/0270-beings-app.md) (what this app is and why), [ADR 0271](../../docs/adr/0271-beings-the-page-and-its-notes.md) (the list, the page, notes), [ADR 0272](../../docs/adr/0272-beings-editing-stats-and-handing-over.md) (editing, stats, handing over), [RFC 0043](../../docs/rfcs/0043-the-being-sheet.md) with [ADR 0282](../../docs/adr/0282-beings-sheet-shell-modes-and-sections.md) to [0284](../../docs/adr/0284-beings-sheet-datasheet.md) (the sheet: modes, playing, the datasheet; the design and prototype are in [docs/design/beings](../../docs/design/beings/README.md)), [ADR 0004](../../docs/adr/0004-static-astro-frontend.md) (why static Astro) and [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md).

## What it does

After logging in through Authgear and choosing a library:

- **Beings** (`/beings/?tenant=`): the beings the viewer may list, with a search and filters for campaign, kind (characters or NPCs) and Mine. The filters are in the address. Rows stay compact until a picture loads. A visible picture is shown as an 80 px portrait; desktop pointers (and keyboard focus) show a larger preview up to 512 px, constrained to the viewport. Touch devices keep normal tap-to-open links. Portraits load as rows approach the viewport, through the existing visibility-checked preview API. Picture bytes are cached privately by the browser and revalidated after access checks; unchanged pictures return 304 without downloading them again. Those who run a campaign (or the library) can make an NPC. Players can also create a character of their own in a campaign where they hold a seat.
- **A being** (`/being/?tenant=&slug=` or `&id=`): a sheet with an identity header (picture, name, kind, link name, tags), About, Notes, Stats and Inventory, and who plays it. A switch picks how you look at it: **Read** (prose first), **Play** (numbers first: a number the library calls adjustable has a stepper and an adjuster that takes away, adds or sets an amount, tags toggle, and each change says what it did and can be undone with Undo or Ctrl/Cmd+Z) and **Edit** (every value is a field; name, link name, picture, tags and the description become forms). Edit is offered only to those the API would let write. A sticky bar keeps the name, the pinned numbers and the same switch in view.
- **Delete being** (in Edit): a confirmed, permanent deletion with the API's existing permission guards. Stats, information and the link name go with it; owned-and-carried items are deleted, borrowed items are set down, and items owned elsewhere become unowned and uncarried ([ADR 0302](../../docs/adr/0302-deleting-a-being.md)).
- **Stats** show every stat in the library's being stat group, plus other stats for which the being has a value set on the being, inherited or calculated, in the vocabulary's order ([ADR 0297](../../docs/adr/0297-beings-stat-selection.md)). This applies in Read, Play and Edit, on Sheet and Datasheet; without a selected group, only valued stats appear. Unset stats in the selected group show a dash, or a field in Edit. Numbers are drawn as tiles with their unit and sign, "of 9" and "+3" from the hints, text as rows, and where a value comes from ("From Dwarf"; a calculated number opens how it was made up).
- **Datasheet**: a second layout of the same being, for the table: a line of cells per stat group, the equipped weapons as a table (the library says which stat group holds a weapon's stats), abilities and notes, with the same Play controls.
- **Notes** are written in one of four audiences: GM only, Everyone, Some characters, Player note; they show who wrote them, and can be edited, deleted and put in order in Edit.
- **Hand over to a player** (for a GM of a campaign in the library, in Edit): pick the campaign and the player.

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

Editable descriptions and notes include **Who can read this**, with explicit character and group
recipients and the existing Player grants. Audience changes are atomic and versioned (ADR 0304);
a stale form asks the editor to review the current audience before saving again.

Descriptions and notes may hold several LorenzoScript texts and pictures, kept in one ordered
bundle with one audience (ADR 0306). **Add picture** and **Add text** extend the existing editor;
move/remove controls keep each part in order. A failed save keeps the draft and stable attachment
IDs for retry. Read mode includes every part; protected pictures use authenticated requests.

## Facts about an entry

An entry lists the Facts explicitly about it when the reader can see their existence/name.
The Fact page renders its visible information bundles and About subjects. LorenzoScript links
resolve to that page. The Fact's outer audience and each information audience are independent;
hidden Facts produce the same unavailable view as missing entries (ADR 0305, RFC 0044).
