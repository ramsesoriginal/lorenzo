# RFC: Item repositories — a shared vocabulary, common equipment, a rules repository, and a bridge that attaches the rules to the equipment

Status: proposed. The maintainer decided its shape on 2026-10-04 ([Decided](#decided-with-the-maintainer-2026-10-04)); two small questions remain ([Open](#open-questions)). Written at the maintainer's request after the first real import. It would amend [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md), and it needs one change to the repository API ([§3](#3-attachments-the-api-change)). It is meant to be accepted before anything is published or granted.

## Context

[RFC 0024](0024-repositories.md) §5 and §9 designed repositories to be combined: a *content* repository (Faerûn), a *system* repository (D&D 5e), and a *bridge* (`dnd_faerun`) that holds copies of both and authors "Blackstaff (D&D 5e)" with a parent in each. [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md) built it. [RFC 0001](0001-core-domain-data-model.md)'s open question 3 guessed the same for items, as RFC 0024's context recounts: a system-neutral "Sword" with "Sword (D&D 5e)" variants inheriting from it.

[ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) applied it to the equipment seed in a smaller form: two repositories.

- **`core`** holds the neutral vocabulary and no items: the category tree (weapon, ranged weapon, crossbow, armour, kinds of gear), the stat groups and definitions, and the weight recipe.
- **`dnd5e`** is a bridge over it. It holds the D&D layer (proficiency, tier and property categories, the dice and flag stats) **and every imported item**, each with its neutral and its D&D facts together.

It named a third option and left it out: "a third repository, for items only", out of scope because it cost three grants instead of two. That reason is weaker since [`repo offer`](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md) grants and copies a whole stack.

The maintainer's picture, for the equipment seed, started as three repositories: the common equipment, the D&D rules (the mechanical stat groups, the keyword tags such as versatile and loading, the economic cost in copper, and the prototypes that apply them), and a bridge between them. Two refinements followed. The vocabulary is its own repository, apart from the equipment. And the bridge should not create a second set of items: a tenant that subscribes to the common equipment has everything usable, and later subscribing to the bridge, which pulls in the rules, **adds the D&D stats and prototypes to the items the tenant already has**.

### What this builds on

- **A bridge carries only what it authored.** Its edits to its copies of a dependency don't travel downstream. ADR 0120 lists two things a bridge doesn't carry: "its edits to its copies of its dependencies" and "rows between two copied entities", and says "to make an upstream entity behave differently under a system, the bridge authors a new entity that inherits from it" (RFC 0024 A8). This RFC changes that for one kind of row.
- **Copying works on a repository's *own* rows**, those that aren't themselves copies, and re-targets every reference onto the subscriber's copy through the *origin* the two copies share ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md), [0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)). An `entity_prototype` edge belongs to its child. A row whose target the subscriber lacks is dropped, and the copy reports it.
- **Updates already merge an entity's prototype set element by element**, and take a repository's later additions as "added" rows ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).
- **Descriptions and pictures accumulate down the prototype chain**, each labelled with where it came from ("From Longsword"). A title doesn't inherit ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md), [0067](../adr/0067-item-title-falls-back-to-name.md)).
- **A stat value resolves through the prototypes**, and a value on the entity itself beats an inherited one ([ADR 0037](../adr/0037-effective-stat-resolution.md)).
- **Stat groups and definitions can't be renamed or retyped, and can only be deleted while unused** ([ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)). Which repository defines which one has to be right before anything is published.
- **The API reads some stat names**: `weight`, `size`, `is_container`, and the named `price` and `armor` columns on an item ([well-known stats](../reference/well-known-stats.md)).
- **Grants aren't transitive**, and `lorenzo repo offer` follows a bridge's manifest ([ADR 0163](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md)).

## What was tried

Three things were run against the real API on 2026-10-04, as scratch end-to-end tests that are not committed.

**A bridge over repositories that share a dependency.** **A0** was seeded with the core layer; **A1** copied A0 and got one item, "Longsword", with a weight and a description; **B** copied A0 and was seeded with the D&D layer; **C** copied A1 and B; a play tenant took C.

- **`repo offer` follows the diamond.** C's first offer, from A1, granted A0 and A1 and copied them in that order. Its second, from B, found A0 "already copied there" and copied only B's own rows. A0 is in C once.
- **One offer brings a table the whole stack**: it granted C's three dependencies and C, then copied A0, A1, B and C in order. The copy plan lists those four steps.
- **Nothing is duplicated.** The table had six stat groups and forty stat definitions, each once.
- **The `repo contents` view reads the stack**: for C it lists the three repositories it is built on.

**A bridge that derives.** C authored a second entity, "Longsword", with parents A1's Longsword and B's categories, plus a price and dice. The table's copy of it had A1's item as a parent (one of it, not two), A1's weight by inheritance, and A1's and B's descriptions labelled "From Longsword" and "From Versatile". A search found two items. The API accepted two entities with the same name in one tenant, so they were indistinguishable in a list. This is the design this RFC replaces.

**A bridge that attaches.** C gave its copy of A1's Longsword an extra parent, a new item "Longsword (D&D 5e)" holding a price and dice with B's Martial weapon and Versatile as parents, and a stat value directly on the copy. In C the sword showed the price through the new parent. A table that already held A1 then took C. Its copy plan listed A0 and A1 as already copied and B and C as new. The new prototype arrived and was attached to nothing; **the table's Longsword kept its two parents and gained no stat**, and nothing said so. That is ADR 0120's rule, working as written.

Not tried: attachments that travel (they don't exist yet), corrections through the levels, and the importer writing the two halves.

## Proposal

### 1. Four repositories

The maintainer's names and slugs; "depends on" means holds a copy of.

| Repository (slug) | Depends on | Holds | Its authors answer |
| --- | --- | --- | --- |
| **A0, Core** (`core`) | nothing | The vocabulary seeded today as `core`: the category tree, the stat groups and ten stat definitions (weight, the container, consumable, magical and material tags, the citation), and the weight recipe. **No items.** | What can be said of a thing, anywhere? |
| **A1, Common Fantasy Equipment** (`common-fantasy-eq`) | A0 | The **items**, usable on their own and public: name, aliases, weight, the forms and materials they are, whether they hold things, the sourcebook citation, and every description that isn't tied to a mechanic. | What is this thing, anywhere? |
| **B, Dungeons and Dragons 5e** (`dnd5e`) | A0 | A copy of A0, then the D&D layer on top. Every stat of the D&D layer and the other D&D stats listed in section 5 (price in copper, armour, strength required, ranges), and the proficiency, tier and property categories with their rules text. | How does D&D 5e treat things? |
| **C, Common D&D5e Equipment** (`dnd5e-common-eq`) | A1 and B | **No vocabulary of its own, and no second set of items.** One *D&D prototype* per item with D&D facts, and an *attachment* that gives A1's item that prototype as a parent. Packs. | What is this thing in D&D 5e? |

B depends on A0 because the D&D stats go into groups (`damaging`, `tags`) that A0 creates, as `dnd5e` over `core` does today ([RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R9 has the core layer create all five conventional groups). A1 and B both build on A0, so C's dependencies form a diamond; "What was tried" shows ADR 0120's manifest handles it.

### 2. How an item is built

```text
A1  Longsword           public    parents: blade, melee-weapon       own_weight 3        (usable on its own)
B   Martial weapon      category                                     Versatile           (category, tag, rules text)
C   Longsword (D&D 5e)  not public  parents: B's Martial weapon, B's Versatile
                                    own: price 1500, damage_dice_count 1, damage_die 8, damage_versatile_die 10, rules text
C   attachment:  A1's Longsword  ->  C's "Longsword (D&D 5e)"        (one more parent of A1's item)
```

A table that holds only A1 has a Longsword with a weight and a description. When it takes C, **the same Longsword** gains the D&D prototype as a parent, and with it the price, the dice, B's categories and B's rules text, by inheritance. There is one Longsword in the table, a GM's catalog lists the D&D prototype as a non-public item (as it does the categories), and no suffix is needed on any name. Another system's bridge attaches its own prototype beside it.

### 3. Attachments: the API change

**Definition.** An *attachment* is an `entity_prototype` edge in a repository whose **child is a copy** (an entity the repository holds because it copied another repository) and whose **parent is the repository's own entity**. Authors make one with what exists: `PUT /tenants/{id}/items/{entity_id}/prototypes` on the copy, which was run in "What was tried" and answers `200`. The only new thing is what a copy does with it.

**Why this and not more.** The edge is unambiguously the bridge's: a parent that is the bridge's own entity cannot have arrived with a copy, so nothing about whose edge it is needs guessing. An edge between two copies is not carried, as ADR 0120 says, because it could be either the bridge's or an upstream's own. A stat value or a name or a description written onto a copy is not carried either. Facts the bridge wants to add belong on its own prototype, where they are inherited.

**In a copy** ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)):

- For each attachment of the repository it is copying, the plan finds the subscriber's local copy of the child through the origin both copies share, finds the local copy of the parent among the rows it is copying, and writes the edge between them.
- The subscriber's copy of the child is already there when it took the dependency first. When it takes the bridge first, the manifest copies the dependency before it ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)), so it is there either way.
- If the subscriber has no copy of the child (it skipped the dependency's row, or deleted it), that one attachment is **dropped and reported**, like any row whose target is missing. If the edge would make a prototype loop, it is dropped with that reason, as an update already does.
- Plans and copy responses count attachments beside entities, stat groups, stat definitions and information, so a dry run shows them.

**Provenance.** A new copy-link table records each attachment a tenant took (the repository, the child's origin, the parent's origin), with the tenant's RLS like the other three. Without it a later removal could not be told from an edge the tenant added itself. It is bookkeeping, not repository content, so it goes in the "not content" list of `repository_access` (ADR 0118).

**In updates** ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)):

