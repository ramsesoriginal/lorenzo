# RFC: Item repositories — a shared vocabulary, common equipment, a rules repository, and a bridge that attaches the rules to the equipment

Status: proposed. The maintainer decided its shape on 2026-10-04 ([Decided](#decided-with-the-maintainer-2026-10-04)); one question remains ([Open](#open-questions)). Written at the maintainer's request after the first real import. It would amend [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md), and it needs one change to the repository API ([§3](#3-attachments-the-api-change)). It is meant to be accepted before anything is published or granted.

## Context

[RFC 0024](0024-repositories.md) §5 and §9 designed repositories to be combined: a *content* repository (Faerûn), a *system* repository (D&D 5e), and a *bridge* (`dnd_faerun`) that holds copies of both and authors "Blackstaff (D&D 5e)" with a parent in each. [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md) built it. [RFC 0001](0001-core-domain-data-model.md)'s open question 3 guessed the same for items, as RFC 0024's context recounts: a system-neutral "Sword" with "Sword (D&D 5e)" variants inheriting from it.

[ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) applied it to the equipment seed in a smaller form: two repositories.

- **`core`** holds the neutral vocabulary and no items: the category tree (weapon, ranged weapon, crossbow, armour, kinds of gear), the stat groups and definitions, and the weight recipe.
- **`dnd5e`** is a bridge over it. It holds the D&D layer (proficiency, tier and property categories, the dice and flag stats) **and every imported item**, each with its neutral and its D&D facts together.

It named a third option and left it out: "a third repository, for items only", out of scope because it cost three grants instead of two. That reason is weaker since [`repo offer`](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md) grants and copies a whole stack.

What the maintainer wants is this. The common equipment is written once, with its descriptions. A rules system adds its stats and prototypes **to those same items**, without redefining them. A tenant that subscribes to the equipment has everything usable, and later subscribing to a system pulls in its rules and adds them to the items the tenant already has. Another system (Pathfinder, Shadowrun, Vampire: the Masquerade) does the same without touching the first. A repository that extends D&D attaches to D&D's prototypes without knowing the repository that joins D&D to the equipment. Tenants can be multi-system and campaigns are not: a tenant holds several systems' prototypes side by side, and a campaign uses the one its game system names ([§9](#9-systems-side-by-side)).

### What this builds on

- **A bridge carries only what it authored.** Its edits to its copies of a dependency don't travel downstream. ADR 0120 lists two things a bridge doesn't carry, "its edits to its copies of its dependencies" and "rows between two copied entities", and says "to make an upstream entity behave differently under a system, the bridge authors a new entity that inherits from it" (RFC 0024 A8). This RFC changes that for one kind of row.
- **Copying works on a repository's *own* rows**, those that aren't themselves copies, and re-targets every reference onto the subscriber's copy through the *origin* the two copies share ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md), [0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)). An `entity_prototype` edge belongs to its child. A row whose target the subscriber lacks is dropped, and the copy reports it.
- **Every copy link records a snapshot of the entity as it was copied**, "with every id translated to its origin", and that snapshot includes the entity's prototypes. **Updates** diff the snapshot, the repository's current state and the tenant's, and already merge an entity's prototype set element by element, so a parent the tenant added to a copy is kept and a repository's later additions arrive as "added" rows ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).
- **Descriptions and pictures accumulate down the prototype chain**, each labelled with where it came from ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md)). A title doesn't inherit ([ADR 0067](../adr/0067-item-title-falls-back-to-name.md)).
- **A stat value resolves through the prototypes**: the entity's own value wins, then the nearest ancestor's, a tie between equally near ancestors breaks on the priority of the stat groups each has acquired, and then arbitrarily but deterministically ([ADR 0037](../adr/0037-effective-stat-resolution.md)).
- **Stat groups and definitions can't be renamed or retyped, and can only be deleted while unused** ([ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)). Which repository defines which one has to be right before anything is published.
- **The API reads some stat names**: `weight`, `size`, `is_container`, and the named `price` and `armor` columns on an item ([well-known stats](../reference/well-known-stats.md)).
- **Grants aren't transitive**, and `lorenzo repo offer` follows a bridge's manifest ([ADR 0163](../adr/0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md)).

## What was tried

Four things were run against the real API on 2026-10-04, as scratch end-to-end tests that are not committed.

**A bridge over repositories that share a dependency.** **A0** was seeded with the core layer; **A1** copied A0 and got one item, "Longsword"; **B** copied A0 and was seeded with the D&D layer; **C** copied A1 and B; a play tenant took C.

- **`repo offer` follows the diamond.** C's first offer, from A1, granted A0 and A1 and copied them in that order. Its second, from B, found A0 "already copied there" and copied only B's own rows. A0 is in C once.
- **One offer brings a table the whole stack**: it granted C's three dependencies and C, then copied A0, A1, B and C in order. The copy plan lists those four steps.
- **Nothing is duplicated.** The table had six stat groups and forty stat definitions, each once.
- **The `repo contents` view reads the stack**: for C it lists the three repositories it is built on.

**A bridge that derives.** C authored a second entity, "Longsword", with parents A1's Longsword and B's categories, plus a price and dice. The table's copy had A1's item as a parent (one of it, not two), A1's weight by inheritance, and A1's and B's descriptions labelled "From …". A search found two items, and the API accepted two with the same name. This is the design this RFC replaces.

**A bridge that attaches, today.** C gave its copy of A1's Longsword an extra parent, a new item "Longsword (D&D 5e)" holding a price and dice with B's Martial weapon and Versatile as parents, and a stat value directly on the copy. In C the sword showed the price through the new parent. A table that already held A1 then took C. Its copy plan listed A0 and A1 as already copied and B and C as new. The new prototype arrived and was attached to nothing; **the table's Longsword kept its two parents and gained no stat**, and nothing said so. That is ADR 0120's rule, working as written.

**The maintainer's example as one prototype graph**, in a single tenant, with both attachments made by replacing an item's prototypes: Physical Object; Weapon, Melee Weapon, Blade and Longsword with descriptions; Weapon Class, Martial Weapon, Weapon Property, Versatile (a tag) and Economic Object; "Longsword 5e" under Martial Weapon and Versatile with the price and dice; Economic Object added as a parent of Weapon, and Longsword 5e as a parent of Longsword. The Longsword resolved to the price 1500, the damage die 8 and one die, and the `is_versatile` tag, all inherited, and to its own weight of 3. Its descriptions accumulated nearest first: its own, Blade, Longsword 5e, Melee Weapon, Martial Weapon, Versatile, Weapon, Weapon Class. A different weapon, a Handaxe, inherited the economic default through the attachment on Weapon. The graph behaves as the example expects; what is missing is only that attachments don't yet travel between repositories.

Not tried: attachments that travel (they don't exist yet), corrections through the levels, and the importer writing the two halves.

## Proposal

### 1. Four repositories

The maintainer's names and slugs; "depends on" means holds a copy of. The contents follow the maintainer's example, which isn't exhaustive.

| Repository (slug) | Depends on | Holds | Its authors answer |
| --- | --- | --- | --- |
| **A0, Core** (`core`) | nothing | The root prototype, Physical Object, which carries the weight recipe; the stat groups `physical` and `sourcebook`, and `tags` for the container, consumable, magical and material tags; and the ten neutral stat definitions of section 5. | What can be said of a thing, anywhere? |
| **A1, Common Fantasy Equipment** (`common-fantasy-eq`) | A0 | The **forms and the items**, each with a description: Weapon, Melee Weapon, Blade, Longsword, the gear kinds, and the items under them, packs included. The items are public and usable on their own; the forms are not public, as in the seed today. | What is this thing, anywhere? |
| **B, Dungeons and Dragons 5e** (`dnd5e`) | A0 | The `economic` stat group with `price`, the `damaging` group with the damage stats, the `is_versatile` tag and the other D&D flags; and the prototypes that use them: Weapon Class (damaging), Martial Weapon under it, Weapon Property, Versatile under that (setting `is_versatile`), Economic Object (adding the economic group), all under a **system root prototype**, "D&D 5e" ([§9](#9-systems-side-by-side)). Rules text on the prototypes that have it. | How does D&D 5e treat things? |
| **C, Common D&D5e Equipment** (`dnd5e-common-eq`) | A1 and B | **No vocabulary, no forms and no second set of items.** Its own D&D prototypes, such as Longsword 5e under Martial Weapon and Versatile, with the values of the damaging and economic stats; and the **attachments** that join the equipment to the rules: Economic Object as a parent of Weapon, Longsword 5e as a parent of Longsword. | What is this thing in D&D 5e? |

A1 and B both build on A0, so C's dependencies form a diamond; "What was tried" shows ADR 0120's manifest handles it.

### 2. How an item is built

```text
core                 Physical Object   (weight recipe; physical, sourcebook, tags groups)
common-fantasy-eq    Weapon            parent: Physical Object
                     Melee Weapon      parent: Weapon
                     Blade             parent: Weapon
                     Longsword         parents: Blade, Melee Weapon            own_weight 3
dnd5e                D&D 5e            (system root: Weapon Class, Weapon Property and Economic Object descend from it)
                     Weapon Class      (damaging group)
                     Martial Weapon    parent: Weapon Class
                     Weapon Property   ->  Versatile  (sets is_versatile)
                     Economic Object   (adds the economic group, with price)
dnd5e-common-eq      attach  Economic Object  ->  Weapon                       (B's prototype on A1's form)
                     Longsword 5e      parents: Martial Weapon, Versatile      price 1500, damage_dice_count 1, damage_die 8
                     attach  Longsword 5e     ->  Longsword                    (C's prototype on A1's item)
```

A table that holds only A1 has a Longsword with a weight and a description. When it takes C, **the same Longsword** gains Longsword 5e as a parent, and with it the price, the dice, B's categories and B's rules text; and every weapon gains the economic group through Weapon. There is one Longsword in the table, and no suffix on any name. Another system's repository attaches its own prototypes to the same Weapon and Longsword, and a repository that extends D&D attaches to B's prototypes (to Martial Weapon, say) without knowing C.

### 3. Attachments: the API change

**Definition.** An *attachment* is a parent that a repository's authors added to an entity the repository holds a copy of. In terms of rows: an `entity_prototype` edge in the repository whose child is a copy, and which the child's copy link did not record when the child was copied or last synced. Its **parent may be the repository's own entity** (Longsword 5e on Longsword) **or another repository's copy** (B's Economic Object on A1's Weapon). Authors make one with what exists: `PUT /tenants/{id}/items/{entity_id}/prototypes` on the copy, which was run in "What was tried" and answers `200`. The only new thing is what a copy does with it.

**How an attachment is told from an edge that came with a copy.** The copy link of the child records a snapshot of its prototypes as origin ids. The edges the child has now, beyond that set, are the repository's own additions: the repository is a tenant, and whatever its authors add to a copy is theirs. So an edge between two copies is carried when the bridge added it and not when it arrived with a dependency, and nothing has to be guessed or compared against the dependency. A parent the bridge *removed* from a copy does not travel: only additions do.

**In a copy** ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)):

- For each attachment of the repository it is copying, the plan finds the subscriber's local copy of the child, and of the parent, through the origin both copies share, and writes the edge between them. For a parent that is the repository's own entity, that is the local copy made in the same call.
- A dependency is copied before the bridge ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)), and a subscriber that already holds it keeps its copy, so both ends are there either way.
- If the subscriber has no copy of the child or of the parent (it skipped the row, or deleted it), that one attachment is **dropped and reported**, like any row whose target is missing. If the edge would make a prototype loop, it is dropped with that reason, as an update already does.
- Plans and copy responses count attachments beside entities, stat groups, stat definitions and information, so a dry run shows them.

**Provenance.** A new copy-link table records each attachment a tenant took (the repository, the child's origin, the parent's origin), with the tenant's RLS like the other three. Without it a later removal could not be told from an edge the tenant added itself. It is bookkeeping, not repository content, so it goes in the "not content" list of `repository_access` (ADR 0118).

**In updates** ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)):

