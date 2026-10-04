# RFC: Item repositories — common equipment, a rules repository, and the bridge between them

Status: proposed. The maintainer answered three of its questions on 2026-10-04 ([Decided](#decided-with-the-maintainer-2026-10-04)); the [open ones](#open-questions) remain. Written at the maintainer's request after the first real import. It would amend [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) if accepted, and it is meant to be decided before anything is published or granted.

## Context

[RFC 0024](0024-repositories.md) §5 and §9 designed repositories to be combined: a *content* repository (Faerûn), a *system* repository (D&D 5e), and a *bridge* (`dnd_faerun`) that holds copies of both and authors "Blackstaff (D&D 5e)" with a parent in each. [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md) built it. [RFC 0001](0001-core-domain-data-model.md)'s open question 3 guessed the same for items, as RFC 0024's context recounts: a system-neutral "Sword" with "Sword (D&D 5e)" variants inheriting from it.

[ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) applied it to the equipment seed in a smaller form: two repositories.

- **`core`** holds the neutral vocabulary and no items: the category tree (weapon, ranged weapon, crossbow, armour, kinds of gear), the stat groups and definitions, and the weight recipe.
- **`dnd5e`** is a bridge over it. It holds the D&D layer (proficiency, tier and property categories, the dice and flag stats) **and every imported item**, each with its neutral and its D&D facts together.

It named a third option and left it out: "a third repository, for items only", out of scope because it cost three grants instead of two. That reason is weaker since [`repo offer`](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md) grants and copies a whole stack.

The maintainer's picture, for the equipment seed, is three repositories:

- **A, Common Fantasy Equipment:** the items with their descriptions, the obvious physical facts (weight, is a container, certain tags), and the logical hierarchy ("a heavy crossbow is a crossbow, a crossbow is a ranged weapon, a ranged weapon is a weapon, and it is heavy"). Later, beings (race, class) would join it.
- **B, Dungeons & Dragons 5e:** the mechanical stat groups, the keyword tags (versatile, loading), the economic cost in copper coin, and the prototypes that apply them (a "versatile" prototype that applies the versatile stat).
- **C, Common items in D&D 5e:** a bridge over A and B that gives A's items B's prototypes, the D&D prices, and the values of the mechanical stats.

A table subscribes to C and gets all three. A Pathfinder table would take A, a Pathfinder rules repository and a Pathfinder bridge.

### What this builds on

- **A bridge carries only what it authored.** Its edits to its copies of a dependency don't travel downstream, so C can't change A's Longsword. It authors a new entity that inherits from it ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md), RFC 0024 A8).
- **Descriptions and pictures accumulate down the prototype chain**, each labelled with where it came from ("From Longsword"). A title doesn't inherit: an item's displayed title is its own description's title, else its own name ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md), [0067](../adr/0067-item-title-falls-back-to-name.md)).
- **A stat value resolves through the prototypes**, and a value on the entity itself beats an inherited one ([ADR 0037](../adr/0037-effective-stat-resolution.md)).
- **Stat groups and definitions can't be renamed or retyped, and can only be deleted while unused** ([ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)). Which repository defines which one has to be right before anything is published.
- **The API reads some stat names**: `weight`, `size`, `is_container`, and the named `price` and `armor` columns on an item ([well-known stats](../reference/well-known-stats.md)). A tenant that defines one gets the behaviour.
- **A merged stat group or definition counts downstream as a copy of the origin it was merged with** ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)), so two repositories that both define a same-named group copy together after a one-time merge.
- **Grants aren't transitive**, and `lorenzo repo offer` follows a bridge's manifest ([ADR 0163](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md)).

## What was tried

The part of the picture that wasn't known to work, a bridge over two repositories one of which is itself a bridge, was run against the real API on 2026-10-04, as a scratch end-to-end test that is not committed. A was seeded with the core layer and given one item, "Longsword", with a weight and a description. B copied A and was seeded with the D&D layer. C copied B (which brought A first) and authored a second entity with parents A's Longsword and B's Martial weapon and Versatile categories, plus a price and two dice stats of its own. A play tenant then copied C.