- An attachment the bridge adds later is an *added* row, applied like one.
- One it removes is a *removed* row, with ADR 0121's existing choices.
- One the tenant removed locally is *deleted locally*.
- The tenant's own extra parents on an item stay, since the prototype set already merges element by element.

**Purging a copy** (ADR 0119) already counts "an edge from its own entity to a copied one" under `also_removed`. Attachments taken from a repository go with it, and are counted.

**What does not change.** Edits to copies other than these edges still don't travel. A bridge still can't change a dependency's item. Nothing flows live: the attachments reach a tenant by copy or by `repo updates`, when the tenant chooses, so RFC 0024's "curated, reviewed composition over live pass-through" holds. The change is to ADR 0119, 0120 and 0121 and to RFC 0024 A8's list of what a bridge carries.

**One limit it has.** A value on the item itself beats an inherited one, so a D&D prototype cannot override a stat that A1's item sets directly. The ten stats in A0 are the neutral ones, and every D&D stat is defined in B, so only a case where D&D wants a different weight for an item runs into it.

### 4. Authoring rules

- **A1's items are public and plain-named.** They are authored with `in_public_catalog` true (`--public-catalog` on the neutral pass), so a tenant that holds only A1 has usable items, and a player lists them.
- **C's prototypes are not public.** They are authored with `in_public_catalog` false, which is what the importer does by default, so players don't list them. A GM sees them in the whole catalog, and can narrow with the existing `prototype_id` filter ([ADR 0073](../adr/0073-item-prototype-graph-inspection-and-bulk-editing.md)): "everything built on Martial weapon" is C's.
- **C never edits A1's items.** It adds a prototype and an attachment. Slugs name the repository: A1's items use the `basic-` namespace and C's prototypes a D&D one (`srd5e-weapons-longsword`).
- **Packs are C's own items**, an Explorer's Pack being D&D content, and they link A1's items, so `pack give` gives the real items, with the D&D facts the table has attached.

