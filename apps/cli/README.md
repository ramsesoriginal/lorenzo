# apps/cli

The `lorenzo` command-line tool. Its first feature is the MPMB standard-item importer of [RFC 0025](../../docs/rfcs/0025-lorenzo-cli-mpmb-item-importer.md); the stack is recorded in [ADR 0137](../../docs/adr/0137-lorenzo-cli-app-python-client-and-auth.md).

Python 3.14, run and tested on Linux (WSL included). Native Windows is not a supported target.

## Run it

```bash
mise run //apps/cli:dev -- --help
```

or, from this directory, `uv run lorenzo --help`.

The tool needs an access token for `apps/api`. Until `lorenzo login` works against a registered Authgear client (see below), supply one directly:

```bash
export LORENZO_API_URL=http://localhost:8000
export LORENZO_TOKEN=...   # the token that `mise run //apps/api:dev-token` prints
uv run lorenzo tenant show <tenant-id-or-slug>
```

Or pipe a token in with `--token-stdin`. A token from the stored login is used last.

## Commands

| Command | What it does |
| --- | --- |
| `lorenzo tenant show <tenant>` | Reads one tenant (its `kind`, whether it is published) - the first call through the generated client |
| `lorenzo login` / `lorenzo login --no-browser` / `lorenzo logout` | Stores or forgets a login (needs the Authgear client, see below) |
| `lorenzo inspect [--base FILE...] FILE...` | Shows what the JavaScript host reads from MPMB files (files, per-list counts and which file each entry came from, stubbed sheet names), without touching a tenant. Needs no login |
| `lorenzo seed --tenant <tenant>` | Creates the item taxonomy, stat groups and definitions, and the weight recipe an import needs, in a repository tenant. Safe to run again; `--dry-run` first |
| `lorenzo plan --tenant <tenant> FILES...` | Works out what importing these MPMB files would do and changes nothing. Deterministic JSON with `--json`; exit 0 nothing to do, 2 changes pending, 1 something unresolved |
| `lorenzo apply --tenant <tenant> FILES... --yes` | Imports them: what is resolved, and none of what needs a decision. Safe to run again, and unattended |
| `lorenzo pack give <pack> --tenant <tenant>` | Creates an imported pack's contents in a tenant: its container, then what is inside, with quantities. `--owner`, `--into`, `--dry-run` |

## Importing MPMB items

The order is: seed the tenant once, then plan, then apply ([ADR 0144](../../docs/adr/0144-lorenzo-import-mapping-identity-plan-apply.md)).

```bash
uv run lorenzo seed --tenant my-repository --yes

# The sheet's own SRD items (its data files are GPL-3.0 and are not shipped; clone the repository):
S=/tmp/mpmb/_variables
uv run lorenzo plan  --tenant my-repository --base $S/ListsSources.js --base $S/Lists.js --base $S/ListsGear.js
uv run lorenzo apply --tenant my-repository --base $S/ListsSources.js --base $S/Lists.js --base $S/ListsGear.js --yes

# Homebrew on top of it (a later file wins), with your own map:
uv run lorenzo apply --tenant my-repository --base $S/ListsSources.js --base $S/Lists.js \
  --base $S/ListsGear.js --map my.map.toml my-homebrew.js --yes
```

An item's identity is its slug, `<namespace>-<list>-<key>` (`basic-weapons-longsword`), so a second run finds what the first made. The namespace comes from the map, per input file (`[namespaces]`, default `basic`); it is a commitment, since a rename doesn't rewrite `[[links]]`.

**What is decided by data, not code.** `src/lorenzo_cli/importer/builtin_map.toml` says what each MPMB value means (a `Martial` weapon is `dnd5e-martial`; `Natural`, `Cantrip` and `Spell` aren't items; an `ammunition` gear entry is ammunition; a longsword is a `blade` with the `Versatile` property, found from its name and description), and your map, in the same format, overlays it row by row:

```toml
schema = 1

[namespaces]
"my-homebrew.js" = "hb-alice"

[currencies]
mark = 250                       # 3 marks is 750 copper

[classify.weapons.type]
exotic = { disposition = "create-under", axis = "proficiency", slug = "hb-exotic", name = "Exotic weapon" }