- An attachment the bridge adds later is an *added* row, applied like one.
- One it removes is a *removed* row, with ADR 0121's existing choices.
- One the tenant removed locally is *deleted locally*.
- The tenant's own extra parents on an item stay, since the prototype set already merges element by element.

**Purging a copy** (ADR 0119) already counts "an edge from its own entity to a copied one" under `also_removed`. Attachments taken from a repository go with it, and are counted.

**What does not change.** Edits to copies other than these edges still don't travel: a stat value, a name or a description written onto a copy stays in the bridge, so a bridge still can't change a dependency's item. Nothing flows live: the attachments reach a tenant by copy or by `repo updates`, when the tenant chooses, so RFC 0024's "curated, reviewed composition over live pass-through" holds. The change is to ADR 0119, 0120 and 0121 and to RFC 0024 A8's list of what a bridge carries.

**What it limits.** A value on the item itself beats an inherited one, so a D&D prototype cannot override a stat that A1's item sets directly. The ten stats in A0 are the neutral ones, and every D&D stat is defined in B, so only a case where D&D wants a different weight for an item runs into it. **Two systems on one item** both give it values for stats of the same name, and today resolution takes every ancestor: between equally near ones ADR 0037 breaks the tie on group priority and then arbitrarily. Until resolution is system-aware ([§9](#9-systems-side-by-side)), one system per tenant is what this supports.

