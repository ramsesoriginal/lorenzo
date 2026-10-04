# RFC: Item repositories — a common vocabulary, common equipment, a rules repository, and the bridge

Status: proposed. The maintainer decided its shape on 2026-10-04 ([Decided](#decided-with-the-maintainer-2026-10-04)); two small questions remain ([Open](#open-questions)). Written at the maintainer's request after the first real import. It would amend [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) if accepted, and it is meant to be accepted before anything is published or granted.

## Context

[RFC 0024](0024-repositories.md) §5 and §9 designed repositories to be combined: a *content* repository (Faerûn), a *system* repository (D&D 5e), and a *bridge* (`dnd_faerun`) that holds copies of both and authors "Blackstaff (D&D 5e)" with a parent in each. [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md) built it. [RFC 0001](0001-core-domain-data-model.md)'s open question 3 guessed the same for items, as RFC 0024's context recounts: a system-neutral "Sword" with "Sword (D&D 5e)" variants inheriting from it.

[ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) applied it to the equipment seed in a smaller form: two repositories.

- **`core`** holds the neutral vocabulary and no items: the category tree (weapon, ranged weapon, crossbow, armour, kinds of gear), the stat groups and definitions, and the weight recipe.
- **`dnd5e`** is a bridge over it. It holds the D&D layer (proficiency, tier and property categories, the dice and flag stats) **and every imported item**, each with its neutral and its D&D facts together.

It named a third option and left it out: "a third repository, for items only", out of scope because it cost three grants instead of two. That reason is weaker since [`repo offer`](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md) grants and copies a whole stack.

The maintainer's picture, for the equipment seed, was three repositories:

- **Common Fantasy Equipment:** the items with their descriptions, the obvious physical facts (weight, is a container, certain tags), and the logical hierarchy ("a heavy crossbow is a crossbow, a crossbow is a ranged weapon, a ranged weapon is a weapon, and it is heavy"). Later, beings (race, class) would join it.
- **Dungeons & Dragons 5e:** the mechanical stat groups, the keyword tags (versatile, loading), the economic cost in copper coin, and the prototypes that apply them (a "versatile" prototype that applies the versatile stat).
- **Common items in D&D 5e:** a bridge over both, that gives the common items the D&D prototypes, the D&D prices, and the values of the mechanical stats.

The first of those has since been split in two, the vocabulary apart from the items, which makes four repositories (section 1). A Pathfinder table would take the common vocabulary and equipment, a Pathfinder rules repository and a Pathfinder bridge. A Warhammer table with items of its own would take the vocabulary alone.

### What this builds on

- **A bridge carries only what it authored.** Its edits to its copies of a dependency don't travel downstream, so a bridge can't change a dependency's Longsword. It authors a new entity that inherits from it ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md), RFC 0024 A8).
- **Descriptions and pictures accumulate down the prototype chain**, each labelled with where it came from ("From Longsword"). A title doesn't inherit: an item's displayed title is its own description's title, else its own name ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md), [0067](../adr/0067-item-title-falls-back-to-name.md)).
- **A stat value resolves through the prototypes**, and a value on the entity itself beats an inherited one ([ADR 0037](../adr/0037-effective-stat-resolution.md)).
- **Stat groups and definitions can't be renamed or retyped, and can only be deleted while unused** ([ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)). Which repository defines which one has to be right before anything is published.
- **The API reads some stat names**: `weight`, `size`, `is_container`, and the named `price` and `armor` columns on an item ([well-known stats](../reference/well-known-stats.md)). A tenant that defines one gets the behaviour.
- **A merged stat group or definition counts downstream as a copy of the origin it was merged with** ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)).
- **Grants aren't transitive**, and `lorenzo repo offer` follows a bridge's manifest ([ADR 0163](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md)).

## What was tried

The part of the picture that wasn't known to work, a bridge over repositories that are themselves bridges over a shared dependency, was run against the real API on 2026-10-04 as scratch end-to-end tests that are not committed. A first run used three repositories and a second the four of this proposal: **A0** seeded with the core layer; **A1** a copy of A0 with one item, "Longsword (common)", given a weight and a description; **B** a copy of A0 seeded with the D&D layer; **C** a copy of A1 and B, which authored a second entity, "Longsword", with parents A1's Longsword and B's Martial weapon and Versatile categories, plus a price and two dice stats of its own; and a play tenant that took C.

