# apps/cli

The `lorenzo` command-line tool. Its first feature is the MPMB standard-item importer of [RFC 0025](../../docs/rfcs/0025-lorenzo-cli-mpmb-item-importer.md); the stack is recorded in [ADR 0137](../../docs/adr/0137-lorenzo-cli-app-python-client-and-auth.md).

Python 3.14, run and tested on Linux (WSL included). Native Windows is not a supported target.

## Install it

On Linux or macOS (WSL included), with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"
lorenzo --help
```

That installs the `lorenzo` command from this repository's `main` branch, into its own environment. It isn't on PyPI: it only works against a Lorenzo `apps/api`, and its client is generated from that API's schema, so the two move together. Put `@<tag>` (or `@<commit>`) before the `#` to pin a version, and update with `uv tool upgrade lorenzo-cli`. To run it from a checkout of the repository instead, see below.

`lorenzo --version` says which one is installed. To complete commands and options with Tab, run `lorenzo --install-completion` once (it adds a line to your shell's startup file; `lorenzo --show-completion` prints the script instead, if you'd rather place it yourself). Tenant slugs aren't completed.

## Before you start

Four things have to be true before the first command does anything useful. The first three are about the Lorenzo you are talking to, not about this tool.

1. **You know its API address.** There is no default, on purpose: the CLI sends your token only to an address you gave it. It is whatever your Lorenzo's operator tells you (for a local `apps/api`, `http://localhost:8000`).
2. **You have an account on it, and the CLI has a way to sign in.** Signing in uses an Authgear client registered for the CLI: a *public* client, with no secret, whose redirect URIs are `http://127.0.0.1:8766/callback`, `:8767` and `:8768`. Registering it is a one-time step for whoever runs the Authgear project ([docs/operations](../../docs/operations/README.md)); you need its **issuer** and **client id**. Until one exists, a token from `LORENZO_TOKEN` or `--token-stdin` does everything `login` would.
3. **To create a tenant, you need the `tenant-creator` role**, which the Authgear project's maintainer grants in its Portal. Nothing else in this tool needs it, and the API says so (`403`) if you lack it. (`whoami` can't tell you beforehand: the API doesn't report roles yet.)
4. **To import MPMB items, you have the sheet's data.** It is GPL-3.0 and not shipped; clone it (see [Reading MPMB files](#reading-mpmb-files)).

Python 3.14 is installed for you by `uv`. Linux and macOS (WSL included) are supported; native Windows isn't.

### The first run

```bash
lorenzo login --api-url https://api.example --issuer https://example.authgear.cloud --client-id abc123
lorenzo whoami          # the API says who it thinks you are: the check that it all works
lorenzo tenant list     # the tenants you belong to
```

`login` remembers the three values it used, so after that `lorenzo login` alone, from any shell, is enough, and every other command finds the API address by itself. `--no-browser` prints the address to open, for WSL and SSH.

### Where the settings come from

