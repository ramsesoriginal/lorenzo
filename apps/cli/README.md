# apps/cli

The `lorenzo` command-line tool: creates repositories and applies the starters to them, imports MPMB standard items, authors a library's stat vocabulary, reads items and beings, imports inventories and calendars, publishes and copies repositories, and makes any authenticated request for a script. The stack is recorded in [ADR 0137](../../docs/adr/0137-lorenzo-cli-app-python-client-and-auth.md); the importer began as [RFC 0025](../../docs/rfcs/0025-lorenzo-cli-mpmb-item-importer.md).

Python 3.14, installed for you by `uv`. Linux and macOS (WSL included) are supported; native Windows isn't.

## Install it

On Linux or macOS (WSL included), with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=apps/cli"
lorenzo --help
```

That installs the `lorenzo` command from this repository's `main` branch, into its own environment. It isn't on PyPI: it only works against a Lorenzo `apps/api`, and its client is generated from that API's schema, so the two move together. Put `@<tag>` (or `@<commit>`) before the `#` to pin a version, and update with `uv tool upgrade lorenzo-cli`. To run it from a checkout of the repository instead, see below.

`lorenzo --version` says which one is installed. To complete commands and options with Tab, run `lorenzo --install-completion` once (it adds a line to your shell's startup file; `lorenzo --show-completion` prints the script instead, if you'd rather place it yourself). Tenant slugs aren't completed.

## Before you start

Three things have to be true before the first command does anything useful. The first two are about you and the Lorenzo you talk to, not about this tool.