- **`repo offer` follows the diamond.** C's first offer, from A1, granted A0 and A1 and copied them in that order. Its second, from B, found A0 "already copied there" and copied only B's own rows, 28 entities and 22 stat definitions. A0 is in C once, although A1 and B both build on it.
- **One offer brings a table the whole stack.** `lorenzo repo offer` to the play tenant granted C's three dependencies and C, then copied A0, A1, B and C in that order. The copy plan lists those four steps.
- **The parents are re-targeted onto the table's own copies.** The table's D&D sword has the parents "Longsword (common)", Martial weapon and Versatile, and the first *is* the table's copy of A1's item: one of it, not two.
- **Nothing is duplicated.** The table has six stat groups and forty stat definitions, each once, though A0's groups reach it through both A1 and B.
- **Neutral facts arrive by inheritance.** The sword's weight is A1's, through A0's weight recipe. Its price and dice are its own. The Versatile tag is inherited from B's category.
- **Descriptions accumulate.** The sword's description list holds A1's text labelled "From Longsword (common)" and B's rules text labelled "From Versatile". The sword had no description of its own, so its title was its own name, "Longsword".
- **Both are listed.** A search for "Longsword" in the table finds "Longsword (common)" and "Longsword". The first run named both items "Longsword", which the API accepted, so the two were indistinguishable in a list. That is why the naming decision below matters.
- **`repo contents` reads the stack.** For C it lists the three repositories it is built on and the seed layers it holds, which is what ADR 0169's view was for.

Not tried: corrections travelling through the levels, and the importer writing the two halves.

## Proposal

### 1. Four repositories, by what is true of what

| Repository | Holds | Its authors answer |
| --- | --- | --- |
| **A0, common vocabulary** | The vocabulary seeded today as `core`: the category tree, the stat groups and ten stat definitions (weight, the container, consumable, magical and material tags, the citation), and the weight recipe. **No items.** | What can be said of a thing, anywhere? |
| **A1, common equipment** | A bridge over A0. The **neutral items**: name, aliases, weight, the forms and materials they are, whether they hold things, the sourcebook citation, and every description that isn't tied to a mechanic. | What is this thing, anywhere? |
| **B, D&D 5e** | A bridge over A0: it copies A0, then the D&D layer on top. Every stat of the D&D layer (dice, damage type, attack ability, the property flags) and the other D&D stats listed in section 4 (price in copper, armour, strength required, ranges), and the proficiency, tier and property categories with their rules text. | How does D&D 5e treat things? |
| **C, common items in D&D 5e** | A bridge over A1 and B (and so A0). **No vocabulary of its own.** One entity per D&D item: parents are A1's item and B's categories, and it carries the D&D values (price, dice, armour, strength required) and the sheet's rules text. Packs. | What is this thing in D&D 5e? |

B is a bridge over A0 because the D&D stats go into groups (`damaging`, `tags`) that A0 creates, as `dnd5e` over `core` does today ([RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R9 has the core layer create all five conventional groups, so two systems never collide on creating one). B could instead copy nothing and define its own groups, leaving C to merge the same-named ones when it copies both ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md) allows a merge). That hasn't been tried, and it makes the merge a decision at every copy.

A1 and B both build on A0, so C's dependencies form a diamond. "What was tried" shows ADR 0120's manifest handles it: A0 is copied once.

### 2. How an item is built

```text
A1  Longsword (common)  parents: blade, melee-weapon      own_weight 3     (aliases, prose)
B   Martial weapon      (category)                        Versatile        (category, tag, rules text)
C   Longsword           parents: A1's Longsword (common), B's Martial weapon, B's Versatile
                        own: price 1500, damage_dice_count 1, damage_die 8, damage_versatile_die 10
```

C's entity never edits A1's. A table sees the D&D item with A1's weight and text and B's rules text by inheritance, and C's values on top.

### 3. Authoring rules

