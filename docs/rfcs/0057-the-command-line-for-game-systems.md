# 0057 - The command line for game systems

Status: accepted (2026-11-17), decided with the maintainer, not built (slices C1 to C13).
Decisions: [ADR 0481](../adr/0481-the-clis-output-and-machine-contract.md) to [ADR 0493](../adr/0493-completing-names-from-a-private-cache.md).
Builds on [RFC 0052](0052-game-systems-in-one-library.md), [RFC 0053](0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md),
[RFC 0054](0054-features-grants-and-choices.md), [RFC 0055](0055-vocabulary-check.md) and [RFC 0056](0056-dice-values.md), which built the
API this covers, and on [RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) and [RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md),
which built the command line it changes. RFC 0055 left a client of the check to its own work: this is it. No API change.

## Purpose

`lorenzo` covers what the API learned about game systems: systems, the stat vocabulary with roles, bounds and dice, formulas of
every kind, templates, features, grant rules, prerequisites and grants, a campaign's system, and the vocabulary check. It does so
for a person at a terminal and for a script or an agent, and it is quick to start and never waits in silence.

What the command line did before systems is revised where it no longer fits. Before launch nothing is kept for old data: the seed,
its layers, `unseed`, the importers' commands, flags and walkthroughs change or go.

## Decided inputs

- The API of RFC 0052 to RFC 0056 as built: a system is a row with a slug, a group of a system forces the `<slug>_` prefix on its
  stats, a role is held by one neutral stat or group per library, a template is a filter and slots, formulas are curated kinds with
  limits, features are granted by rules and applied on demand, and the check is a read that refuses nothing.
- RFC 0016 and RFC 0053: no expression language and no interpreter. A formula is one curated kind with parameters.
- ADR 0156, ADR 0144 and ADR 0159: `--json` prints one document on stdout, exit codes are 0 (nothing to do), 2 (something to do or
  decide) and 1 (refused or failed), and a writing command says which Lorenzo it writes to (ADR 0164).
- ADR 0194: command and option names keep `tenant` and `--tenant`; text a person reads follows the identity's terminology.
- Measured on 2026-11-16 in an ext4 clone: `lorenzo --version` 469 ms warm and 984 ms with no bytecode, of which the generated models
  are 174 ms and 521 modules load for every command; `seed` makes 165 requests one after another in about 6 s with no output until
  the end; completion takes as long as `--version`.

## Hard invariants

- stdout carries what was asked for and nothing else; progress, notices and questions go to stderr.
- Colour never carries meaning alone: every status has a word and a symbol.
- A command that writes plans first. It asks at a terminal, `--yes` skips the question, `--dry-run` never writes, and with no terminal
  and no `--yes` it writes nothing and exits 2.
- Applying a document never deletes. Only `--prune` does, after showing what it would delete.
- Everything a document names is found by slug or name, so a second apply finds what the first made.
- No formula notation: a formula is written as the fields of its kind.

## Design

### Commands

```text
lorenzo plan|apply  FILE | --starter NAME  -t LIBRARY  [--prune] [--yes] [--json]
lorenzo export      SYSTEM | neutral       -t LIBRARY  [-o FILE]
lorenzo starter     list | show NAME
lorenzo schema      [document | output COMMAND]

lorenzo system          list | show | create | edit | delete
lorenzo stat-group      list | show | create | edit | delete     (--system, --role)
lorenzo stat-definition list | show | create | edit | delete     (--system, --role, --min, --max, --type dice)
lorenzo formula         set | show | preview | tree | delete
lorenzo template        list | show | create | delete | matching | view
lorenzo feature         list | show | award | activate | deactivate | remove
lorenzo grant-rule      list | show | create | delete
lorenzo grants          show | apply                            (--pick RULE=OPTION, --override)
lorenzo check           [--code C] [--entry E] [--parent P] [--kind K] [--stat S] [--fail-on warning|info]
lorenzo campaign        list | create | set-system
lorenzo being           create | show

lorenzo import mpmb      plan | apply
lorenzo import inventory FILE        (and `lorenzo export inventory`)
lorenzo import calendar  FILE        (and `lorenzo export calendar`)
```

`tenant`, `login`, `whoami`, `item`, `item-instance`, `character`, `pack`, `repo`, `legal` and `api` stay. `seed`, `unseed` and the
top-level `plan`, `apply` and `inspect` of the MPMB importer go (`inspect` becomes `lorenzo import mpmb inspect`). `lorenzo api`
stays the escape hatch for a route no command has (ADR 0161).

### The library document

One TOML document describes a system or the neutral vocabulary: the system row, stat groups, stats with roles, bounds and dice,
entries with parents, stats, tags and descriptions, formulas on entries, templates and slots, features with prerequisites, grant
rules with conditions and options, and parents added to entries another document owns. It has a `format` number and a published
JSON Schema, `requires` names the documents it builds on, and `export` writes it back so that applying an export to an empty library
and exporting again gives the same document. The command groups are edits over the same planner, so the two never disagree.

### Starters