- **A copy of C brings the whole stack in one step**, in dependency order: A, then B, then C. The plan lists three steps. C's own copy of B lists two, A and B.
- **The parents are re-targeted onto the table's own copies.** The table's D&D sword has the parents Longsword, Martial weapon and Versatile, and its Longsword *is* the table's copy of A's Longsword: one Longsword, not two.
- **Neutral facts arrive by inheritance.** The sword's weight is A's, through A's weight recipe. Its own price and dice are its own. The Versatile tag is inherited from B's category.
- **Descriptions accumulate.** The sword's description list holds A's text labelled "From Longsword" and B's rules text labelled "From Versatile". The sword has no description of its own, so its title is its own name.
- **Both repositories' entities are listed.** A search for "Longsword" in the table finds two items. The API accepts two entities with the same name in one tenant, so they would be indistinguishable in a list that shows names. This is a cost, not a bug, and a decision below.

Not tried: corrections travelling through three levels, `repo offer` over a three-repository stack, and the importer writing the two halves.

## Proposal

### 1. Three repositories, by what is true of what

| Repository | Holds | Its authors answer |
| --- | --- | --- |
| **A, common equipment** | The vocabulary seeded today as `core` (the category tree, the physical and tag stats, the weight recipe). The **neutral items**: name, aliases, weight, the forms and materials they are, whether they hold things, the sourcebook citation, and every description that isn't tied to a mechanic. | What is this thing, anywhere? |
| **B, D&D 5e** | A bridge over A: it copies A, then the D&D layer on top. Every stat of the D&D layer (dice, damage type, attack ability, the property flags) and the other D&D stats listed in section 4 (price in copper, armour, strength required, ranges), and the proficiency, tier and property categories with their rules text. | How does D&D 5e treat things? |
| **C, common items in D&D 5e** | A bridge over B (and so A). **No vocabulary of its own.** One entity per D&D item: parents are A's item and B's categories, and it carries the D&D values (price, dice, armour, strength required) and the sheet's rules text. Packs. | What is this thing in D&D 5e? |

B is a bridge over A because the D&D stats go into groups (`damaging`, `tags`) that A creates, as `dnd5e` over `core` does today ([RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R9 has A create all five conventional groups, so two systems never collide on creating one). B could instead copy nothing and define its own groups, leaving C to merge the same-named ones when it copies both ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md) allows a merge). That hasn't been tried, and it makes the merge a decision at every copy.

### 2. How an item is built

```text
A  Longsword          parents: blade, melee-weapon      own_weight 3     (aliases)
B  Martial weapon     (category)                        Versatile        (category, tag, rules text)
C  Longsword (D&D 5e) parents: A's Longsword, B's Martial weapon, B's Versatile
                      own: price 1500, damage_dice_count 1, damage_die 8, damage_versatile_die 10, sourcebook
```

C's entity never edits A's. A table sees the D&D item with A's weight and text and B's rules text by inheritance, and C's values on top.

### 3. Authoring rules

- **C authors, it never edits.** Anything C wants to differ from A it says on its own entity, as ADR 0120 already requires.
- **A's items are prototypes.** They are authored with `in_public_catalog` false, which is what the importer does unless it is told `--public-catalog`, and C's import is told. A player lists only public items ([ADR 0116](../adr/0116-players-read-catalog-items-and-a-public-catalog.md)) and a copy keeps the flag as its author set it (RFC 0024), so a table's players see the D&D items and not the neutral ones. A GM lists the whole catalog and sees both, and can narrow it with the existing `prototype_id` filter ([ADR 0073](../adr/0073-item-prototype-graph-inspection-and-bulk-editing.md)): "everything built on Martial weapon" is C's.
- **A's items and C's are told apart by name and slug.** Slugs are already `<namespace>-<list>-<key>`; A and C take different namespaces (`basic-` and a D&D one), so a slug names which repository's entity it is. The name needs a rule: see the first open question.

### 4. The stat vocabulary

