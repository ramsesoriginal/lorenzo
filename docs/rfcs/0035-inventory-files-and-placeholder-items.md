# RFC: Inventory files and placeholder items — importing and exporting a character's gear, with a stand-in for what the catalog does not know

Status: accepted, decided with the maintainer on 2026-10-05: the build order (placeholders in the API first, then import and export, then "Not in the list" in inventory-web, then a GM view for sorting them), a placeholder badge on the board, notifying the player when a GM sorts one, no flooding limit (a social matter, not a code one), the file format in [§1](#1-the-inventory-file) (specified in the [guide](../guides/inventory-file-format.md)), the matching order in [§3](#3-how-a-line-finds-its-item), and the placeholder as a well-known item the seed's `core` layer creates ([§4](#4-the-placeholder-item)). The rest of [Decision](#decision) is a proposal for review, and what is still open is in [Open questions](#open-questions). Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands; the first, [ADR 0191](../adr/0191-inventory-file-format-v1.md), is the format. Row "Importing and exporting an inventory" of [v1.0](../../v1.0.md).

## Context

Two real inventories were looked at while shaping this: a LaTeX list (about 140 lines in eight sections, German and English mixed, counts written in front of names, notes in brackets) and a spreadsheet (99 rows, 14 containers, with weight, value, type and description columns). Both are things a player already has and wants to bring in, and neither is anything Lorenzo can read. What they showed:

- **Lorenzo has the model.** Items, instances with their own names, containers, equipped and not carried, notes, a public catalog players can read, and self-service creation ([RFC 0034](0034-player-self-service.md)). The CLI has `item list`, `item add` and `character list` ([ADR 0190](../adr/0190-lorenzo-item-and-character-commands.md)), written as the groundwork for this.
- **It has no way to say "I do not know what this is yet".** A player can only make instances of public items ([ADR 0186](../adr/0186-player-self-service-enforcement.md)). About a third of both lists is homebrew, one-offs and things in another language, none of it in a catalog. Today that is a dead end, which a bulk import would hit forty times in a row.
- **Sources vary and will keep varying.** A sheet, a LaTeX file, a character sheet, a notes app. A reader for each inside the CLI is a lot of surface; a stable file they all convert into is not.
- **Matching titles is the hard, human part.** "Seil", "rope", "Hemp rope 50 ft" and "Hanfseil 50 ft" are one thing to a person and four to a computer. A GM looking at a list of what is unknown can do that quickly. An importer guessing cannot.

What the code already offers, which this builds on:

- An instance has its own name, a note (an `information` row on the entity, writable by whoever controls the entity), a prototype link written at creation, and a change feed that tells its holders about changes ([ADR 0099](../adr/0099-player-facing-change-feed.md)).
- The pack-list grammar ([ADR 0145](../adr/0145-pack-contents-in-the-description.md)) already reads `- 5 x [Label](slug)` with indentation for "in", in Python, against shared test cases.
- The seed's `core` layer ([ADR 0181](../adr/0181-the-seeds-four-layers-and-a-system-root.md)) creates slugged items through the normal route, though today only as non-public category nodes.

And what it does not offer, found by reading the code and the reason the first slice exists:

- **An instance's prototype cannot be changed.** `PATCH .../item-instances/{id}` takes only `name`; the prototype routes act on items.
- **Instances cannot be listed by item.** The list takes `container_id` and `recursive` only.
- **A note a player writes is invisible to them by default**: a new non-public note has no knowers, and the author is not made one.
- **The seed has no public item and no concept of one**: nodes are made with `in_public_catalog=False`.

## Decision

### 1. The inventory file

One text file, one owner, written by hand or by a script, and written back out by Lorenzo. The full specification is the player-facing [guide](../guides/inventory-file-format.md); the decisions are:

- **Two forms of one model.** A Markdown list (the form people write, a superset of the pack-list grammar) and a JSON twin (for scripts and for `export --json`). Same fields, same meaning.
- **Header, two sections, containers by indentation.** `format: lorenzo-inventory/1` and `owner:` first; `## Equipped` and `## Not carried` (with aliases such as `Holding`, which a spreadsheet already calls it); everything else is a container, written as a line with lines indented under it. A container kept elsewhere is a container under *Not carried* with a `place:`.
- **A line** is `[N x ]Name | field: value | …`. Fields: `ref`, `item`, `weight` (pounds, per piece), `value` (free text), `kind` (a hint), `note`, `place`. All optional. Unknown fields are ignored with a warning.
- **A stack needs a container**, since a count lives on a containment row ([ADR 0140](../adr/0140-a-stack-when-an-item-instance-is-created.md)); a loose count above 1 is reported, never guessed.
- **One owner per file.** The structure leaves room for more later without changing what v1 means.
- **A version line**, and readers ignore what they do not know. The format is meant to outlive any importer.
- **Weight, value, kind and place are kept as a note** on the instance, in a fixed, plain layout (`Weight: 0.04 lb`, one per line). They are for the GM who sorts it, who may make the catalog item from them; they are not a new column.

### 2. Commands

`lorenzo inventory import FILE --tenant T [--owner C] [--dry-run] [--add]` and `lorenzo inventory export --tenant T --owner C [--json]`, in `apps/cli`, built on what `item add` and the API already do, following the importer's habit ([RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md)): a plan first, then apply, and a report of every line that was not what it expected.

- **Create-only.** Import refuses a character that already has things unless `--add`. A line whose `ref` is the id of the owner's own instance does not create but moves it to where the file puts it, which is what makes an export, edited and read back in, work. Nothing else is updated.
- **Equipped** is made as owned-and-not-carried, then picked up with the route that already does it, since creating straight into the hands is a manager's, not self-service's ([ADR 0186](../adr/0186-player-self-service-enforcement.md)).
- **A player or a GM runs it**, with the same standing as `item add`: the API decides, in its own words. A GM may import for any character in their library.

### 3. How a line finds its item

In this order, first hit wins, all case-insensitive and trimmed:

1. `ref` as an **instance id** of the owner's own item
2. `ref` as an **item id**
3. `ref` as a **slug**
4. the name as an **exact title**
5. the name **preprocessed**: when nothing above matched, a table of known translations and spellings (German to English gear names to begin with, singulars, a stripped bracket) produces alternative titles, tried in turn. The table is data kept with the importer and grows as GMs find gaps; it is a step of the importer, not of the API.
6. **nothing: a placeholder** ([§4](#4-the-placeholder-item))

What a caller may match is what they may see: the public catalog for a player, the whole library for a GM. A line with nothing visible to match becomes a placeholder, not an error. Fuzzy matching is deliberately **not** in the importer; it belongs to the GM's view in [§6](#6-the-gms-view), where a person is looking at it.

### 4. The placeholder item

A well-known item in each library: **"Unsorted item", slug `unsorted`**, public, created by the seed's `core` layer. An instance of it is a placeholder:

- **The player's name is on the instance**, the name they wrote.
- **The player's description is the instance's note**, with the details of [§1](#1-the-inventory-file) in a second note. Both readable by the player and the GM.
- **A board badge** marks it as unsorted, so nobody mistakes it for the thing it stands in for.
- **No limit.** If a table is flooded with them, that is something to say at the table.

What this needs and the code lacks, all in the API slice:

- **The seed makes a node public**: a `public = true` on a `[[node]]` (or the layer's equivalent), applied through `ItemCreate`, and the layer's `version` raised. A tenant already seeded gets it by running `lorenzo seed` again (it is idempotent) or by taking the repository's update.
- **No unsorted item in the library** means import stops on the first line that needs one and says what to run, rather than falling back to anything.
- **A note the writer can read.** A note created on an instance by someone who controls it is made visible to the people who control it (the author's own player, and the GM's reach as now), by an API change so the author is a knower, or by the clients granting it. Which, is the first ADR's to decide after a test that shows what actually happens today.

### 5. Sorting one: changing the prototype

A **GM** can change what an instance is: `PATCH .../item-instances/{id}` takes a `prototype_id`, which replaces the instance's prototype link. **The name and notes stay**, which is the point: the player's own words survive being sorted. It is a manager's action (GM or tenant `OWNER`/`ORGA`), is recorded in the activity log, and writes a change-feed entry of a new kind (`sorted`) to the instance's holders, which is how the player is told ([§7](#7-telling-the-player)).

Also in the API: **`GET .../item-instances?prototype_id=`**, so "every unsorted item in the library" is one call, by owner and campaign as the list's visibility rules already narrow it.

The two things a GM does with a placeholder, then, are two uses of what exists: **assign** is a prototype change to an item that already exists; **create from it** is `POST .../items` with the placeholder's name and note, then a prototype change to the new item. **Keep as is** is doing nothing.

### 6. The GM's view

An "Unsorted" view in inventory-web, listing every placeholder in the library: owner, the name they wrote, their note with weight and value, how many. For each: search the catalog and **assign**; **create** a catalog item prefilled from the name, note and details, optionally public; **keep**. With fuzzy search over titles (and over the preprocessing table, so a German name suggests its likely English one) and **bulk actions**, since the same thing is usually unsorted for several players: "assign all 5 'Torch' to Torch". It is a view on one list and the calls above, no new API beyond a bulk convenience if a loop over `PATCH` proves too slow.

### 7. Telling the player

When a GM sorts one, its holders are told: **"Your *Hydra Zahn* is now a *Hydra Tooth*"**. Through the change feed ([ADR 0099](../adr/0099-player-facing-change-feed.md)) rather than the `notification` table: the feed is already written to exactly the people who hold an instance, for every write to it, and read through `GET /me/changes`; the notification table is for a message one person writes to another and would need the recipients worked out again. To confirm with the maintainer, since "use notifications" was said of the system as a whole ([Open questions](#open-questions)).

### 8. "Not in the list" for a player

In inventory-web's *Add an item* card ([ADR 0187](../adr/0187-inventory-web-adding-an-item-to-a-board.md)): when a search finds nothing, an option to add it as an **unsorted item**, with a name, an optional description, weight and value. This removes the dead end players hit today, and is the same placeholder an import makes.

## Slices

1. **The format** (docs): the [guide](../guides/inventory-file-format.md) and [ADR 0191](../adr/0191-inventory-file-format-v1.md). First, so players can start writing files and anyone can write a converter before any of the rest is built.
2. **The placeholder, in the API and the seed** (`apps/api`, `apps/cli`): the seed's public node and the `unsorted` item, the prototype change, the list filter, the `sorted` change-feed kind, the readable note. A contract extension, no tightening. An ADR when it lands.
3. **Import and export** (`apps/cli`): the parsers (Markdown and JSON) against shared test cases in the way the pack lists are, the matching order and its preprocessing table, `inventory import` with plan and apply, `inventory export`. An ADR when it lands.
4. **"Not in the list" and the badge** (`apps/inventory-web`): the add-an-item option and the board badge. An ADR when it lands.
5. **The GM's view** (`apps/inventory-web`): the Unsorted view with fuzzy search and bulk actions. An ADR when it lands.
6. **Converters** (not scoped): CSV first, then LaTeX lists, then whatever is asked for. Where they live, in this repository or not, is decided when the first one is.

## Open questions

- **The notification route**: the change feed in [§7](#7-telling-the-player) or the notification table. The feed is the closer fit and already does the recipients, but "told" may mean something the maintainer wants to see in account-hub's notifications. Settled before slice 2 is built.
- **Who may read a player's note** ([§4](#4-the-placeholder-item)): whether a test shows the author cannot see what they wrote, and which of two fixes is right. Slice 2's first step.
- **The slug.** `unsorted` is the proposal; the maintainer floated `unknown`, `tosort`, `proposed` and `misc`. A library may already have an item with the chosen slug, in which case the seed's rename-or-skip applies. Settled before slice 2.
- **The size of a file** and whether a stack of a hundred should be allowed to be a hundred lines. A limit like the pack-list's is proposed (500 lines) and not decided.
- **What import does with a line that has a `ref` to an instance of another character.** Refused, with the line number, is the proposal.
- **Moving into the hands by id.** `--add` with an instance id that is to be Equipped needs the pick-up route, with its capacity rules ([ADR 0128](../adr/0128-capacity-and-moving-anyway.md)); what happens when it is full is slice 3's to decide.

## Not in scope

- **Converters in this repository**, until slice 6. The format is the contract.
- **Sync.** Import creates and moves; it never renames, edits or deletes what exists.
- **Several owners in one file**, and group inventories, beyond what the structure leaves room for.
- **Fractional counts** (`0.5 m³`, `8.5 barrels`): a note, not a number.
- **Turning a skeleton or a pet into a being.** In v1 everything is an item instance.
- **A limit on placeholders.**

## Alternatives considered

- **Reading each source directly in the CLI.** Many parsers to keep, each guessing. A stable file with converters outside is smaller, and lets players write their own.
- **One format only, JSON or YAML.** JSON is a poor thing to hand to a player; YAML has traps (`no` as false, indentation) a player will meet. The Markdown list is something they can already read and the pack grammar already parses.
- **A tag or flag marking any instance as unsorted**, instead of a placeholder item. A player cannot make catalog items, and a flag on an arbitrary instance needs a prototype anyway.
- **Fuzzy matching in the importer.** Right often enough to be trusted, wrong often enough to hurt. A GM looking at a list is the safer place.
- **A `notification` row for "sorted".** See [§7](#7-telling-the-player).

## Consequences

- A player can bring a whole inventory in with one command, and nothing they wrote is lost for the catalog not knowing it.
- A GM gets a worklist of exactly what the catalog is missing, from the people who have it, with the details to hand.
- The format is a published contract; changing it later costs players their files, which is why it is written down and versioned first.
- The API gains a manager's prototype change, a list filter and a change-feed kind; no new table, so [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)'s RLS and [ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md)'s same-tenant keys are untouched.
- The seed's `core` layer gets its first public item and a version bump, so tenants take it when they next seed or update.