**Adding a group.** A stat group is acquired by an entity only by setting a stat or a tag in it, so a prototype that adds the economic group does it by carrying a default for a stat in it. Economic Object has a price of 0 in the graph of "What was tried", and every weapon inherits that default until a more specific prototype sets one. The maintainer prefers this to a route that acquires a group with no value: a default is chosen deliberately, per prototype, as part of authoring it.

### 4. Authoring rules

- **A1's items are public.** They are authored with `in_public_catalog` true (`--public-catalog` on the neutral pass), so a tenant that holds only A1 has usable items and a player lists them. Its forms, like the seed's categories today, are not.
- **C's prototypes are not public.** They are authored with `in_public_catalog` false, which is what the importer does by default, so players don't list them. A GM sees them in the whole catalog, and can narrow with the existing `prototype_id` filter ([ADR 0073](../adr/0073-item-prototype-graph-inspection-and-bulk-editing.md)): "everything built on Martial Weapon" is B's.
- **C never edits A1's items.** It adds prototypes and attachments. Slugs name the repository: A1's items use the `basic-` namespace and C's prototypes a D&D one (`srd5e-weapons-longsword`).
- **Packs are A1's items.** A pack is an item whose description lists its contents, linking A1's items, so `pack give` gives the real items. C attaches D&D's prototype to a pack like any other item, which is where an Explorer's Pack gets its price.