Three documents ship with the command line: `neutral` (physical stats, roles assigned explicitly, the weight recipe, the forms and
materials, the placeholder for a player's own item), `dnd5e` (a system row on the `dnd5e-system` root, `dnd5e_` stats, damage as
dice, ability modifiers, proficiency by level, armour class with a cap, a sheet template, a fighting style chosen through a grant
rule; SRD 5.1 only, with its attribution) and `wrath-and-glory` (slug `wg`: attributes and skills with their bounds, the derived
traits as formulas, the dice pool as a dice formula, an example archetype with a talent and a choice; mechanics and numbers only, no
rules or setting text). A starter is applied to a repository, which is published and copied; applying one straight into a library is
for a library's own use.

### Feedback and speed

One console module draws every result: tables and trees in one style, a spinner for a wait of unknown length and a bar with a count
for a batch, both on stderr and only when stderr is a terminal and `NO_COLOR`, `--quiet`, `--no-progress` and `--json` allow.
Command groups load when they are named, the generated models when an operation first needs them. Within one run a vocabulary read
is cached; independent requests run four at a time in dependency order with output in a fixed order. Targets, warm: `--version`,
`--help` and completion under 150 ms; a read that needs one request under 250 ms plus the network. A test fails when a command
group's imports reach every command.

### Machine use

Every `--json` document carries a `format` number. With `--json` a failure is printed as one problem document on stdout and the
command exits 1. `lorenzo schema` prints the document schema and the shape of each command's `--json` output. Choices are given with `--pick`,
and nothing asks a question when `--yes` or `--json` is given.

## Delivery

Thirteen slices, each one pull request stacked on the one before, each tested on its own: unit tests for the pure parts, end-to-end
tests against the real API (`tests/e2e`), and the generated client in step with the API.

| Slice | What | ADR | Builds on |
| --- | --- | --- | --- |
| C1 | `main.py` split by command group, groups and models loaded on use, the start-up test | 0483 | |
| C2 | The console module, the write contract, `--json` failures and format numbers, applied to every existing command | 0481, 0482 | C1 |
| C3 | The MPMB, inventory and calendar commands under `lorenzo import` and `lorenzo export` | 0490 | C2 |
| C4 | Typed operations for every route of RFC 0052 to RFC 0056 | | C3 |
| C5 | The document planner for the vocabulary, `plan`/`apply`/`export`, `lorenzo schema`, `system`, `stat-group`, `stat-definition` | 0484, 0485 | C4 |
| C6 | Formulas in the document and `lorenzo formula` | 0486 | C5 |
| C7 | Templates, campaigns and beings in the document and their commands; `--system`, `--template`, `--campaign` on reads | 0487 | C6 |
| C8 | Features, grant rules, prerequisites and grants | 0488 | C7 |
| C9 | `lorenzo check` | 0489 | C8 |
| C10 | The three starters; the seed, its layers and `unseed` removed; the importers on the new names | 0491, 0490 | C9 |
| C11 | `repo copy-plan`, `copy`, `updates` and `contents` with systems, templates and warnings | 0492 | C10 |
| C12 | Completion of names from a private cache | 0493 | C11 |
| C13 | README, guides and the walkthrough, with its end-to-end test | | C12 |

The first step is C1: it changes no behaviour, and every later slice prints through what C2 builds on it.

## What the API does not have

Each is an issue against `apps/api`, not a change in this work:

- a formula that counts over a group's members, so that a limit such as "at most one of these in a team" is reported by the check;
- a bulk, transactional write of vocabulary, so that applying a document is not one request per row;
- filters on the stat group and stat definition lists (system, group, role, name), the system on a stat definition, and a system read
  by slug;
- a severity filter on the check, and totals that count findings.

## Not in scope

Refusing a write because of a computed value (RFC 0055 keeps the check a read); importing MPMB's classes, subclasses, races,
backgrounds, feats, spells and magic items, and deciding which kind a spell is; importing a character from D&D Beyond; commands for
entries beyond what the document and `being create` cover; native Windows; a formula notation; unit conversion.

## Open questions

- Roles are held by neutral stats only (ADR 0449). The starters assign `weight`, `height`, `is_container`, `physical` and `tags`; a
  system's price, armour, hit points and damage hold no role, so a card does not show them until a library gives a neutral stat that
  role. Whether a starter should ship neutral `price`, `armor` and `hp` stats is open.
- The neutral `weight` has no unit, as the seed's had none, because one system counts in pounds and another in kilograms. Whether
  the neutral starter names a unit is open.

## Consequences

Easier: a library gets a working system from a published repository in a few commands; a system is a file that can be read,
reviewed, exported and applied again; every command answers a person with feedback and a script with one document.

Harder, and accepted: every command, flag, seed document and walkthrough of the command line before this changes; applying a
large document is bounded by one request per row until the API has a bulk write; the starters are content to keep correct.

## As built

All thirteen slices are built as stacked pull requests, C1 to C13, each with an "As built" note on its ADR where it differs. In
short:

- Completing a name loads the command's group, since the completer sits on its parameter: about 280 ms against about 100 ms for
  the root; it reads only the cache file (ADR 0493).
- The API reports a merged stat's unit warning only for a merge it is told to make, so `copy --on-collision merge --dry-run` shows
  it and a plain `copy-plan` does not (ADR 0492).
- The published repositories are two, the equipment and the rules, not four (ADR 0491).
- Found on the way: a concurrent write of two values on one entry answers 500 (the writer serializes per row; issue #1282), and
  inventory-web still names the removed `lorenzo seed` (issue #1287).