Each of the three, for each command, in this order: **a flag** (`--api-url`, and `--issuer` and `--client-id` on `login`), then **the environment** (`LORENZO_API_URL`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`), then **the file** `login` wrote: `$XDG_CONFIG_HOME/lorenzo/config.toml` (`~/.config/lorenzo/config.toml`), three plain lines with nothing secret in them. Only `login` writes it. `lorenzo logout` forgets your tokens and keeps the file; delete the file to forget the addresses too ([ADR 0157](../../docs/adr/0157-lorenzo-remembers-the-api-url-issuer-and-client-id.md)).

The token is looked for in this order: `--token-stdin` (the first line of stdin), `LORENZO_TOKEN`, then the stored login (`credentials.json` beside the settings, readable only by you, renewed on its own). `--tenant` can come from `LORENZO_TENANT`. Unattended use, a script holding its own credentials, isn't supported: the CLI is run by a person with their own token.

## Run it

```bash
mise run //apps/cli:dev -- --help
```

or, from this directory, `uv run lorenzo --help`.

The tool needs an access token for `apps/api`. Until `lorenzo login` works against a registered Authgear client (see [Before you start](#before-you-start)), supply one directly:

```bash
export LORENZO_API_URL=http://localhost:8000
export LORENZO_TOKEN=...   # the token that `mise run //apps/api:dev-token` prints
uv run lorenzo tenant show <tenant-id-or-slug>
```

Or pipe a token in with `--token-stdin`. A token from the stored login is used last.

## Commands

| Command | What it does |
| --- | --- |
| `lorenzo --version` | Says which version is installed. Needs no login |
| `lorenzo whoami [--json]` | Asks the API who the token you'd use belongs to, and says where the token came from: the check that a login works |
| `lorenzo tenant list [--kind repository\|play] [--json]` | The tenants you belong to, with each one's kind and your role |
| `lorenzo tenant create <name> [--slug S] [--kind KIND]` | Creates a tenant and makes you its owner (a `repository`, which is what an import needs, unless `--kind play`; the kind can't be changed later). Needs the tenant-creator role. Doesn't seed: run `lorenzo seed` next |
| `lorenzo tenant show <tenant>` | Reads one tenant (its `kind`, whether it is published) - the first call through the generated client |
| `lorenzo login [--api-url U] [--issuer I] [--client-id C]` / `--no-browser` / `lorenzo logout` | Stores or forgets a login, and remembers the three values `login` used (needs the Authgear client, see [Before you start](#before-you-start)) |
| `lorenzo inspect [--base FILE...] FILE...` | Shows what the JavaScript host reads from MPMB files (files, per-list counts and which file each entry came from, stubbed sheet names), without touching a tenant. Needs no login |
| `lorenzo seed --tenant <tenant>` | Creates the item taxonomy, stat groups and definitions, and the weight recipe an import needs, in a repository tenant. Safe to run again; `--dry-run` first |
| `lorenzo plan --tenant <tenant> FILES...` | Works out what importing these MPMB files would do and changes nothing. Deterministic JSON with `--json`; exit 0 nothing to do, 2 changes pending, 1 something unresolved |
| `lorenzo apply --tenant <tenant> FILES... --yes [--json]` | Imports them: what is resolved, and none of what needs a decision. Safe to run again, and unattended. `--json` prints one document: the plan, what was written, what failed |
| `lorenzo pack give <pack> --tenant <tenant> --owner <being-or-group>` | Hands an imported pack out: the API makes its containers and what is inside them, with quantities, in one go or not at all. A being takes the top of it into its hands; a group owns it with nothing in a container. `--dry-run` says what would be made; `--override` is a GM's, past what the owner can carry; `--json` prints what the API made |
| `lorenzo repo publish\|unpublish\|grant\|revoke\|subscribers --tenant <repository>` | The repository's own side: publish it (again, to announce an update), withdraw it, give a tenant access, take it back, list who has it. Owners only |
| `lorenzo repo list\|copy-plan\|copy\|updates --tenant <tenant>` | A tenant's side: which repositories it holds, what copying one would do, copying it, and taking what it changed since. See [Publishing a repository](#publishing-a-repository) |
| `lorenzo repo offer <tenant> --tenant <repository>` | Grant it, then copy it into that tenant; a copy already there is a success, so it is safe to run again |
| `lorenzo api <METHOD> <path> [-d JSON] [-q K=V] [--paginate]` | One authenticated request to the API, for scripts. See [Scripting](#scripting) |

## Importing MPMB items

The order is: create a repository (`lorenzo tenant create "My Homebrew" --slug my-homebrew`), seed it once, then plan, then apply ([ADR 0144](../../docs/adr/0144-lorenzo-import-mapping-identity-plan-apply.md)). For something you mean to publish, seed core and D&D 5e into [two repositories](#core-and-dd-5e-are-two-repositories) instead.

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

**Packs.** An Explorer's pack is imported as an item whose public description lists its contents (`- 5 x [Rations (1 day)](basic-gear-rations-1-day)`, nested under its container, [ADR 0145](../../docs/adr/0145-pack-contents-in-the-description.md)). It copies with a repository, and `lorenzo pack give basic-packs-explorer --tenant my-campaign --owner alice` has the API make the backpack and everything in it for Alice ([ADR 0149](../../docs/adr/0149-giving-a-pack-from-the-api.md), [ADR 0150](../../docs/adr/0150-lorenzo-pack-give-on-the-api.md)). Every line of the list links to an item, since the API refuses a pack that has one that doesn't, naming it: an entry the sheet has no gear entry for (an alms box) becomes a simple plain gear item so the pack can be given complete; a name the map does not know is made one too and reported, with a `[pack_items]` row to link it to a real item instead (`"item"` says it is a plain item; `"text"` is no longer a choice). A pack written before that with a line that doesn't link is fixed by editing its description.

Other flags: `--reconcile` re-parents items the map now files elsewhere (default is create-only, and a changed map only reports "N items would change parents"); `--accept-moves` creates the items whose namespace changed; `--public-catalog` lets players list the imported items; `--allow-play-tenant`, as for `seed`.

## Publishing a repository

A repository is a tenant of kind `repository`; other tenants draw on it by being **granted** it and **copying** it, and take its later changes as **updates** ([RFC 0024](../../docs/rfcs/0024-repositories.md)). After `tenant create`, `seed` and `apply`:

```bash
lorenzo repo publish --tenant my-homebrew                       # until now, nobody it is granted to can see it
lorenzo repo offer table-one --tenant my-homebrew               # grant it to table-one, and copy it in
```

`offer` is for whoever owns the repository and belongs to the tenant (a tenant that isn't yours can only be granted by its id: `repo grant <id>`). Each step is also a command of its own:

```bash
lorenzo repo grant table-one --tenant my-homebrew               # table-one's members are told
lorenzo repo copy-plan my-homebrew --tenant table-one           # what copying would do; exit 0 fine, 2 needs choices, 1 refused
lorenzo repo copy my-homebrew --tenant table-one --dry-run      # every check, then roll back
lorenzo repo copy my-homebrew --tenant table-one --on-collision merge
```

A copy makes the repository's content the tenant's own, so a stat group or slug that the tenant already has needs a choice (rename, merge or skip) before anything is written. `copy-plan --json` lists each collision with its `source_id` and the choices it allows; give them back in a file (`--choices choices.json`, a list of `{"kind", "source_id", "action", "name"}`) or answer all of them with `--on-collision merge|skip` (a slug can't be merged). With no answer, nothing is copied and the exit code is 2.

When the repository publishes again, `lorenzo repo list --tenant table-one` says "updated since":

```bash
lorenzo repo updates my-homebrew --tenant table-one             # what changed, row by row; exit 2 if anything
lorenzo repo updates my-homebrew --tenant table-one --apply     # take what needs no decision
lorenzo repo updates my-homebrew --tenant table-one --actions mine.json   # decide row by row
```

`--apply` takes the changes that don't touch anything the tenant also changed, and additions that collide with nothing. A conflict is never taken without being named: put the field in `take_upstream` (or `keep_local`) in an `--actions` file, the API's own action list ([ADR 0121](../../docs/adr/0121-repository-updates-and-re-sync.md)). `--dry-run` applies it all and rolls it back.

### Core and D&D 5e are two repositories

What is meant to be published is split in two ([ADR 0162](../../docs/adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)): **core**, the system-neutral taxonomy and stat definitions, and **D&D 5e**, a repository that has copied core and added its own layer on top. That makes D&D a *bridge* ([ADR 0120](../../docs/adr/0120-bridge-repositories-and-dependency-manifests.md)), and the imported items live in it, since a longbow is a ranged weapon (core) and a martial one (D&D). Another system can then build on core without carrying D&D.

```bash
lorenzo tenant create "Core" --slug core
lorenzo seed --tenant core --layer core --yes
lorenzo repo publish --tenant core

lorenzo tenant create "D&D 5e" --slug dnd5e
lorenzo repo grant dnd5e --tenant core            # the bridge draws on core like any tenant
lorenzo repo copy core --tenant dnd5e --yes
lorenzo seed --tenant dnd5e --layer dnd5e --yes   # needs core's copy, which it now has
lorenzo apply --tenant dnd5e --base ... --yes     # the items, parented in both layers
lorenzo repo publish --tenant dnd5e

lorenzo repo offer table-one --tenant dnd5e       # grants core too, then dnd5e, and copies both
```

A table needs a grant on **each** repository, since grants aren't transitive; `offer` makes both, for whoever owns them all, and a single copy brings core in first. Someone who owns the bridge but not core is told which command to ask core's owners for. **A correction to core** takes four steps: core publishes again; the bridge takes it (`lorenzo repo updates core --tenant dnd5e --apply`); the bridge publishes again; each table takes it on core's own route (`lorenzo repo updates core --tenant table-one --apply`). A bridge's own edits to its copy of core don't travel (to change how a core entity behaves under D&D, author one that inherits from it).

`lorenzo seed` without `--layer` still seeds both layers into one repository, which is fine for a table's own use and for trying things; it says so, and says to separate them if they are to be published.

## Scripting

- **Exit codes.** On `plan`, `seed --dry-run`, `repo copy-plan`, `repo updates` and `repo offer --dry-run`: 0 is fine, 2 is something to do or to decide, and 1 is refused or unresolved. Each command's `--help` says what 0 and 2 mean for it.
- **`--json`** (on `plan`, `apply`, `seed`, `tenant`, `whoami`, `pack give` and every `repo` command) prints exactly one JSON document on stdout; whatever is for a person goes to stderr. It never asks a question, so a command that writes needs `--yes` with it.
- **`lorenzo api`** is for everything else, with the login you already have, so no token is pasted into a shell:

```bash
lorenzo api GET /tenants --paginate | jq '.[].slug'
lorenzo api POST /tenants -d '{"name": "Table One", "kind": "play"}'
lorenzo api PATCH "/tenants/$T/items/$I" -d @rename.json --if-match '"etag-from-an-earlier-read"'
```

It takes a path, never a full address, so the token only goes to the API you named. The body goes to stdout (indented; `--raw` leaves it as it came, `--include` adds the status line and headers, where an `ETag` shows). The exit code is 0 for a 2xx answer and 1 for anything else, and a refusal is still printed as the API sent it, with its status on stderr ([ADR 0161](../../docs/adr/0161-lorenzo-api-passthrough.md)).

## Seeding a tenant

An import needs somewhere to put things: item prototypes to descend from (weapon, container, martial...) and the stat definitions the values are written to. `lorenzo seed` creates them once ([ADR 0143](../../docs/adr/0143-lorenzo-seed-taxonomy-and-stats.md)):

```bash
uv run lorenzo seed --tenant my-repository --dry-run   # what would be created (exit 2 if anything)
uv run lorenzo seed --tenant my-repository --yes       # create it
```

The taxonomy is a graph with multiple inheritance, so a weapon is several things at once: `longsword` descends from `blade`, `dnd5e-martial` and `dnd5e-versatile`. Weapon families (blade, axe, hammer, bow, crossbow, sling, firearm), weapon properties (finesse, heavy, light, reach, thrown, two-handed, versatile…), materials, consumables and kinds of gear (clothing, climbing, nautical…) are nodes of their own; a property carries its rules as a public description, which shows on every weapon that has it, and the property lists the weapons that do ([ADR 0146](../../docs/adr/0146-a-richer-item-taxonomy-and-keeping-what-the-sheet-says.md)). What the sheet says beyond that is kept: other names as an "Also known as" entry, a weapon's special rules as a note, and the ability, strength requirement, bundle size and flags as stats.

It writes to an existing `repository` tenant. A `play` tenant is refused, because a tenant's kind can't be changed and nothing in it could ever be published; `--allow-play-tenant` writes there anyway. The seed is in `src/lorenzo_cli/seed/builtin.toml`, tagged by layer (`core`, and `dnd5e` for D&D 5e's categories and dice, chosen with `--layer`; into [separate repositories](#core-and-dd-5e-are-two-repositories) if they are to be published). Stat names and types can't be changed once a tenant has them, so read that file before the first run against a tenant that matters.

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

`login` uses the authorization code flow with PKCE against a public Authgear client on a fixed loopback port (8766, with 8767 and 8768 as fallbacks). That client has to be registered on the Authgear project first (an operations step, see [docs/operations](../../docs/operations/local-authgear-setup.md)), and its issuer and client id given to `login` once ([Before you start](#before-you-start)). Until then `login` says so and exits; tokens through `LORENZO_TOKEN` or `--token-stdin` work regardless.

Environment: `LORENZO_API_URL` (the API base URL), `LORENZO_TOKEN`, `LORENZO_TENANT`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`.

## Tests

`mise run test` runs the unit tests, with coverage. `mise run test-e2e` runs `tests/e2e/`, which starts the real `apps/api` on a fresh database behind a fake Authgear and runs the CLI against it; it takes minutes, needs Postgres (`docker compose -f infra/docker-compose.yml up -d`, or CI's service), and skips without it. `LORENZO_REQUIRE_E2E=1` makes a missing stack a failure instead, as CI does, and `TEST_SHARD=2/3` runs one third of the test files (CI splits them over three runners, ADR 0148). `mise run check` does not include `test-e2e`, like inventory-web's.