- **C authors, it never edits.** Anything C wants to differ from A1 it says on its own entity, as ADR 0120 already requires.
- **A1's items are prototypes, and say so in their names.** Each carries the suffix " (common)": "Longsword (common)". C's items carry the plain name, which is what a table's players see. The title follows, since an item's title is its own description's title or its name ([ADR 0067](../adr/0067-item-title-falls-back-to-name.md)), and the importer titles a description with the item's name ([ADR 0165](../adr/0165-a-description-is-titled-with-its-items-name.md)).
- **A1's items are not public.** They are authored with `in_public_catalog` false, which is what the importer does unless it is told `--public-catalog`, and C's import is told. A player lists only public items ([ADR 0116](../adr/0116-players-read-catalog-items-and-a-public-catalog.md)) and a copy keeps the flag as its author set it (RFC 0024), so a table's players see the D&D items and not the neutral ones. A GM lists the whole catalog and sees both, told apart by the suffix, and can narrow it with the existing `prototype_id` filter ([ADR 0073](../adr/0073-item-prototype-graph-inspection-and-bulk-editing.md)): "everything built on Martial weapon" is C's.
- **Slugs name the repository.** They are already `<namespace>-<list>-<key>`; A1 and C take different namespaces (`basic-` and a D&D one), so a slug says whose entity it is.

### 4. The stat vocabulary

Today all eighteen definitions of the core layer would go to A0. With D&D pulled out into B, eight of them are D&D's, and so are the twenty-two the D&D layer already has:

| Where | Definitions |
| --- | --- |
| **A0** (ten) | `own_weight`, `weight`, `contents_weight`, `bundle_amount`, `is_container`, `is_consumable`, `is_magical`, `is_silvered`, `is_adamantine`, `sourcebook` |
| **B** (thirty) | the twenty-two of the D&D layer, and `price`, `armor`, `armor_formula`, `strength_required`, `stealth_disadvantage`, `adds_modifier`, `range_normal`, `range_long` |