### 5. The stat vocabulary

Today all eighteen definitions of the core layer would go to A0. With D&D pulled out into B, eight of them are D&D's, and so are the twenty-two the D&D layer already has:

| Where | Definitions |
| --- | --- |
| **A0** (ten) | `own_weight`, `weight`, `contents_weight`, `bundle_amount`, `is_container`, `is_consumable`, `is_magical`, `is_silvered`, `is_adamantine`, `sourcebook` |
| **B** (thirty) | the twenty-two of the D&D layer, and `price`, `armor`, `armor_formula`, `strength_required`, `stealth_disadvantage`, `adds_modifier`, `range_normal`, `range_long` |

In the maintainer's example B defines the `economic` and `damaging` groups itself, and A0 holds `physical`, `sourcebook` and `tags`; B's tags go into A0's `tags` group. A second system that defines a group or definition of the same name (a `price`, an `economic` group) merges with B's on its first copy by one choice, which ADR 0119 allows when the types match, and the table's `price` is then one stat. Moving a definition is a change to the seed's layer tags (the seed's `layer` key exists for this) and a new seed version. Nothing is published, so it costs nothing now; after a publish a definition can't be moved, only added.

### 6. The importer and the seed write two halves

An MPMB sheet is D&D data. The importer has to split what it reads into what is true anywhere (name, aliases, weight, forms, materials, whether it contains things, the sourcebook citation, descriptive text) and what is D&D's (price, dice, armour and range numbers, proficiency, properties, rules text). In the sheet's own fields that is: `nameAlt` and `alternatives` (aliases), prose descriptions of gear, packs and their contents, and `sourcebook` for A1; a weapon's `description`, which lists its properties and gives the versatile die, its `tooltip` of special rules, and the numbers, for C. It does this as **two passes over the same files**, so each repository's content is a function of the source and a map, and either can be re-run:

- a neutral pass into A1, creating the item under its forms, public;
- a D&D pass into C, which finds A1's item by its slug **in C's own copy of A1** (as it finds a core category in the bridge today), creates the D&D prototype under B's categories with the D&D values, and **appends the prototype to the item's parents** if it isn't there yet.

Identity stays the slug, so a second run finds what the first made and attaches nothing twice. The built-in map's rows gain a `part` (neutral or system). That is a slice of its own, with its own ADR.

The seed follows the same split. Today `core` holds 33 categories and the D&D layer 28. In the maintainer's example A0 keeps only Physical Object and the stat vocabulary, the forms tree (Weapon, Melee Weapon, Blade and the rest) is A1's, and the category-level attachments (Economic Object on Weapon) are C's. That is a seed layer for each of the four repositories, `core`, an equipment layer, `dnd5e` and a layer for C, chosen with `--layer` ([ADR 0143](../adr/0143-lorenzo-seed-taxonomy-and-stats.md), [0166](../adr/0166-a-bare-seed-refuses-to-add-a-layer-to-a-tenant-that-holds-another.md)). The layer names are provisional.

### 7. Setting it up, and what a table does

```bash
# A0
lorenzo tenant create "Core" --slug core
lorenzo seed --tenant core --layer core --yes
lorenzo repo publish --tenant core

# A1: a copy of A0, the forms and the neutral items, public
lorenzo tenant create "Common Fantasy Equipment" --slug common-fantasy-eq
lorenzo repo offer common-fantasy-eq --tenant core --yes
lorenzo seed --tenant common-fantasy-eq --layer equipment --yes                             # layer name provisional
lorenzo apply --tenant common-fantasy-eq --part neutral --public-catalog --base ... --yes   # --part is proposed
lorenzo repo publish --tenant common-fantasy-eq

# B: a copy of A0, with the D&D layer
lorenzo tenant create "Dungeons and Dragons 5e" --slug dnd5e
lorenzo repo offer dnd5e --tenant core --yes
lorenzo seed --tenant dnd5e --layer dnd5e --yes
lorenzo repo publish --tenant dnd5e

# C: copies of A1 and B, the category-level attachments, then the D&D prototypes and their attachments
lorenzo tenant create "Common D&D5e Equipment" --slug dnd5e-common-eq
lorenzo repo offer dnd5e-common-eq --tenant common-fantasy-eq --yes
lorenzo repo offer dnd5e-common-eq --tenant dnd5e --yes
lorenzo seed --tenant dnd5e-common-eq --layer dnd5e-equipment --yes                         # layer name provisional
lorenzo apply --tenant dnd5e-common-eq --part system --base ... --yes
lorenzo repo publish --tenant dnd5e-common-eq

# A table: the equipment alone is usable...
lorenzo repo offer my-table --tenant common-fantasy-eq --yes
# ...and later, D&D is added to the items it already has
lorenzo repo offer my-table --tenant dnd5e-common-eq --yes
```

Eighteen commands to build the four repositories, then one to use the equipment and one to add D&D to it, each already built except for the proposed `--part`, the new seed layers and the attachments in `copy`. A single setup command is a separate, later question.

### 8. Corrections

A table takes each repository's updates from that repository, as [ADR 0162](../adr/0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)'s four steps already assume. A correction to A1's item is published once and a table takes it from A1. A new attachment in C reaches a table as an added row. A1's, B's and C's authors re-sync their dependencies to keep their own copies current. Whether a bridge must also publish again for a table to see anything is the part of ADR 0162's steps that more levels would test, and it hasn't been tried.

### 9. Systems side by side

Tenants can be multi-system and campaigns are not. With the rules as prototypes, a tenant can hold Pathfinder's, Shadowrun's and D&D's prototypes attached to the same items, and a campaign should resolve an item through the one prototype tree its game system names.

This is already the direction of the codebase. RFC 0001's open question 3 proposes that "which system is this for" be a property of which prototype an entity inherits from, not a column. `campaign.game_system` exists, as a plain string, and the docstring of the campaign update says that changing it "changes which prototype variants every entity in the campaign resolves through on next read". Nothing implements that last part: effective stats walk every ancestor ([ADR 0037](../adr/0037-effective-stat-resolution.md)) and inherited descriptions take every ancestor ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md)).

What this RFC does for it is only to make the data available. **Each system's repository gives its prototypes one common ancestor, a system root** (`D&D 5e` in B), so that belonging to a system is ancestry and needs no new kind of tag. A prototype is a system's if it has that root among its ancestors and neutral if it has none. Attachments connect neutral entities to system prototypes, so the neutral item stays neutral and a system's facts reach it through the attached prototype's ancestry.

Resolution that uses it is a follow-up RFC, with questions of its own: how a campaign's `game_system` names a root; what an item shows in a tenant's catalog, which has no campaign, and how an instance, which belongs to one, differs; and which reads take the system (stats, descriptions, tags and the named columns).

## What it costs

- **An API change**, in the copy planner, the updates diff and apply, purge, one new table and its migration, the plan and copy response fields, and the tests that go with them. It is bounded: one kind of row, one rule for whose it is, and the existing machinery for re-targeting, dropping and updating.
- **Four grants and a longer chain of authors.** `repo offer` takes the work out of the grants. The chain is A0, then A1 and B, then C.
- **The importer becomes two passes and the seed four layers**, and the map gains a notion of which half a value belongs to.
- **Pre-1.0 churn in the seed.** Moving definitions and categories between layers changes `builtin.toml`, its version, and the README's counts.
- **No way to take D&D back off**, the same as any copy today ("what they already copied stays theirs"). A tenant that wants to undo C removes the attachments itself. A command for it is a later question.
- **One system per tenant until resolution knows about systems** (section 9): two would share items and break ties arbitrarily.

What it buys: one item per thing in a table, usable from A1 alone and enriched by C when the tenant wants it; a second system takes A0 and A1 and brings its own B and C, each attaching its own prototypes to the same items, with no item defined twice; a repository that extends a system attaches to that system's prototypes without knowing the one that joins it to the equipment; the rules and the items can be published, owned and licensed on their own; and the neutral facts of a thing are written once.

## Alternatives

- **C derives instead of attaching** (the earlier version of this RFC). C authors a second, playable entity per item with the neutral item as a parent. It needs no API change and works today, and it leaves two entities per D&D item in a table, told apart by a suffix on the neutral one. It is the fallback if the API change is not wanted.
- **Attachments whose parent must be the bridge's own entity.** Narrower, and recommended while the question was open, because an edge between two copies was thought to be indistinguishable from one that arrived with a dependency. The copy link's snapshot settles that, and the maintainer's example needs the wider form (Economic Object on Weapon), so it is not chosen.
- **An attach step in the CLI.** C carries the prototypes and a list of which items each applies to, and a command adds the parents in the tenant after a copy. No API change, but the attachments are not part of the copy, `repo updates` doesn't know of them, and the step has to be run.
- **Writing stat values straight onto a dependency's items.** Rejected: two systems would write the same stat onto one item and collide, nothing would say where a value came from, and a tenant could not remove it. A prototype per system avoids all three.
- **Keep ADR 0162's two repositories**, or **three, with items staying D&D's.** Nothing to build, and neutral and D&D facts stay mixed in every item, so a second system re-imports its own items.
- **The vocabulary and the equipment in one repository.** One repository and one grant fewer, and a system that wants the vocabulary without the equipment carries it anyway. Splitting costs nothing while nothing is published.

## Decided with the maintainer (2026-10-04)

- **What text lives in A1:** every description that isn't tied to a mechanic. The sheet has little of it for weapons, whose `description` is a property list and whose `tooltip` is special rules (both C's), so most of A1's descriptive text will be written rather than imported. Gear text, aliases and packs are A1's.
- **Which stat definitions are D&D's:** section 5. `sourcebook` is common.
- **Nothing is published or granted.** There is only local test data, so nothing has to be migrated. The local `core` and `dnd5e` tenants can be rebuilt.
- **The vocabulary and the equipment are two repositories**, A0 and A1.
- **The names and slugs** of section 1.
- **C attaches to A1's items instead of deriving from them**, through the API, so that a tenant that holds A1 gets D&D added to its existing items.
- **Packs are A1's items**, and get C's prototype like any other.
- **An attachment's parent may be another repository's copy**, not only the bridge's own entity.
- **The shape of the contents**, as in the Longsword example of section 2.
- **The forms tree lives in A1.** A0 keeps Physical Object and the stat vocabulary.
- **B defines the `economic` and `damaging` groups.** A second system's same-named groups and definitions merge with them on its first copy.
- **A prototype adds a stat group by carrying defaults** for stats in it, so no route to acquire a group alone is needed.
- **Tenants are multi-system and campaigns are not.** Several systems' prototypes are attached tenant-wide, and a campaign resolves through the one its game system names. That resolution is a follow-up RFC.