### 5. The stat vocabulary

Today all eighteen definitions of the core layer would go to A0. With D&D pulled out into B, eight of them are D&D's, and so are the twenty-two the D&D layer already has:

| Where | Definitions |
| --- | --- |
| **A0** (ten) | `own_weight`, `weight`, `contents_weight`, `bundle_amount`, `is_container`, `is_consumable`, `is_magical`, `is_silvered`, `is_adamantine`, `sourcebook` |
| **B** (thirty) | the twenty-two of the D&D layer, and `price`, `armor`, `armor_formula`, `strength_required`, `stealth_disadvantage`, `adds_modifier`, `range_normal`, `range_long` |

A0 still creates all five conventional stat groups, so `economic`, `destroyable` and `damaging` exist in A0 with no definitions of their own, and B's go into them (RFC 0025 R9). Moving a definition is a change to the seed's layer tags (the seed's `layer` key exists for this) and a new seed version. Nothing is published, so it costs nothing now; after a publish a definition can't be moved, only added.

### 6. The importer writes two halves

An MPMB sheet is D&D data. The importer has to split what it reads into what is true anywhere (name, aliases, weight, forms, materials, whether it contains things, the sourcebook citation, descriptive text) and what is D&D's (price, dice, armour and range numbers, proficiency, properties, rules text). In the sheet's own fields that is: `nameAlt` and `alternatives` (aliases), prose descriptions of gear, and `sourcebook` for A1; a weapon's `description`, which lists its properties and gives the versatile die, its `tooltip` of special rules, and the numbers, for C. It does this as **two passes over the same files**, so each repository's content is a function of the source and a map, and either can be re-run:

- a neutral pass into A1, creating the item under its forms, public;
- a D&D pass into C, which finds A1's item by its slug **in C's own copy of A1** (as it finds a core category in the bridge today), creates the D&D prototype under B's categories with the D&D values, and **appends the prototype to the item's parents** if it isn't there yet.

Identity stays the slug, so a second run finds what the first made and attaches nothing twice. The built-in map's rows gain a `part` (neutral or system). That is a slice of its own, with its own ADR.

### 7. Setting it up, and what a table does

```bash
# A0
lorenzo tenant create "Core" --slug core
lorenzo seed --tenant core --layer core --yes
lorenzo repo publish --tenant core

# A1: a copy of A0, with the neutral items, public
lorenzo tenant create "Common Fantasy Equipment" --slug common-fantasy-eq
lorenzo repo offer common-fantasy-eq --tenant core --yes
lorenzo apply --tenant common-fantasy-eq --part neutral --public-catalog --base ... --yes   # --part is proposed
lorenzo repo publish --tenant common-fantasy-eq

# B: a copy of A0, with the D&D layer
lorenzo tenant create "Dungeons and Dragons 5e" --slug dnd5e
lorenzo repo offer dnd5e --tenant core --yes
lorenzo seed --tenant dnd5e --layer dnd5e --yes
lorenzo repo publish --tenant dnd5e

# C: copies of A1 and B, then the D&D prototypes and their attachments
lorenzo tenant create "Common D&D5e Equipment" --slug dnd5e-common-eq
lorenzo repo offer dnd5e-common-eq --tenant common-fantasy-eq --yes
lorenzo repo offer dnd5e-common-eq --tenant dnd5e --yes
lorenzo apply --tenant dnd5e-common-eq --part system --base ... --yes
lorenzo repo publish --tenant dnd5e-common-eq

# A table: the equipment alone is usable...
lorenzo repo offer my-table --tenant common-fantasy-eq --yes
# ...and later, D&D is added to the items it already has
lorenzo repo offer my-table --tenant dnd5e-common-eq --yes
```

Sixteen commands to build the four repositories, then one to use the equipment and one to add D&D to it, each already built except for the proposed `--part` and the attachments in `copy`. A single setup command is a separate, later question.

### 8. Corrections

A table takes each repository's updates from that repository, as [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)'s four steps already assume. A correction to A1's item is published once and a table takes it from A1. A new attachment in C reaches a table as an added row. A1's, B's and C's authors re-sync their dependencies to keep their own copies current. Whether a bridge must also publish again for a table to see anything is the part of ADR 0162's steps that more levels would test, and it hasn't been tried.

## What it costs

- **An API change**, in the copy planner, the updates diff and apply, purge, one new table and its migration, the plan and copy response fields, and the tests that go with them. It is bounded: one kind of row, one rule for whose it is, and the existing machinery for re-targeting, dropping and updating.
- **Four grants and a longer chain of authors.** `repo offer` takes the work out of the grants. The chain is A0, then A1 and B, then C.
- **The importer becomes two passes**, and its map gains a notion of which half a value belongs to.
- **Pre-1.0 churn in the seed.** Moving definitions between layers changes `builtin.toml`, its version, and the README's counts.
- **No way to take D&D back off**, the same as any copy today ("what they already copied stays theirs"). A tenant that wants to undo C removes the attachments itself. A command for it is a later question.

What it buys: one item per thing in a table, usable from A1 alone and enriched by C when the tenant wants it; a second system takes A0 and A1 and brings its own B and C, each attaching its own prototype beside the others; the rules and the items can be published, owned and licensed on their own; and the neutral facts of a thing are written once.

## Alternatives

- **C derives instead of attaching** (the earlier version of this RFC). C authors a second, playable entity per item with the neutral item as a parent. It needs no API change and works today, and it leaves two entities per D&D item in a table, told apart by a suffix on the neutral one. It is the fallback if the API change is not wanted.
- **An attach step in the CLI.** C carries the prototypes and a list of which items each applies to, and a command adds the parents in the tenant after a copy. No API change, but the attachments are not part of the copy, `repo updates` doesn't know of them, and the step has to be run. The API route's data and the CLI's could be the same, so it is not a dead end, but it is not clean.
- **Writing stat values straight onto a dependency's items.** Rejected: two systems would write the same stat onto one item and collide, nothing would say where a value came from, and a tenant could not remove it. A prototype per system avoids all three.
- **Keep ADR 0162's two repositories**, or **three, with items staying D&D's.** Nothing to build, and neutral and D&D facts stay mixed in every item, so a second system re-imports its own items.
- **The vocabulary and the neutral items in one repository.** One repository and one grant fewer, and a system that wants the vocabulary without these items carries them anyway. Splitting costs nothing while nothing is published.

## Decided with the maintainer (2026-10-04)

- **What text lives in A1:** every description that isn't tied to a mechanic. The sheet has little of it for weapons, whose `description` is a property list and whose `tooltip` is special rules (both C's), so most of A1's descriptive text will be written rather than imported. Gear text and aliases are A1's.
- **Which stat definitions are D&D's:** section 5. `sourcebook` is common.
- **Nothing is published or granted.** There is only local test data, so nothing has to be migrated. The local `core` and `dnd5e` tenants can be rebuilt.
- **The vocabulary and the equipment are two repositories**, A0 and A1.
- **The names and slugs** of section 1, as the maintainer proposed them.
- **C attaches to A1's items instead of deriving from them**, through the API, so that a tenant that holds A1 gets D&D added to its existing items. This supersedes the " (common)" suffix on the neutral items and the non-public neutral items of the earlier version.