A0 still creates all five conventional stat groups, so `economic`, `destroyable` and `damaging` exist in A0 with no definitions of their own, and B's go into them (RFC 0025 R9). Moving a definition is a change to the seed's layer tags (the seed's `layer` key exists for this) and a new seed version. Nothing is published, so it costs nothing now; after a publish a definition can't be moved, only added.

### 5. The importer writes two halves

An MPMB sheet is D&D data. The importer has to split what it reads into what is true anywhere (name, aliases, weight, forms, materials, whether it contains things, the sourcebook citation, descriptive text) and what is D&D's (price, dice, armour and range numbers, proficiency, properties, rules text). In the sheet's own fields that is: `nameAlt` and `alternatives` (aliases), prose descriptions of gear, and `sourcebook` for A1; a weapon's `description`, which lists its properties and gives the versatile die, its `tooltip` of special rules, and the numbers, for C. It does this as **two passes over the same files**, so each repository's content is a function of the source and a map, and either can be re-run:

- a neutral pass into A1, creating the item under its forms, with the " (common)" suffix on its name;
- a D&D pass into C, which finds A1's item by its slug **in C's own copy of A1** (as it finds a core category in the bridge today), creates the D&D entity beside it, and parents it in both.

Identity stays the slug, so a second run finds what the first made. The built-in map's rows gain a `part` (neutral or system). That is a slice of its own, with its own ADR.

### 6. Setting it up, and what a table does

```bash
# A0, the vocabulary
lorenzo tenant create "Common vocabulary" --slug common-vocabulary
lorenzo seed --tenant common-vocabulary --layer core --yes
lorenzo repo publish --tenant common-vocabulary

# A1: a bridge over A0, with the neutral items
lorenzo tenant create "Common Fantasy Equipment" --slug common-equipment
lorenzo repo offer common-equipment --tenant common-vocabulary --yes
lorenzo apply --tenant common-equipment --part neutral --base ... --yes   # --part is proposed
lorenzo repo publish --tenant common-equipment

# B: a bridge over A0, with the D&D layer
lorenzo tenant create "Dungeons & Dragons 5e" --slug dnd5e
lorenzo repo offer dnd5e --tenant common-vocabulary --yes
lorenzo seed --tenant dnd5e --layer dnd5e --yes
lorenzo repo publish --tenant dnd5e

# C: a bridge over A1 and B
lorenzo tenant create "Common items in D&D 5e" --slug dnd5e-common-items
lorenzo repo offer dnd5e-common-items --tenant common-equipment --yes
lorenzo repo offer dnd5e-common-items --tenant dnd5e --yes
lorenzo apply --tenant dnd5e-common-items --part system --public-catalog --base ... --yes
lorenzo repo publish --tenant dnd5e-common-items

# A table: grants on all four, and one copy
lorenzo repo offer my-table --tenant dnd5e-common-items --yes
```

Seventeen commands, each already built except for the proposed `--part`. A single setup command is a separate, later question.

### 7. Corrections

A table takes each repository's updates from that repository ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)), as [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)'s four steps already assume. A correction to A0 is published once, and a table takes it from A0. A1's, B's and C's authors re-sync A0 to keep their own copies current. Whether a bridge must also publish again for a table to see anything is the part of ADR 0162's steps that more levels would test, and it hasn't been tried.

## What it costs

- **Two entities per D&D item** in a table's catalog, which is what multiple inheritance makes of "the same sword, in a system". A search finds both; the player-facing one is C's.
- **Four grants and a longer chain of authors.** `repo offer` takes the work out of the grants. The chain is A0, then A1 and B, then C, and each is published by whoever owns it.
- **The importer becomes two passes**, and its map gains a notion of which half a value belongs to.
- **Pre-1.0 churn in the seed.** Moving definitions between layers changes `builtin.toml`, its version, and the README's counts.

What it buys: a second system takes A0 and A1 and brings its own B and C, without D&D's stats or prices in its repositories; one with items of its own takes only A0; the rules and the items can be published, owned and licensed on their own; and the neutral facts of a thing are written once.

## Alternatives

- **Keep ADR 0162's two repositories.** Nothing to build. Neutral and D&D facts stay mixed in every item, and a second system re-imports its own items.
- **Three repositories, items stay D&D's.** Core as vocabulary, a rules repository (B), and a bridge (C) whose items are complete D&D items with parents in both layers. No neutral items, so no second entity per item and one importer pass. It separates the rules from the items, which move at different speeds. It gives up reuse of items across systems. It is the cheapest first step, and it can grow into the proposal later by adding the neutral items and re-parenting C's onto them, but every subscriber then takes that as an update, which is the cost [RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R8 named for splitting late.
- **The vocabulary and the neutral items in one repository** (the first version of this RFC). One repository and one grant fewer, and a system that wants the vocabulary without these items carries them anyway. Splitting costs nothing while nothing is published, which is why it was chosen.

## Decided with the maintainer (2026-10-04)

- **What text lives in A1:** every description that isn't tied to a mechanic. The sheet has little of it for weapons, whose `description` is a property list and whose `tooltip` is special rules (both C's), so most of A1's descriptive text will be written rather than imported. Gear text and aliases are A1's.
- **Which stat definitions are D&D's:** section 4. `sourcebook` is common.
- **Nothing is published or granted.** There is only local test data, so nothing has to be migrated. The local `core` and `dnd5e` tenants can be rebuilt, and no order of work has to protect a subscriber.
- **What the neutral item is called beside the D&D one:** a suffix on the neutral item's name, "Longsword (common)". The D&D item keeps the plain name that players see.
- **The vocabulary and the neutral items are two repositories**, A0 and A1.

## Open questions

1. **Which items do packs link to?** A pack is D&D (an Explorer's Pack has D&D contents, and `pack give` makes the table's items), so it lives in C and links C's entities. Confirm.
2. **Names.** The four repositories' names and slugs are the maintainer's. "Common Fantasy Equipment" is the maintainer's for A1; "Common vocabulary" for A0 is a placeholder.

## Slices, if accepted

Each its own ADR, in this order:

1. **The seed's layers.** Sort the stat definitions (section 4), decide where each category and definition lives, bump the seed version, and extend `tests/e2e/test_split.py` to the four-repository stack that was tried here.
2. **The importer's two passes**, the `part` in its map, and the " (common)" suffix.
3. **Rebuilding the local tenants**, and the setup walkthrough in the README.
4. **Later:** a single setup command, and showing on a table's item which repository each part of it came from.

## Not in scope

- **Beings** (race, class). They would join the common repositories and a rules repository the same way, and they are a later question.
- **Settings.** A setting such as Faerûn is the same pattern on another axis (RFC 0024's own example) and isn't touched.
- **Live reads and edits through a bridge.** ADR 0120's rule that a bridge's edits to its copies don't travel stays.
- **What the SRD's licence allows** for text in a published repository. It is worth checking before anything is published, and it isn't decided here.