## Open questions

1. **Do the systems' prototypes get a system root now?** Section 9 proposes that each system's repository gives its prototypes a common ancestor, so that a system's membership is ancestry and the follow-up needs no new tag. The cost is one more prototype per system, `D&D 5e` in B and its seed layer, and the top-level prototypes naming it as a parent. Nothing is published, so adding it now costs nothing and adding it later is a change to a published repository. Recommended: yes.

## Slices, if accepted

Each its own ADR, in this order:

1. **Attachments in copy and updates** (section 3): the rule, the copy-link table and migration, the planner, `repo updates`, purge, the response fields, and an end-to-end test of the stack tried here with a table that takes A1 first and C later, including an attachment whose parent is another repository's copy. It amends ADR 0119, 0120, 0121 and RFC 0024 A8.
2. **The seed's layers.** Sort the stat definitions and the categories into the four repositories (sections 5 and 6), add the system root (section 9) if it is wanted, bump the seed version, and extend `tests/e2e/test_split.py` to the four-repository stack.
3. **The importer's two passes** and the `part` in its map, and `repo contents` counting a repository's attachments.
4. **Rebuilding the local tenants**, and the setup walkthrough in the README.
5. **Later:** a single setup command, a command that takes an attached repository back off a tenant, showing on a table's item which repository each part of it came from, and **system-aware resolution** (section 9, its own RFC).

## Not in scope

- **Beings** (race, class). They would join the common repositories and a rules repository the same way, and they are a later question.
- **Settings.** A setting such as Faerûn is the same pattern on another axis (RFC 0024's own example) and isn't touched.
- **Live reads of a dependency.** Attachments travel by copy and by updates, never live.
- **Carrying stat values, names or descriptions written onto a copy.** Only the added parents travel.
- **System-aware resolution**: a campaign choosing among the systems a tenant holds. A follow-up RFC; section 9 only makes the data available.
- **What the SRD's licence allows** for text in a published repository. It is worth checking before anything is published, and it isn't decided here.