## Open questions

1. **Which items do packs link to?** A pack is D&D content and lives in C as an own item, and links A1's items. Confirm.
2. **May an attachment's parent be another repository's copy?** This RFC allows only the bridge's own entity, so C needs a prototype per item even for an item that only needs B's categories, as a prototype with no stats of its own. Allowing "A1's Longsword gets B's Martial weapon as a parent" directly would save those prototypes, but an edge between two copies can't be told from one that came with a dependency without comparing against the dependency. Recommended: own parents only.

## Slices, if accepted

Each its own ADR, in this order:

1. **Attachments in copy and updates** (section 3): the rule, the copy-link table and migration, the planner, `repo updates`, purge, the response fields, and an end-to-end test of the stack tried here with a table that takes A1 first and C later. It amends ADR 0119, 0120, 0121 and RFC 0024 A8.
2. **The seed's layers.** Sort the stat definitions (section 5), bump the seed version, and extend `tests/e2e/test_split.py` to the four-repository stack.
3. **The importer's two passes** and the `part` in its map, and `repo contents` counting a repository's attachments.
4. **Rebuilding the local tenants**, and the setup walkthrough in the README.
5. **Later:** a single setup command, a command that takes an attached repository back off a tenant, and showing on a table's item which repository each part of it came from.

## Not in scope

- **Beings** (race, class). They would join the common repositories and a rules repository the same way, and they are a later question.
- **Settings.** A setting such as Faerûn is the same pattern on another axis (RFC 0024's own example) and isn't touched.
- **Live reads of a dependency.** Attachments travel by copy and by updates, never live.
- **Carrying stat values, names or descriptions written onto a copy.** Only the edge to the bridge's own entity travels.
- **What the SRD's licence allows** for text in a published repository. It is worth checking before anything is published, and it isn't decided here.