Decided with the maintainer on 2026-10-04. Today all eighteen definitions of the core layer would go to A. With D&D pulled out into B, eight of them are D&D's, and so are the twenty-two the D&D layer already has:

| Where | Definitions |
| --- | --- |
| **A** (ten) | `own_weight`, `weight`, `contents_weight`, `bundle_amount`, `is_container`, `is_consumable`, `is_magical`, `is_silvered`, `is_adamantine`, `sourcebook` |
| **B** (thirty) | the twenty-two of the D&D layer, and `price`, `armor`, `armor_formula`, `strength_required`, `stealth_disadvantage`, `adds_modifier`, `range_normal`, `range_long` |

A still creates all five conventional stat groups, so `economic`, `destroyable` and `damaging` exist in A with no definitions of their own, and B's go into them ([RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R9). Moving a definition is a change to the seed's layer tags (the seed's `layer` key exists for this) and a new seed version. Nothing is published, so it costs nothing now; after a publish a definition can't be moved, only added.

### 5. The importer writes two halves

An MPMB sheet is D&D data. The importer has to split what it reads into what is true anywhere (name, aliases, weight, forms, materials, whether it contains things, the sourcebook citation, descriptive text) and what is D&D's (price, dice, armour and range numbers, proficiency, properties, rules text). In the sheet's own fields that is: `nameAlt` and `alternatives` (aliases), prose descriptions of gear, and `sourcebook` for A; a weapon's `description`, which lists its properties and gives the versatile die, its `tooltip` of special rules, and the numbers, for C. It does this as **two passes over the same files**, so each repository's content is a function of the source and a map, and either can be re-run:

- a neutral pass into A, creating the item under its forms;
- a D&D pass into C, which finds A's item by its slug **in C's own copy of A** (as it finds a core category in the bridge today), creates the D&D entity beside it, and parents it in both.

Identity stays the slug, so a second run finds what the first made. The built-in map's rows gain a `part` (neutral or system). That is a slice of its own, with its own ADR.

### 6. Setting it up, and what a table does

```bash
# A
lorenzo tenant create "Common Fantasy Equipment" --slug common-equipment
lorenzo seed --tenant common-equipment --layer core --yes
lorenzo apply --tenant common-equipment --part neutral --base ... --yes   # --part is proposed
lorenzo repo publish --tenant common-equipment

# B: a copy of A, then the D&D layer
lorenzo tenant create "Dungeons & Dragons 5e" --slug dnd5e
lorenzo repo offer dnd5e --tenant common-equipment
lorenzo seed --tenant dnd5e --layer dnd5e --yes
lorenzo repo publish --tenant dnd5e

# C: a copy of B (which brings A), then the items
lorenzo tenant create "Common items in D&D 5e" --slug dnd5e-common-items
lorenzo repo offer dnd5e-common-items --tenant dnd5e
lorenzo apply --tenant dnd5e-common-items --part system --public-catalog --base ... --yes
lorenzo repo publish --tenant dnd5e-common-items

# A table: grants on all three, and one copy
lorenzo repo offer my-table --tenant dnd5e-common-items
```

Thirteen commands, each already built except for the proposed `--part`. A single setup command is a separate, later question.

### 7. Corrections

A table takes each repository's updates from that repository ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)), as [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)'s four steps already assume. A correction to A is published once, and a table takes it from A. B's and C's authors re-sync A to keep their own copies current. Whether a bridge must also publish again for a table to see anything is the part of ADR 0162's steps that three levels would test, and it hasn't been tried.

## What it costs

- **Two entities per D&D item** in a table's catalog, which is what multiple inheritance makes of "the same sword, in a system". A search finds both; the player-facing one is C's.
- **Three grants and a longer chain of authors.** `repo offer` takes the work out of the grants. The chain is A, then B, then C, and each is published by whoever owns it.
- **The importer becomes two passes**, and its map gains a notion of which half a value belongs to.
- **Pre-1.0 churn in the seed.** Moving definitions between layers changes `builtin.toml`, its version, and the README's counts.

What it buys: a second system takes A and brings its own B and C, without D&D's items or its stats or its prices in its repositories; the rules and the items can be published, owned and licensed on their own; and the neutral facts of a thing are written once.

## Alternatives

- **Keep ADR 0162's two repositories.** Nothing to build. Neutral and D&D facts stay mixed in every item, and a second system re-imports its own items.
- **Three repositories, items stay D&D's.** Core as vocabulary, a rules repository (B), and a bridge (C) whose items are complete D&D items with parents in both layers. No neutral items, so no second entity per item and one importer pass. It separates the rules from the items, which move at different speeds. It gives up reuse of items across systems. It is the cheapest first step, and it can grow into the proposal later by adding A's items and re-parenting C's onto them, but every subscriber then takes that as an update, which is the cost [RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R8 named for splitting late.

## Decided with the maintainer (2026-10-04)

- **What text lives in A:** every description that isn't tied to a mechanic. The sheet has little of it for weapons, whose `description` is a property list and whose `tooltip` is special rules (both C's), so most of A's descriptive text will be written rather than imported. Gear text and aliases are A's.
- **Which stat definitions are D&D's:** section 4. `sourcebook` is common.
- **Nothing is published or granted.** There is only local test data, so nothing has to be migrated. The local `core` and `dnd5e` tenants can be rebuilt, and no order of work has to protect a subscriber.