[attributes.weapons]
flavour = { transform = "text", stat = "flavour_text", group = "lore" }   # creates the stat
```

**What it won't guess.** A value with no row (a weapon `type` the map has never heard of), a price it can't read, or a weapon that is neither melee nor ranged holds that item back, and everything held is written to `review-queue.json` with a row to paste, and to `proposed.map.toml`. Your map file is never edited. `--teach`, at a terminal, asks about each unknown value once, uses the answer straight away, and offers to append the rows to your map afterwards. Attributes no rule mentions are listed and don't block an item; under `--strict` they count as unresolved.

**Packs.** An Explorer's pack is imported as an item whose public description lists its contents (`- 5 x [Rations (1 day)](basic-gear-rations-1-day)`, nested under its container, [ADR 0145](../../docs/adr/0145-pack-contents-in-the-description.md)). It copies with a repository, and `lorenzo pack give basic-packs-explorer --tenant my-campaign --owner alice` creates the backpack and everything in it. An entry the sheet has no gear entry for (an alms box) becomes a simple plain gear item so the pack can be given complete; a name the map does not know is made one too and reported, with a `[pack_items]` row to link it to a real item instead (`"item"` says it is a plain item, `"text"` that it is no item at all).

Other flags: `--reconcile` re-parents items the map now files elsewhere (default is create-only, and a changed map only reports "N items would change parents"); `--accept-moves` creates the items whose namespace changed; `--public-catalog` lets players list the imported items; `--allow-play-tenant`, as for `seed`.

## Seeding a tenant

An import needs somewhere to put things: item prototypes to descend from (weapon, container, martial...) and the stat definitions the values are written to. `lorenzo seed` creates them once ([ADR 0143](../../docs/adr/0143-lorenzo-seed-taxonomy-and-stats.md)):

```bash
uv run lorenzo seed --tenant my-repository --dry-run   # what would be created (exit 2 if anything)
uv run lorenzo seed --tenant my-repository --yes       # create it
```

The taxonomy is a graph with multiple inheritance, so a weapon is several things at once: `longsword` descends from `blade`, `dnd5e-martial` and `dnd5e-versatile`. Weapon families (blade, axe, hammer, bow, crossbow, sling, firearm), weapon properties (finesse, heavy, light, reach, thrown, two-handed, versatile…), materials, consumables and kinds of gear (clothing, climbing, nautical…) are nodes of their own; a property carries its rules as a public description, which shows on every weapon that has it, and the property lists the weapons that do ([ADR 0146](../../docs/adr/0146-a-richer-item-taxonomy-and-keeping-what-the-sheet-says.md)). What the sheet says beyond that is kept: other names as an "Also known as" entry, a weapon's special rules as a note, and the ability, strength requirement, bundle size and flags as stats.

It writes to an existing `repository` tenant. A `play` tenant is refused, because a tenant's kind can't be changed and nothing in it could ever be published; `--allow-play-tenant` writes there anyway. The seed is in `src/lorenzo_cli/seed/builtin.toml`, tagged by layer (`core`, and `dnd5e` for D&D 5e's categories and dice, chosen with `--layer`). Stat names and types can't be changed once a tenant has them, so read that file before the first run against a tenant that matters.

## Reading MPMB files

MPMB's additional-content files are executable JavaScript, so they are evaluated, not parsed ([ADR 0138](../../docs/adr/0138-lorenzo-cli-js-host.md)). `lorenzo_cli.evalworker` runs an embedded V8 (`mini-racer`) in a subprocess that is given no credentials and is killed on a timeout, and returns plain JSON in which a `RegExp` is `{"$re": [source, flags]}` and a function is `{"$fn": text}` (never called).

Homebrew is written against lists that already hold the sheet's SRD data, and some files patch it, so pass the sheet's own files first as `--base`:

```bash
git clone https://github.com/morepurplemorebetter/MPMBs-Character-Record-Sheet /tmp/mpmb
uv run lorenzo inspect \
  --base /tmp/mpmb/_variables/ListsSources.js --base /tmp/mpmb/_variables/Lists.js \
  --base /tmp/mpmb/_variables/ListsGear.js my-homebrew.js
```

The sheet's data is GPL-3.0 and is not shipped with Lorenzo. `tests/corpus/` holds the golden fixtures every engine must reproduce; `LORENZO_UPSTREAM_CORPUS=/tmp/mpmb uv run pytest tests/test_evalworker_upstream.py` runs the worker against the real thing.

## The API client

`src/lorenzo_cli/client/models.py` is generated from `apps/api`'s OpenAPI document and committed. After changing `apps/api`'s routes or schemas:

```bash
mise run //apps/cli:generate-schema
```

CI's `client-drift` job runs `check-schema`, which fails on any difference. `src/lorenzo_cli/client/ops.py` lists the operations the CLI calls; a test checks each against the dumped schema.

## Login needs an Authgear client

`login` uses the authorization code flow with PKCE against a public Authgear client on a fixed loopback port. That client has to be registered on the Authgear project first (an operations step, see [docs/operations](../../docs/operations/local-authgear-setup.md)). Until then `login` says so and exits; tokens through `LORENZO_TOKEN` or `--token-stdin` work regardless.

Environment: `LORENZO_API_URL` (the API base URL), `LORENZO_TOKEN`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`.

## Tests

`mise run test` runs everything. `tests/e2e/` starts the real `apps/api` on a fresh database behind a fake Authgear and runs the CLI against it; it needs Postgres (`docker compose -f infra/docker-compose.yml up -d`, or CI's service) and skips without it. `LORENZO_REQUIRE_E2E=1` makes a missing stack a failure instead, as CI does.