1. **You have an account on the official Lorenzo.** It is the default: with nothing named, the CLI talks to it and signs in at its Authgear project, and `lorenzo login` is the whole setup ([ADR 0164](../../docs/adr/0164-the-official-instance-is-the-clis-default.md)). Your own Lorenzo (a local `apps/api`, a staging one, a fork) is a matter of naming it, see [Another Lorenzo](#another-lorenzo).
2. **To create a tenant, you need the `tenant-creator` role**, which the Authgear project's maintainer grants in its Portal. Nothing else in this tool needs it, and the API says so (`403`) if you lack it. (`whoami --json` tells you beforehand: `capabilities.create_tenant`, [ADR 0175](../../docs/adr/0175-me-says-what-you-may-create.md).)
3. **To import MPMB items, you have the sheet's data.** It is GPL-3.0 and not shipped; clone it (see [Reading MPMB files](#reading-mpmb-files)).

### The first run

```bash
lorenzo login           # opens your browser; --no-browser prints the address instead (WSL, SSH)
lorenzo whoami          # the API says who it thinks you are: the check that it all works
lorenzo login --token   # no browser here: approve a code in the account hub; see Personal access tokens
lorenzo tenant list     # the tenants you belong to
```

`login` says where it is signing in and for which API before it opens anything. A command that **writes** (creating a tenant, applying a document, importing, handing out a pack, publishing, granting, copying, `lorenzo api` with anything but `GET`) prints `Using the official Lorenzo at <address>.` on stderr, once, whenever the official one is the default; reads and `whoami` stay quiet (`whoami` shows the API with `(the default)` beside it). It is a line to read, not a question.

### Another Lorenzo

Name **all three** once, and `login` remembers them:

```bash
lorenzo --api-url http://localhost:8000 login --issuer https://example.authgear.cloud --client-id abc123
```

The official values are a *set*. If any of the three is named as something other than the official one, none of the others is filled in from the default: an official issuer is never assumed for somebody else's API, and the other way round, so a token can't be sent to one party under another's name. `lorenzo --api-url http://localhost:8000 login` alone means "that API, and no issuer": `login` then asks for the other two, and `LORENZO_TOKEN` (which needs no issuer) just works. Naming the official values themselves changes nothing. A habit worth having in a development shell: `export LORENZO_API_URL=http://localhost:8000`, so a forgotten flag can never reach the official one.

To go back, `lorenzo login` with the official values (or without a file at all): when what a login used is the official set, it forgets the remembered file and says so, rather than keeping a copy that would outlive them.

### Where the settings come from

Each of the three, for each command, in this order: **a flag** (`--api-url` before the command name, as in `lorenzo --api-url URL whoami`, and `--issuer` and `--client-id` on `login`), then **the environment** (`LORENZO_API_URL`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`), then **the file** `login` wrote: `$XDG_CONFIG_HOME/lorenzo/config.toml` (`~/.config/lorenzo/config.toml`), up to three plain lines with nothing secret in them. Anything named there wins over the official default. Only `login` writes the file, and only what you named, never the official defaults. `lorenzo logout` forgets your tokens and keeps the file; delete the file to forget the addresses too ([ADR 0157](../../docs/adr/0157-lorenzo-remembers-the-api-url-issuer-and-client-id.md)).

The token is looked for in this order: `--token-stdin` (the first line of stdin), `LORENZO_TOKEN`, then the stored login (`credentials.json` beside the settings, readable only by you, renewed on its own). `--tenant` can come from `LORENZO_TENANT`. Unattended use, a script holding its own credentials, isn't supported: the CLI is run by a person with their own token.

## Run it

```bash
mise run //apps/cli:dev -- --help
```

or, from this directory, `uv run lorenzo --help`.

The tool needs an access token for `apps/api`. `lorenzo login` gets one; to supply one yourself, against a local API:

```bash
export LORENZO_API_URL=http://localhost:8000
export LORENZO_TOKEN=...   # the token that `mise run //apps/api:dev-token` prints
uv run lorenzo tenant show <tenant-id-or-slug>
```

Or pipe a token in with `--token-stdin`. A token from the stored login is used last.

### Personal access tokens

`lorenzo login --token` needs no browser on the machine and no Authgear settings, only the API URL: it prints a code and an address, you open the address anywhere you are signed in to the account hub, check the code is the one shown, name the token, and approve. The token has no expiry unless you choose one there, acts as you (except that it cannot manage tokens or delete your account), and is listed under your profile with when it was last used, where you can revoke it. The stored file is `credentials.json`, readable only by you; anyone who can read it can act as you until the token is revoked.

## Commands

| Command | What it does |
| --- | --- |
| `lorenzo --version` | Says which version is installed. Needs no login |
| `lorenzo whoami [--json]` | Asks the API who the token you'd use belongs to, and says where the token came from: the check that a login works |
| `lorenzo tenant list [--kind repository\|play] [--json]` | The tenants you belong to, with each one's kind and your role |
| `lorenzo tenant create <name> [--slug S] [--description D] [--kind KIND] [--json]` | Creates a tenant and makes you its owner (a `repository`, which is what an import needs, unless `--kind play`; the kind can't be changed later). Needs the tenant-creator role. It starts empty: `lorenzo apply --starter neutral` next |
| `lorenzo tenant show <tenant>` | Reads one tenant (its `kind`, whether it is published) - the first call through the generated client |
| `lorenzo tenant delete <tenant> [--yes] [--json]` | Deletes a tenant and everything in it. **It can't be undone.** Needs the tenant-creator role and being one of the tenant's owners; asks you to type the slug (`--yes` skips that, `--json` needs it). A repository other tenants still hold a grant on is refused, with how to go on ([ADR 0184](../../docs/adr/0184-deleting-a-tenant.md)) |
| `lorenzo login --token` | Connects with a personal access token ([ADR 0269](../../docs/adr/0269-personal-access-tokens-hub-and-cli.md)): prints a code and the address of the account hub's *Connect a device* page, waits until you approve it there (naming the token and, if you like, an expiry), and stores it like any login. `whoami` then names it; `logout` forgets it here, and it works until you revoke it under your profile in the hub |
| `lorenzo [--api-url U] login [--issuer I] [--client-id C] [--no-browser]` / `lorenzo logout` | Stores or forgets a login, and remembers what you named for it (the official Lorenzo is the default, so a plain `lorenzo login` is enough, see [Before you start](#before-you-start)) |
| `lorenzo import mpmb inspect [--base FILE...] [FILE...]` | Shows what the JavaScript host reads from MPMB files (files, per-list counts and which file each entry came from, stubbed sheet names), without touching a tenant. Needs no login. Name files, `--base` files, or both: `--base` alone shows what the sheet ships |
| `lorenzo import mpmb plan --tenant <tenant> FILES...` | Works out what importing these MPMB files would do and changes nothing. Deterministic JSON with `--json`; exit 0 nothing to do, 2 changes pending, 1 something unresolved |
| `lorenzo import mpmb apply --tenant <tenant> FILES... --yes [--json]` | Imports them: what is resolved, and none of what needs a decision. Safe to run again, and unattended. `--json` prints one document: the plan, what was written, what failed |
| `lorenzo pack give <pack> --tenant <tenant> --owner <being-or-group>` | Hands an imported pack out: the API makes its containers and what is inside them, with quantities, in one go or not at all. A being takes the top of it into its hands; a group owns it with nothing in a container. `--dry-run` says what would be made; `--override` is a GM's, past what the owner can carry; `--json` prints what the API made |
| `lorenzo item list --tenant <tenant> [-q QUERY]` | The items you may add: for a player the public catalog, for a library member all of it. Title and id ([ADR 0190](../../docs/adr/0190-lorenzo-item-and-character-commands.md)) |
| `lorenzo character list --tenant <tenant> [--all]` | Your characters in a library, or with `--all` everyone's |
| `lorenzo item add <item> --tenant <tenant> [--owner CHARACTER] [--name N] [-n QUANTITY --into CONTAINER]` | Makes your own item, as on the web: one instance of the item (its id, slug or exact title) for the character (your only one, unless you name one), not carried, or a stack inside a container you hold. Prints the new id; `--json` prints the instance. The API says why when it isn't allowed (not public, switched off) |
| `lorenzo import inventory FILE --tenant <tenant> [--owner CHARACTER] [--add\|--replace] [--backup FILE] [--dry-run] [--yes] [--preprocess TABLE]` | Makes the things a [ledger](../../docs/guides/inventory-file-format.md) ([ADR 0226](../../docs/adr/0226-lorenzoledger.md)) lists, for a character ([ADR 0193](../../docs/adr/0193-lorenzo-inventory-import-and-export.md)). Each line is matched to an item by id, slug, exact title or a known other spelling; what matches nothing becomes an *Unsorted item* with the player's own name and notes, for the GM to sort. Nothing is made if a line can't be made as written. A character who already has things needs `--add`, which also moves what the file names by id. `--dry-run` says what would be made. Coming from D&D Beyond? [`lorenzo-beyond`](https://github.com/ramsesoriginal/lorenzo-beyond) writes the file. A GM or administrator can name any being they may list, by exact name ([ADR 0232](../../docs/adr/0232-inventory-import-any-being-replace-and-progress.md)). `--replace` starts a being's inventory over: what it owns and you can see is deleted (deepest first), then the file's things are made. Run it as the campaign's GM or an organizer, since a library owner who is neither sees none of a player's things. Whatever is tied up with someone else's is left alone, and the plan names it: a thing of the being's in another's container, a container holding another's thing, and the containers around those. The whole file is checked before the first delete, and `--backup FILE` first writes what is there as a ledger. `--dry-run` prints what would be made as a tree, and a progress bar shows the writing The table of other spellings is edited in `packages/inventory-names` and copied here with `mise run sync-names` ([ADR 0242](../../docs/adr/0242-inventory-names-the-spelling-table-shared.md)) |
| `lorenzo export inventory --tenant <tenant> [--owner CHARACTER] [--json] [-o FILE]` | Writes a character's inventory as a file: what they own, where it is, and what was noted, with each item's id so `import --add` reads it back as moves |
| `lorenzo repo publish\|unpublish\|grant\|revoke\|subscribers --tenant <repository>` | The repository's own side: publish it as a release (`--label`, `--notes`, `--breaking`; again, to make the next one, [ADR 0207](../../docs/adr/0207-the-release-ledger.md); a release that removes or changes what libraries hold is refused until `--acknowledge-breaking`, [ADR 0208](../../docs/adr/0208-the-release-digest-and-the-breaking-change-detector.md)), withdraw it, give a tenant access, take it back, list who has it. Owners only |
| `lorenzo repo list\|copy-plan\|copy\|updates --tenant <tenant>` | A tenant's side: which repositories it holds, what copying one would do, copying it, and taking what it changed since. `copy --again keep` or `purge` copies afresh a repository the tenant already copied. See [Publishing a repository](#publishing-a-repository) |
| `lorenzo repo contents --tenant <repository>` | What a repository holds: published or a draft and who it is granted to, what it is built on, how many stat groups, stat definitions, items and attachments ([ADR 0169](../../docs/adr/0169-seed-list-and-repo-contents.md)) |
| `lorenzo repo libraries --tenant <repository> --entry E\|--stat S\|--stat-group G` | How many libraries have copied an entry, a stat or a stat group, never which: what deleting it would mean to them. Nothing here blocks a delete ([ADR 0386](../../docs/adr/0386-how-many-libraries-hold-what-is-deleted.md)) |
| `lorenzo repo offer <tenant> --tenant <repository>` | Grant it, then copy it into that tenant; a copy already there is a success, so it is safe to run again; `--apply-updates` also takes the updates that need no decision |
| `lorenzo stat-group list\|show\|create\|edit\|delete`, `lorenzo stat-definition list\|show\|create\|edit\|delete` | A library's stat vocabulary: its groups and definitions, with systems, roles, bounds, display fields and hints ([ADR 0295](../../docs/adr/0295-cli-vocabulary-sheet-settings-and-reads.md), [ADR 0485](../../docs/adr/0485-system-and-vocabulary-commands.md)). See [Authoring the stat vocabulary and reading entries](#authoring-the-stat-vocabulary-and-reading-entries) |
| `lorenzo system list\|show\|create\|edit\|delete` | A library's game systems. See [Game systems and library documents](#game-systems-and-library-documents) |
| `lorenzo plan\|apply FILE\|--starter NAME -t LIBRARY [--prune]`, `lorenzo export SLUG\|neutral -t LIBRARY` | A system or the neutral vocabulary as one document: what applying it would do, applying it, and writing it back ([ADR 0484](../../docs/adr/0484-the-library-document.md)) |
| `lorenzo formula set\|show\|preview\|tree\|delete` | Formulas of every kind, one at a time ([ADR 0486](../../docs/adr/0486-formulas-from-the-command-line.md)) |
| `lorenzo template list\|show\|create\|delete\|matching\|view`, `lorenzo campaign list\|create\|set-system`, `lorenzo being create\|show` | Templates, the system a campaign plays, and beings ([ADR 0487](../../docs/adr/0487-templates-campaigns-and-beings-from-the-command-line.md)) |
| `lorenzo feature list\|show\|award\|activate\|deactivate\|remove`, `lorenzo grant-rule list\|show\|create\|delete`, `lorenzo grants show\|apply` | Features, the rules that grant them, and applying them with choices ([ADR 0488](../../docs/adr/0488-features-and-grants-from-the-command-line.md)) |
| `lorenzo check -t LIBRARY [--code C] [--entry E] [--parent P] [--severity S] [--fail-on warning\|info]` | What a library's stats get wrong without saying so; exit 1 only with `--fail-on` ([ADR 0489](../../docs/adr/0489-lorenzo-check.md)) |
| `lorenzo starter list\|show`, `lorenzo schema document\|output COMMAND` | The documents that ship with the CLI, and the JSON Schemas of the document and of each command's `--json` output. Need no login |
| `lorenzo tenant sheet-settings <tenant> [--being-stat-group G] [--weapon-stat-group G] [--ability-information-type T] [--clear-...] [--json]` | Reads a library's sheet settings, or changes only the ones named; each `--clear-...` unsets one |
| `lorenzo item show <item>`, `lorenzo item-instance show <instance>`, `lorenzo being show <being>` `--tenant <tenant> [--json]` | Reads an item, an instance or a being by id, link name or exact name: resolved stats, inheritance, containment and notes, and for a being its equipped weapons and abilities |
| `lorenzo import calendar FILE --tenant <tenant> [--choices F] [--review-notes] [--accept-warnings] [--dry-run] [--plan-out F] [--apply-plan F] [--timeout S] [--yes] [--json]`, `lorenzo export calendar <source-key> --tenant <tenant> [-O FILE]` | Imports an authored calendar document and exports the current managed source. See [Calendar files](#calendar-files) |
| `lorenzo api <METHOD> <path> [-d JSON] [-q K=V] [--paginate]` | One authenticated request to the API, for scripts. See [Scripting](#scripting) |

## Importing MPMB items

The order is: create a repository (`lorenzo tenant create "My Homebrew" --slug my-homebrew`), apply the [starters](#starters) once, then plan, then apply ([ADR 0144](../../docs/adr/0144-lorenzo-import-mapping-identity-plan-apply.md)). For something you mean to publish, split it into [two repositories](#equipment-and-rules-as-two-repositories) instead.

```bash
uv run lorenzo apply --starter neutral -t my-repository --yes
uv run lorenzo apply --starter dnd5e -t my-repository --yes

# The sheet's own SRD items (its data files are GPL-3.0 and are not shipped; clone the repository):
S=/tmp/mpmb/_variables
uv run lorenzo import mpmb plan  --tenant my-repository --base $S/ListsSources.js --base $S/Lists.js --base $S/ListsGear.js
uv run lorenzo import mpmb apply --tenant my-repository --base $S/ListsSources.js --base $S/Lists.js --base $S/ListsGear.js --yes

# Homebrew on top of it (a later file wins), with your own map:
uv run lorenzo import mpmb apply --tenant my-repository --base $S/ListsSources.js --base $S/Lists.js \
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

**Titles.** An item's displayed title is the title of its description, so `apply` titles a description with the item's name ([ADR 0165](../../docs/adr/0165-a-description-is-titled-with-its-items-name.md)). A description an older version titled "Description" is retitled by the next run: `plan` counts it under "to retitle" (`apply` says how many it retitled). Only that exact title is changed; one a person chose is left alone. `repo updates` doesn't carry information (ADR 0121), so a tenant that copied a repository is put right where the items were imported, by `apply` there.

Other flags: `--reconcile` re-parents items the map now files elsewhere (default is create-only, and a changed map only reports "N items would change parents"; it replaces only the parents the importer places, the starters' categories and the ones a map row mints, and leaves any other, such as a prototype attached by `--part system`); `--accept-moves` creates the items whose namespace changed; `--public-catalog` lets players list the imported items; `--part neutral|system` writes one half of each item ([below](#the-two-halves-of-an-item)); `--allow-play-tenant` writes into a play tenant, whose content can't be published.

### The two halves of an item

Without `--part` an item is written with everything the sheet says of it, on one item. For the [two repositories](#equipment-and-rules-as-two-repositories) it is written in two passes over the same files, so each repository holds the half that is its own ([ADR 0182](../../docs/adr/0182-the-importers-two-passes-neutral-and-system.md)):

- **`--part neutral`** is what is true anywhere: the item's name and other names, the sourcebook citation, its weight, its forms (weapon, melee, a blade), its materials, the kind of gear, a pack and its contents. It creates the item under those, and `--public-catalog` makes it public. It is for the equipment repository, and needs only the `neutral` starter.
- **`--part system`** is D&D's: the price, damage dice, range in feet, armour class and what armour asks of its wearer, the ability, the proficiency, the properties, and a weapon's `description` (its list of properties) and `tooltip` (its special rules). For each item that has any, it finds the neutral item **by its slug in the tenant's own copy of the equipment**, creates a prototype, "Longsword (D&D 5e)" with the slug `srd5e-weapons-longsword`, that is never public, with those parents, stats and text, and then adds it to the item's parents, last. In the rules repository the item is a copy, so that parent is an [attachment](../../docs/adr/0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md) and travels with the rules. An item with nothing of the system's (ammunition) gets no prototype, and an item the tenant doesn't have yet is held back with the way to put it there (run the neutral pass; take it with `repo copy` or `repo updates`).

A second run of either pass finds what the first made and attaches nothing twice. `plan` and `apply` say which half they are for, `--json` has `header.part` (`neutral`, `system` or `all`), and a held item says which pass held it: a price that can't be read holds only the system pass, a value no row knows holds both. `--public-catalog` is refused with `--part system`.

What is whose is decided by the starters ([ADR 0490](../../docs/adr/0490-the-importers-move-under-lorenzo-import.md)): a stat is the system's when its group belongs to a system (`dnd5e_price` and `dnd5e_damage` are D&D's, `own_weight` is neutral), a category the system's when it comes from the `dnd5e` starter, and a category a map row mints the part of its axis (`proficiency`, `tier` and `property` are the system's, `form` and `material` are neutral). A row says `part = "neutral"` or `"system"` only for what no starter decides: text, and a stat or a parent the starters don't have (neutral if it says nothing). Where a starter does decide, a `part` on the row is a map error. `[system_namespaces]` names the prototypes' namespace per file (`srd5e` for the sheet's own data, else the file's namespace and `-5e`), and `[system] label = "..."` the label in their names:

```toml
[namespaces]
"my-homebrew.js" = "hb-alice"        # the neutral item: hb-alice-weapons-purple-sword

[system_namespaces]
"my-homebrew.js" = "hb-alice-5e"   # its prototype: hb-alice-5e-weapons-purple-sword

[attributes.weapons]
lore = { transform = "information", type = "note", title = "Lore", part = "system" }
```

## Publishing a repository

A repository is a tenant of kind `repository`; other tenants draw on it by being **granted** it and **copying** it, and take its later changes as **updates** ([RFC 0024](../../docs/rfcs/0024-repositories.md)). After `tenant create`, `apply --starter` and `import mpmb apply`:

```bash
lorenzo repo publish --tenant my-homebrew --label 1.0                       # until now, nobody it is granted to can see it
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

`--apply` takes the changes that don't touch anything the tenant also changed and additions that collide with nothing, and only **released** ones: a row the repository edited after its latest release, or that a release since the tenant last updated called breaking, is left to be named, and an attachment is never taken this way (below; [ADR 0208](../../docs/adr/0208-the-release-digest-and-the-breaking-change-detector.md)). `repo updates` marks such rows ("edited since release 1.3", "breaking, release 1.2"). A conflict is never taken without being named: put the field in `take_upstream` (or `keep_local`) in an `--actions` file, the API's own action list ([ADR 0121](../../docs/adr/0121-repository-updates-and-re-sync.md)). `--dry-run` applies it all and rolls it back.

**Attachments.** A parent a repository adds to an entity it holds a copy of (a rules repository's prototype on an item it copied from an equipment repository) travels with a copy of the repository and with its updates ([ADR 0172](../../docs/adr/0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md)), so the rules are added to the items a tenant already has. `copy-plan` and `copy` count them on a step's line ("3 attachments") and list the ones they leave out, with the reason: the item or the prototype isn't there, or it would make a prototype loop. `repo updates` lists the attachments added since, the ones gone upstream and the ones removed here. `--apply` takes no attachment, added or removed, for it changes what an item the tenant already holds is: each is named in an `--actions` file (`"confirm": true` when a release called it breaking), which can be the list of actions or `{"actions": [...], "attachments": [{"child_source_id", "parent_source_id", "action": "add" | "detach"}]}`. Detaching drops the record and leaves the parent where it is: updating never takes a parent off an item ([ADR 0174](../../docs/adr/0174-the-cli-shows-attachments.md)).

### What a repository holds

```bash
lorenzo repo contents --tenant common-fantasy-eq
```

It reads one repository tenant and says whether it is published (or a draft) and how many tenants it is granted to; which repositories it is built on, that is the ones it has copied, with the date and whether they have published since; and how many stat groups, stat definitions and items it holds (categories included) and how many parents it attaches to items it copied (attachments, said only when there are some; `holds.attachments` in `--json`). `--json` prints the same as data. It only reads ([ADR 0169](../../docs/adr/0169-seed-list-and-repo-contents.md), [ADR 0492](../../docs/adr/0492-the-repository-commands-show-systems-templates-and-warnings.md)).

### Equipment and rules as two repositories

What is meant to be published is split in two, by starter ([RFC 0033](../../docs/rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md), [ADR 0491](../../docs/adr/0491-starters-replace-the-seed.md)):

| Repository | Holds | Built on |
| --- | --- | --- |
| equipment | The `neutral` starter, and the neutral half of every item, public | nothing |
| rules | The `dnd5e` starter, and D&D's half of every item: a prototype attached to the equipment's item | the equipment |

The rules are a *bridge* ([ADR 0120](../../docs/adr/0120-bridge-repositories-and-dependency-manifests.md)) over the equipment: the imported items are split between them (a longbow is a ranged weapon in the equipment and a martial one in the rules). Another system takes the equipment and brings its own starter.

#### Setting them up

Each repository is built on the one above it, so the copy comes before the starter that needs it, and a repository publishes once it holds what it should ([ADR 0183](../../docs/adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md); `tests/e2e/test_setup.py` runs these commands against the real API).

```bash
S=/tmp/mpmb/_variables    # the sheet's data, see Reading MPMB files
BASE="--base $S/ListsSources.js --base $S/Lists.js --base $S/ListsGear.js"

# the equipment: the neutral starter, and the neutral half of every item, public
lorenzo tenant create "Common Fantasy Equipment" --slug common-fantasy-eq
lorenzo apply --starter neutral -t common-fantasy-eq --yes
lorenzo import mpmb apply --tenant common-fantasy-eq --part neutral --public-catalog $BASE --yes
lorenzo repo publish --tenant common-fantasy-eq

# the rules: a copy of the equipment, the dnd5e starter, then D&D's half of every item
lorenzo tenant create "Common D&D5e Equipment" --slug dnd5e-common-eq
lorenzo repo offer dnd5e-common-eq --tenant common-fantasy-eq --yes
lorenzo apply --starter dnd5e -t dnd5e-common-eq --yes
lorenzo import mpmb apply --tenant dnd5e-common-eq --part system $BASE --yes
lorenzo repo publish --tenant dnd5e-common-eq
```

`repo offer` grants a repository to a tenant and copies it in, and for a bridge it does the same for what the bridge is built on. The commands need the `tenant-creator` role and the sheet's data (see [Before you start](#before-you-start)); homebrew goes in as more files after `$BASE` in **both** `import` lines, so the item is written in two halves. **Starting over:** `lorenzo tenant delete` takes a tenant and everything in it ([ADR 0184](../../docs/adr/0184-deleting-a-tenant.md)), from the top down: a repository that other tenants still hold a grant on is refused, so the table goes first, then the rules, then the equipment (`lorenzo tenant delete my-table --yes`, and so on). The slugs are free afterwards.

#### A table takes them

```bash
lorenzo tenant create "My table" --slug my-table --kind play
lorenzo repo offer my-table --tenant common-fantasy-eq --yes   # the equipment alone is usable
lorenzo repo offer my-table --tenant dnd5e-common-eq --yes     # later, D&D, on the items it already has
```

A table needs a grant on **each** repository, since grants aren't transitive; `offer` makes them, for whoever owns them all, and a single copy brings the others in first (one offer of the rules to a new table copies the equipment too). Someone who owns the rules but not the equipment is told which command to ask its owner for. A table that took the equipment first and the rules later keeps its Purple sword and its Weapon: the rules' prototype is a parent they add to the sword the table has, so that sword has D&D's dice and price afterwards (it still has one sword, not two), and the starter's attachments give every Weapon the Economic object and a `dnd5e_price` of 0. The prototypes are never public, so a player lists the neutral items and a GM, in the whole catalog, sees both.

#### Corrections, and equipment that grows

A correction is taken from the repository it was made in, and nothing else has to move ([ADR 0183](../../docs/adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)):

```bash
lorenzo repo publish --tenant common-fantasy-eq                  # the equipment corrects an item
lorenzo repo updates common-fantasy-eq --tenant my-table --apply # each table takes it from there
```

The rules aren't asked, and the table's sword keeps the rules' prototype. A correction to the rules goes the same way. **Publishing again is the announcement, not the permission**: `repo updates` reads a repository as it is now, so a table sees a change before it is published, and `repo list` says "updated since" once it has been. The rules take the equipment's updates when their author wants their copy current, and **have to before they import D&D's half of new equipment**, since the system pass finds an item in the rules' own copy of the equipment (an item they don't have is held, with the way out). Rules that take a correction keep what they attached.

```bash
lorenzo import mpmb apply --tenant common-fantasy-eq --part neutral --public-catalog $BASE more.js --yes
lorenzo repo publish --tenant common-fantasy-eq
lorenzo repo updates common-fantasy-eq --tenant dnd5e-common-eq --apply   # the rules' copy of it first
lorenzo import mpmb apply --tenant dnd5e-common-eq --part system $BASE more.js --yes
lorenzo repo publish --tenant dnd5e-common-eq
lorenzo repo updates common-fantasy-eq --tenant my-table --apply            # then each table: the items,
lorenzo repo updates dnd5e-common-eq --tenant my-table --apply              # and the prototypes on them
```

A table that takes the rules first gets the prototypes and lets each attachment **wait** for its item (`the item it attaches to isn't here`; exit 2, nothing lost): once the equipment's items are there, name each attachment in an `--actions` file (`repo updates` lists them). A bridge's own edits to its copy of a dependency don't travel, apart from the parents it adds to its copies (attachments, above): to change how an equipment entry behaves under D&D, author one that inherits from it, or attach one to it.

#### What it doesn't do yet

- **No way to take D&D back off a table.** Updating never takes a parent off an item; a tenant that wants to undo the rules removes the prototype from its items itself.
- **No setup in one command**, and nothing that says on a table's item which repository each part of it came from.

For a table's own use, or for trying things, one library can hold both starters: `apply --starter neutral`, `apply --starter dnd5e`, then `import mpmb apply` without `--part` writes each item with both halves on it.

## Scripting

- **Writing.** Every command that writes shows what it will do, then asks once at a terminal; `--yes` skips the question, and `--dry-run`, where a command has it, never writes. With no terminal and no `--yes` it writes nothing and exits 2 ([ADR 0482](../../docs/adr/0482-one-write-contract-for-every-cli-command.md)). `lorenzo api` asks too, for anything but `GET`.
- **Exit codes.** 0 is done or nothing to do, 2 is something to do or to decide that was not done, and 1 is refused or failed. Each command's `--help` says what 0 and 2 mean for it.
- **`--json`** (on every command that prints a result) prints exactly one JSON object on stdout, with `"format": 1` beside what it reports; a list is under a key (`{"format": 1, "tenants": [...]}`). A failure under `--json` is one object too, `{"format": 1, "error": {"status", "code", "message", "details"}}`, with exit 1. It never asks a question, so a command that writes needs `--yes` with it. A file a command writes (a calendar, a ledger) and `lorenzo api`'s answer keep their own shape ([ADR 0481](../../docs/adr/0481-the-clis-output-and-machine-contract.md)).
- **Feedback.** Whatever is for a person goes to stderr: notices, warnings (`⚠`), errors (`✗`), questions, and progress: a spinner while the API takes a moment, a bar with a count for a batch. Nothing animates when stderr is not a terminal, with `NO_COLOR`, with `--json`, or with `--no-progress` before the command (a wait is then one plain line); `--quiet` before the command drops notices and progress and keeps the result, warnings and errors.
- **`lorenzo api`** is for everything else, with the login you already have, so no token is pasted into a shell:

```bash
lorenzo api GET /tenants --paginate | jq '.[].slug'
lorenzo api POST /tenants -d '{"name": "Table One", "kind": "play"}'
lorenzo api PATCH "/tenants/$T/items/$I" -d @rename.json --if-match '"etag-from-an-earlier-read"'
```

It takes a path, never a full address, so the token only goes to the API you named. The body goes to stdout (indented; `--raw` leaves it as it came, `--include` adds the status line and headers, where an `ETag` shows). The exit code is 0 for a 2xx answer and 1 for anything else, and a refusal is still printed as the API sent it, with its status on stderr ([ADR 0161](../../docs/adr/0161-lorenzo-api-passthrough.md)).

## Starters

An import needs somewhere to put things: categories to descend from (weapon, container, martial...) and the stat definitions the values are written to. The CLI ships them as library documents, the **starters**, and nothing else seeds a library ([ADR 0491](../../docs/adr/0491-starters-replace-the-seed.md)):

| Starter | Holds |
| --- | --- |
| `neutral` | What is true of a thing in any game: the stat groups `physical`, `sourcebook` and `tags`, the weights and flags (`own_weight`, `bundle_amount`, `is_container`, `is_magical`...), the weight formulas, and the forms and materials (weapon, armor, tool, the kinds of gear, blade, bow...) with bare slugs, with `physical-object` and `unsorted` (the placeholder for a player's own item) |
| `dnd5e` | D&D 5e's rules as the system `dnd5e`: stats prefixed `dnd5e_` (abilities and their modifiers, level, proficiency bonus, armour class, price, damage as dice, range, the weapon properties), its categories under the root `dnd5e-system`, sheet templates, a class with a choice and the features group. Needs `neutral`; it attaches the Economic object, with a `dnd5e_price` of 0, to the neutral forms. Rules text from the SRD 5.1 (CC-BY-4.0) |
| `wrath-and-glory` | Wrath & Glory as the system `wg`: attributes as rating, bonus and total; the eighteen skills, a dice pool and a roll for each; the traits (Defence, Resilience, Determination, Max Wounds and Shock, Conviction, Resolve, Passive Awareness, Influence, Wealth, Speed, Size) with their floor of 1; Wrath, Wounds, Shock, Corruption, Faith, Ammo and XP; the wargear profile (damage, ED, AP, Salvo, three ranges, Armour Rating, Invulnerable, Bulk, Powered, Value, Rarity) and a template. Checked against the core rulebook and its character sheets; no rules text. The five species, the 27 archetypes of the core rulebook with their abilities, and its talents and Faith talents, by name, XP cost, ratings, requirements and page: what each does is in the book. A character takes an archetype as its parent |

```bash
lorenzo starter list                                     # what ships, with what each needs
lorenzo starter show dnd5e > dnd5e.toml                  # read one, or start your own from it
lorenzo plan  --starter neutral -t my-repository         # what applying it would do
lorenzo apply --starter neutral -t my-repository --yes
lorenzo apply --starter dnd5e   -t my-repository --yes
```

A starter is applied like any [library document](#game-systems-and-library-documents): what is there is left, what is missing is written, and a second run has nothing to do. Stat names and types can't be changed once a library has them, so read the starter before the first run against a library that matters. The MPMB importer writes to the stats and categories of `neutral` and `dnd5e`, and a library that lacks them is told to apply them first.

## Reading MPMB files

MPMB's additional-content files are executable JavaScript, so they are evaluated, not parsed ([ADR 0138](../../docs/adr/0138-lorenzo-cli-js-host.md)). `lorenzo_cli.evalworker` runs an embedded V8 (`mini-racer`) in a subprocess that is given no credentials and is killed on a timeout, and returns plain JSON in which a `RegExp` is `{"$re": [source, flags]}` and a function is `{"$fn": text}` (never called).

Homebrew is written against lists that already hold the sheet's SRD data, and some files patch it, so pass the sheet's own files first as `--base`:

```bash
git clone https://github.com/morepurplemorebetter/MPMBs-Character-Record-Sheet /tmp/mpmb
uv run lorenzo import mpmb inspect \
  --base /tmp/mpmb/_variables/ListsSources.js --base /tmp/mpmb/_variables/Lists.js \
  --base /tmp/mpmb/_variables/ListsGear.js my-homebrew.js
```

Leave `my-homebrew.js` out to see only what the sheet ships, as `plan` and `apply` also allow.

The sheet's data is GPL-3.0 and is not shipped with Lorenzo. `tests/corpus/` holds the golden fixtures every engine must reproduce; `LORENZO_UPSTREAM_CORPUS=/tmp/mpmb uv run pytest tests/test_evalworker_upstream.py` runs the worker against the real thing.

## The API client

`src/lorenzo_cli/client/models.py` is generated from `apps/api`'s OpenAPI document and committed. After changing `apps/api`'s routes or schemas:

```bash
mise run //apps/cli:generate-schema
```

CI's `client-drift` job runs `check-schema`, which fails on any difference. `src/lorenzo_cli/client/ops.py` lists the operations the CLI calls; a test checks each against the dumped schema.

## The Authgear client

`login` uses the authorization code flow with PKCE against a public Authgear client (a Single Page Application, no secret) on a fixed loopback port: 8766, with 8767 and 8768 as fallbacks. The official one is registered and built in as the default ([deployment-setup](../../docs/operations/deployment-setup.md#appsclis-own-authgear-application-adr-0137-0157)); for another Authgear project, register a client the same way and give its issuer and client id to `login` once. Tokens through `LORENZO_TOKEN` or `--token-stdin` work regardless.

Environment: `LORENZO_API_URL` (the API base URL), `LORENZO_TOKEN`, `LORENZO_TENANT`, `LORENZO_AUTHGEAR_ISSUER`, `LORENZO_AUTHGEAR_CLIENT_ID`.

## Tests

`mise run test` runs the unit tests, with coverage. `mise run test-e2e` runs `tests/e2e/`, which starts the real `apps/api` on a fresh database behind a fake Authgear and runs the CLI against it; it takes minutes, needs Postgres (`docker compose -f infra/docker-compose.yml up -d`, or CI's service), and skips without it. It runs on `E2E_WORKERS` parallel workers, four by default and `E2E_WORKERS=0` for one process (a single test, a debugger), each with its own API process and a database of its own, cloned from a migrated template and dropped at the end, so the Postgres user needs to be able to create databases, as the compose one can. The tests of what the importer does start from a copy of one repository holding the `neutral` and `dnd5e` starters that the run builds once per worker; the tests of the starters apply them. `LORENZO_REQUIRE_E2E=1` makes a missing stack a failure instead, as CI does, and `TEST_SHARD=2/3` runs one third of the test files (CI splits them over three runners, ADR 0148). `mise run check` does not include `test-e2e`, like inventory-web's.

## Authoring the stat vocabulary and reading entries

These commands use the existing API and its permissions ([ADR 0295](../../docs/adr/0295-cli-vocabulary-sheet-settings-and-reads.md)). `--tenant` accepts a library's or repository's id or slug, and can come from `LORENZO_TENANT`. Stat and group references accept an id or an exact name, ignoring case; ambiguous names are refused with candidate ids.

```bash
lorenzo stat-group list -t my-library
lorenzo stat-group create Vitals -t my-library --priority 10 --position 0
lorenzo stat-group edit Vitals -t my-library --name Health --mandatory
lorenzo stat-definition create maximum -t my-library --group Health --type int
lorenzo stat-definition create stress -t my-library --group Health --type int --max-hint maximum --adjustable-in-play --pin
lorenzo stat-definition edit stress -t my-library --unit points --no-pin --position 1
lorenzo stat-definition list -t my-library --json
```

A new definition takes `--type int|float|text|bool|enum|dice`, a required `--group`, and, for an enum, repeated `--enum-value` options. Its optional display fields are `--unit` (not for dice), `--adjustable-in-play`, `--pin`, `--signed` and `--position`. Hints are `--max-hint`, `--min-hint` and `--resolved-hint`, naming another definition of the same tenant. A maximum or minimum hint must be numeric; hints are clues, not limits on values. `--min` and `--max` are bounds an int or a float holds to ([ADR 0403](../../docs/adr/0403-stat-scales.md)), and `--role` says what the API reads it for (`weight`, `price`, `armor`...; [ADR 0449](../../docs/adr/0449-roles-the-api-reads-a-stat-by-what-it-is-for.md)).

A group takes `--system SLUG` to belong to a game system; every stat in it is then named `<slug>_something` (`wg_strength`), and the CLI says so before it asks ([ADR 0448](../../docs/adr/0448-a-game-system-as-a-row.md)). A role (`--role physical|economic|destroyable|damaging|tags` for a group) is held by one row of no system per library. Lists are tables with each row's system, role and bounds; `--system SLUG` keeps that system's rows and the neutral ones, `--neutral` only the neutral ones, and `stat-definition list --group G` one group's. `show` reads one row, `delete` removes one nothing uses (the API refuses otherwise).

`edit` changes only the options you name. Boolean flags have negative forms (`--no-pin`, `--no-signed`, `--no-adjustable-in-play`, and a group's `--no-mandatory`). Use `--clear-unit`, `--clear-max-hint`, `--clear-min-hint`, `--clear-resolved-hint`, `--clear-role`, `--clear-min` or `--clear-max` to clear a nullable field, and a group's `--no-system` to make it neutral; setting and clearing it together is refused. A definition's name, type and group cannot be edited by the API. Groups can edit their name, priority, mandatory flag, position, system and role. Priority decides inheritance ties; position decides display order. Vocabulary writes require the API's administrator permissions.

## Game systems and library documents

A game system is a row with a slug (`ds`, `wg`): the prefix of its stats, what a campaign plays, and the entry its content descends from ([ADR 0448](../../docs/adr/0448-a-game-system-as-a-row.md)).

```bash
lorenzo system create ds "Dust and Sun" -t my-library
lorenzo system list -t my-library
lorenzo system show ds -t my-library          # its groups, templates and campaigns
lorenzo system edit ds -t my-library --root ds-root
```

A whole system, or the neutral vocabulary, is one TOML document ([ADR 0484](../../docs/adr/0484-the-library-document.md)): the system, its stat groups and stats (with roles, bounds and dice), entries with parents, values, tags and a description, and parents added to entries another document owns. Everything is named by name or slug, never by id, so one document applies to any library and a second apply finds what the first made.

```toml
format = 1
name = "ds"
requires = ["neutral"]

[system]
slug = "ds"
name = "Dust and Sun"
root = "ds-root"

[[group]]
name = "ds_vitals"
system = true

[[stat]]
name = "ds_stamina"
group = "ds_vitals"
type = "int"
min = 0
max = 20

[[stat]]
name = "ds_bite"
group = "ds_vitals"
type = "dice"

[[entry]]
slug = "ds-root"
name = "Dust and Sun"
description = "Everything of Dust and Sun descends from this."

[[entry]]
slug = "ds-hunter"
name = "Hunter"
parents = ["ds-root"]
stats = { ds_stamina = 12, ds_bite = "1d6" }
```

```bash
lorenzo plan ds.toml -t my-library            # what it would do; exit 0 nothing, 2 changes, 1 refused
lorenzo apply ds.toml -t my-library --yes     # write it, four requests at a time, in dependency order
lorenzo export ds -t my-library -o ds.toml    # a system back as a document (export neutral for the rest)
lorenzo schema document > lorenzo-document.schema.json   # for an editor to check the file
```

`apply` sets what the document names and leaves what it does not; it never deletes. `--prune` also removes what the document's system no longer names, shown first: its stat groups and stats, and the entries under its root that are features or that others inherit from (a leaf item imported under the root is content and stays). It is refused for a document without a `[system]`. A description is created when an entry has none; one that differs is reported, not rewritten. `lorenzo starter list|show` names and prints the documents that ship with the CLI, and `--starter NAME` on `plan` and `apply` stands for one. `lorenzo schema output COMMAND` prints the shape of a command's `--json` output.

### Templates, campaigns and beings

A template says what an entry of a kind, under an ancestor, is shown as: its slots, in order (stats of a group or named stats, information of a type, what it holds, its tags, its features; [ADR 0451](../../docs/adr/0451-templates-a-sheet-as-data.md)). A campaign plays a system, and its beings' sheets are read through that system's template ([ADR 0452](../../docs/adr/0452-a-campaign-names-a-system-and-the-sheet-reads-a-template.md)).

```toml
[[template]]
name = "Datacard"
system = true          # the document's system; a slug for another; false for none
kind = "being"
ancestor = "kt-operative"

[[template.slot]]
kind = "stats"
label = "Profile"
group = "kt_profile"   # or stats = ["kt_move", { stat = "kt_wounds", label = "W" }]
```

```bash
lorenzo template create --from card.toml -t lib       # or replace the one of that name
lorenzo template list -t lib --system kt
lorenzo template matching hale -t lib                  # what an entry matches
lorenzo template view hale Datacard -t lib             # the entry read through it
lorenzo campaign create League --slug league --system kt -t lib
lorenzo campaign set-system league --none -t lib
lorenzo being create Hale --parent kt-gunner --slug hale -t lib
lorenzo being show hale -t lib --campaign league       # the sheet as the campaign shows it
```

`item show`, `item-instance show` and `being show` take `--system SLUG` to read an entry as one system shows it.

### Features and grants

A feature is an entry of kind `feature`; an entry holds one when it is awarded, granted by a rule on something it inherits from or holds, or picked from a rule's choice ([ADR 0488](../../docs/adr/0488-features-and-grants-from-the-command-line.md)). In a document a feature has `prerequisites`, and a `[[grant_rule]]` sits `on` an entry with a `label`, a `mode` (`all`, or `choose` with `min` and `max`), its `options` (or an `option_category`) and its `conditions`:

```toml
[[grant_rule]]
on = "ft-fighter"
label = "Fighting style"
mode = "choose"
min = 1
max = 1
options = ["ft-archery", "ft-defence"]
```

```bash
lorenzo grants show hero -t lib                                   # held, due, open choices, orphaned
lorenzo grants apply hero -t lib                                  # a dry run first; asks each choice at a terminal
lorenzo grants apply hero -t lib --pick "Fighting style=Archery" --yes   # a script answers with --pick
lorenzo feature award ft-defence --to hero -t lib
lorenzo feature deactivate ft-defence --on hero -t lib
lorenzo feature remove ft-defence --from hero -t lib
lorenzo grant-rule list --on ft-fighter -t lib
lorenzo grant-rule create --from rule.toml -t lib
```

`grants apply` exits 2 when a choice is left open or nothing was applied, and a GM's `--override` passes prerequisites and counts by, said in a warning.

### Checking a library

`lorenzo check` is the vocabulary check of RFC 0055: what a library's stats get wrong without saying so. It reads; nothing is refused or written ([ADR 0489](../../docs/adr/0489-lorenzo-check.md)).

```bash
lorenzo check -t lib                                    # grouped by entry, with a count at the end
lorenzo check -t lib --code unset-input --parent weapon
lorenzo check -t lib --severity warning --json
lorenzo check -t lib --fail-on warning                  # exit 1 on a warning, for a script or CI
```

The codes are `unset-input`, `own-value-shadows-formula` and `tie` (warnings), and `computed-outside-scale`, `above-hint` and `formula-chain-depth` (notes; `tie` needs `--entry`). Without `--fail-on` it exits 0 whatever it finds. `apply`, `import mpmb apply` and `repo copy` do not run it; they end with a line that names it.

### Formulas

A formula is one of the API's curated kinds with its fields, never an expression ([ADR 0486](../../docs/adr/0486-formulas-from-the-command-line.md), RFC 0016): `linear`, `comparison`, `sum`, `contents`, `min`, `max`, `product`, `ratio`, `select`, `dice_value` and `dice`. In a document it is a `[[formula]]` with `on` (the entry), `stat`, `kind` and the kind's fields, a stat named by its name (`source`, `left`, `right`, `numerator`, `denominator`, `count`, `sides`, `where`, a term's or input's `stat`, `factors`) and `round` for the rounding:

```toml
[[formula]]
on = "tt-character"
stat = "tt_proficiency"
kind = "select"
source = "tt_level"
mode = "threshold"
steps = [{ from = 1, result = { number = 2 } }, { from = 5, result = { number = 3 } }]
```

```bash
lorenzo formula set tt_strength_mod --on tt-character -t lib --kind linear --source tt_strength --multiplier 0.5 --offset -5 --round floor
lorenzo formula set tt_armour --on tt-fighter -t lib --kind min --input tt_dex_mod --input 2
lorenzo formula set tt_proficiency --on tt-character -t lib --from proficiency.toml   # a select, with its steps
lorenzo formula show tt_strength_mod --on tt-fighter -t lib      # its own, or the one it inherits
lorenzo formula preview tt_damage --on tt-fighter -t lib         # the value and each input; dice as 3d6
lorenzo formula tree tt_damage --on tt-fighter -t lib            # the chain down, and what reads it
lorenzo formula delete tt_armour --on tt-fighter -t lib
```

The limits of a kind are checked before anything is sent (two to five inputs or factors, one to twenty terms, one to sixty-four steps, a dice count of 1 to 100 and sides of 2 to 1000), and `preview` with `--kind` or `--from` evaluates a formula before it is saved. `--warnings` on `set` asks the vocabulary check about what it wrote.

The library's being stat group, weapon stat group and ability information type use one command. With no setting options it reads them; with options it changes only those named. The ability type is free text, not a separately created vocabulary row.

```bash
lorenzo tenant sheet-settings my-library
lorenzo tenant sheet-settings my-library --being-stat-group Vitals
lorenzo tenant sheet-settings my-library --weapon-stat-group Weapons --ability-information-type ability
lorenzo tenant sheet-settings my-library --clear-weapon-stat-group --clear-ability-information-type
```

The being stat group is an optional tenant selection ([ADR 0296](../../docs/adr/0296-being-stat-group.md)); `--clear-being-stat-group` unsets it, and omitted options preserve it. The API accepts and validates a campaign on the sheet read but does not override this setting. Beings uses the setting to choose the stats its sheet shows ([ADR 0297](../../docs/adr/0297-beings-stat-selection.md)).

Read an item, an instance or a being by id, link name or exact name/title:

```bash
lorenzo item show sword -t my-library
lorenzo item-instance show <instance-id> -t my-library
lorenzo being show 'Ashfang' -t my-library
```

The terminal shows resolved stats in vocabulary order with units, hints and where they came from, inheritance, containment and the notes you can read, with their authors. Items include inherited descriptions; instances also show their owner and binding. A being adds its equipped weapons and abilities from the library's settings. The API decides what you may see. `--json` on any new command prints one unrendered document; a `show` document has `entry` and `item`, `item_instance` or `sheet`.

Descriptions and notes are drawn as LorenzoScript, using the same parser as the web apps. Headings, emphasis, nested lists, quotes, tables, code, tasks, footnotes, dates, entity links and `{stat-name}` work in the terminal. Links resolve as your signed-in account, including `my/` in the entry's context; unresolved references stay readable as text. Pictures use their alternate text without downloading media, math is shown as its source, world-calendar dates stay as written, and CSS classes have no terminal appearance. Code stays literal. Authored terminal control characters are stripped. There is no terminal play editor.

The parser is bundled in the wheel, so installing and running the CLI does not require Node. After changing `packages/lorenzoscript/src`, regenerate it with `mise run //apps/cli:bundle-lorenzoscript` (the repository's JavaScript dependencies must be installed). A source-digest test catches a stale bundle, and CI tracks the CLI's dependency on LorenzoScript.

## Calendar files

Convert saved donjon exports offline with `lorenzo-convert donjon`, or author a
[native calendar JSON document](../../docs/guides/calendar-file-format.md). Calendar import
works in a library or repository; it brings no setting data.

```bash
lorenzo import calendar isles.calendar.json --tenant my-library --dry-run --json
lorenzo import calendar isles.calendar.json --tenant my-library --choices choices.json \
  --accept-warnings --dry-run --plan-out reviewed-plan.json
lorenzo import calendar isles.calendar.json --tenant my-library --choices choices.json \
  --accept-warnings --apply-plan reviewed-plan.json --yes
lorenzo export calendar isles --tenant my-library -O isles.current.json
```

`--review-notes` asks for each note's classification (note, Fact, Event or recurring observance).
Otherwise a choices file can classify notes individually or group several explicitly into one
Event. `--accept-warnings` deliberately acknowledges the displayed document warnings. Applying
requires a ready plan and confirmation (`--yes` for noninteractive use); `--json` prints exactly
one plan or receipt, with review messages on stderr. Saved plans keep the reviewed request and
are refused after changes to the file, choices or local material. Repeating a successful import
creates no duplicates, including retrying after a lost response.

A choices file contains optional `annotations`, `definition`, `is_public`, `period_is_public`,
`accepted_warnings` and `resolutions`. Only keys present are overridden. For example:

```json
{
  "annotations": {
    "note-3286-6-16": {"classification": "event", "group": "storm", "title": "Storm"},
    "note-3286-6-17": {"classification": "event", "group": "storm", "title": "Storm"}
  },
  "resolutions": {"$calendar": "keep_local", "event:storm": "take_source"}
}
```

The plan names conflict keys for `keep_local` or `take_source`. Taking the source changes its
managed text, name, public flags, rule or selected dates; additional payloads, other information,
About edges and explicit knowledge grants are preserved. A changed classification/grouping
creates new material only after review and retains the former entries. Omitted source material
is retained. New period audiences use `period_is_public`; existing period audiences are edited
separately. Definitions that erase recorded dates/rules remain refused.

Export covers the current annotations managed by that source key, preserving original source
values. It does not claim to export every locally authored entry. Expanded bundles or date
mappings that the native text-source format cannot represent are refused instead of dropped;
formerly imported material outside the active source is called out. Keep exported files and
saved plans private when their source or notes are private. Import provenance/receipts remain
local and are not repository content; the authored calendar and entries copy normally.

### Waiting for a calendar import

Calendar import reports the number of source notes and shows a spinner with elapsed time
while the API plans or saves. Redirected output uses plain stage messages on stderr;
`--json` keeps stdout machine-readable. Note review shows your position in the source notes.
The API saves the calendar and dated notes in one transaction, so there is no per-note
save percentage before confirmation.

Planning and saving wait up to 300 seconds for a response. Use `--timeout 600` on
`lorenzo import calendar` to allow more time; other CLI requests retain their usual timeout.
If the connection times out, the outcome is unconfirmed: the server may still finish.
Do not delete the calendar. Preview again with the same source key, file and note choices
using `--dry-run`; unchanged units are already imported. Reimports do not duplicate them.
Notes are attached to their dates; look in the source year and month rather than the
calendar entry's own Information. Imported audiences remain restricted unless explicitly chosen.

## Legal notice and privacy policy

`lorenzo legal` prints where the legal notice and the privacy policy of the Lorenzo you use are (and its support link, if it has one), by asking the API's public registry. It needs no login, and nothing about any operator is built into the command ([ADR 0439](../../docs/adr/0439-legal-notice-and-privacy-policy.md)). `--json` prints them as JSON. A command-line login stores its credentials in a file only your user can read; the privacy policy describes this.