## Open questions

1. **What does C's entity call itself?** A GM searching a table's catalog for "Longsword" finds two items, because the neutral one and the D&D one are both in the table:

   ```text
   Longsword   weight 3                                (A's: no price, no damage)
   Longsword   weight 3, price 1500, damage 1d8        (C's: the D&D item)
   ```

   Handing the wrong one to a player gives a sword with no price and no damage, and the D&D item's page says "From Longsword" under a title that is also "Longsword". Players only list C's, since A's items aren't public, so the choice is about GMs and about what players see in their inventories. Three ways:
   - **Same name.** What the importer does today, with no work. The two can't be told apart by name, only by slug.
   - **A suffix on C's** ("Longsword (D&D 5e)"). Clear to a GM; players see the suffix everywhere.
   - **A suffix on A's** ("Longsword (common)"). Players see the plain name, a GM sees which is the prototype, and the label reads "From Longsword (common)". The neutral pass has to add the suffix.

   An item's title is its own description's title or its name, so whichever is chosen is what a table shows.
2. **Is A one repository, or two?** Two would be the vocabulary (categories, stat groups and definitions, the weight recipe) as one repository, and the neutral items as a second that is a bridge over it: A0, "Common vocabulary", and A1, "Common Fantasy Equipment". B would copy A0 only, and C would copy A1 and B, so a table would take four grants (A0, A1, B, C) instead of three. What it buys is a system that wants the shared vocabulary but not these items, a Warhammer repository with its own items, say, without carrying them. What it costs is another repository and another grant, and nothing today needs it, since A's items are non-public prototypes that a system can ignore. This RFC keeps one.
3. **Which items do packs link to?** A pack is D&D (an Explorer's Pack has D&D contents, and `pack give` makes the table's items), so it lives in C and links C's entities. Confirm.
4. **Names.** The three repositories' names and slugs are the maintainer's.

## Slices, if accepted

Each its own ADR, in this order:

1. **The seed's layers.** Sort the stat definitions (section 4), decide where each category and definition lives, bump the seed version, and extend `tests/e2e/test_split.py` to the three-repository stack that was tried here.
2. **The importer's two passes** and the `part` in its map.
3. **Rebuilding the local tenants**, and the setup walkthrough in the README.
4. **Later:** a single setup command, and showing on a table's item which repository each part of it came from.

## Not in scope

- **Beings** (race, class). They would join A and a rules repository the same way, and they are a later question.
- **Settings.** A setting such as Faerûn is the same pattern on another axis (RFC 0024's own example) and isn't touched.
- **Live reads and edits through a bridge.** ADR 0120's rule that a bridge's edits to its copies don't travel stays.
- **What the SRD's licence allows** for text in a published repository. It is worth checking before anything is published, and it isn't decided here.
