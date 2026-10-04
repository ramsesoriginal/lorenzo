# 0181 - The seed's four layers and a system root

Status: accepted

Numbered 0175 originally; renumbered to 0181 on merging `main`, which had independently claimed 0175-0180 for account-hub's ADRs in the meantime (the same collision as ADR 0068 and 0069).

The second slice of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md) (its sections 5, 6 and 9), decided with the maintainer on 2026-10-04. It amends [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) (the seed and its layers) and [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) (`dnd5e` as its own repository), and uses the attachments of [ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md). `seed`, `unseed`, `seed --list` and `repo contents` ([ADR 0166](0166-a-bare-seed-refuses-to-add-a-layer-to-a-tenant-that-holds-another.md), [0168](0168-lorenzo-unseed.md), [0169](0169-seed-list-and-repo-contents.md)) already work over a list of layers, so they follow.

## Context

The built-in seed has two layers: `core` (6 stat groups, 18 stat definitions, 33 categories, 2 recipes) and `dnd5e` (22 stat definitions, 28 categories). RFC 0033 makes four repositories of it: the neutral vocabulary (A0), the common equipment (A1), the D&D 5e rules (B) and the D&D 5e equipment, which attaches B's prototypes to A1's items (C). Each repository is seeded from one layer, so the seed needs four, and the stat definitions and categories have to be sorted among them **before anything is published**, since a definition can't be moved afterwards ([ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)).

Two things the seed can't say today: a prototype that carries a value (RFC 0033 §3, "Adding a group": a group is acquired by setting a stat in it), and an edge between two categories of different layers, which is what C is made of.

## Decision

### The four layers

Provisional in the RFC, named here. Each is **built on** the layers in its row, and may name their groups, definitions and categories and its own.

| Layer | Repository | Built on | Holds |
| --- | --- | --- | --- |
| `core` | A0, `core` | nothing | The stat groups `physical`, `sourcebook` and `tags`; the ten neutral definitions `own_weight`, `weight`, `contents_weight`, `bundle_amount`, `is_container`, `is_consumable`, `is_magical`, `is_silvered`, `is_adamantine` and `sourcebook`; the category `physical-object`; and the two weight recipes on it. |
| `equipment` | A1, `common-fantasy-eq` | `core` | The forms: the other 32 of today's core categories, from `weapon` and `armor` to the kinds of gear, and the materials. Bare slugs, as today. No groups or definitions. |
| `dnd5e` | B, `dnd5e` | `core` | The stat groups `economic`, `damaging` and `destroyable`; the thirty definitions: today's 22 and the eight D&D's that were `core`'s (`price`, `armor`, `armor_formula`, `strength_required`, `stealth_disadvantage`, `adds_modifier`, `range_normal`, `range_long`); the 28 categories and two new ones (below). Slugs start `dnd5e-`. |
| `dnd5e-equipment` | C, `dnd5e-common-eq` | `equipment`, `dnd5e` | Attachments only, for now (below). No groups, definitions or categories of its own: the D&D prototypes of single items, such as Longsword 5e, are the importer's, not the seed's. |

**Why they are sorted so.**

- A0 keeps what can be said of a thing in any system. The materials' tags (`is_silvered`, `is_adamantine`) are A0's, and the categories that use them are forms, so A1's.
- The eight stats are D&D's because their meanings are: a price in copper pieces, an armour class and what armour asks of its wearer, a range in feet. RFC 0033 §5 puts them in B.
- `destroyable` goes to B with `economic` and `damaging`: RFC 0033 names two of the three, and every stat that is in `destroyable` is one of the eight.
- B's tag definitions (`is_finesse` and the rest) stay in A0's `tags` group, which B has a copy of.
- The weight recipe stays with `physical-object` and the three weights it uses.

### A system root

B's layer gets a root prototype, **`dnd5e-system`**, named "D&D 5e", so that belonging to a system is ancestry and needs no new kind of tag (RFC 0033 §9). The five axis roots that are parentless today, `dnd5e-weapon-proficiency` (RFC 0033's Weapon Class), `dnd5e-armor-tier`, `dnd5e-tool-proficiency`, `dnd5e-weapon-property` and `dnd5e-spellcasting-focus`, take it as their parent, and so does the new Economic Object. A category is D&D 5e's if it has the root among its ancestors, and neutral if it has no system root among them. Existing slugs and names stay, so nothing already imported changes meaning.

**Slugs follow the layer**: a layer has a slug prefix, `dnd5e-` for both D&D layers and none for the other two, and a node's slug starts with it exactly when it is in such a layer. That is today's rule for `dnd5e`, kept for any system's layers.

### A prototype that carries a value

A category may set stat values, `stats = { price = 0 }`, written as a value on the node. The rule from RFC 0033 §3 is that a prototype adds a stat group by carrying a default for one stat in it, so:

- **`dnd5e-economic-object`, "Economic object (D&D 5e)"**, in B, under the root, carries `price` 0 (copper pieces) and so adds the `economic` group to everything that has it. A more specific category or the item sets a price of its own.
- **Weapon Class and the others carry no default.** A thing acquires `damaging` through the values its D&D prototype sets (the importer's second pass), not through a number made up for the category.

### Attachments in the seed

An entry `[[attachment]]` names a child category, a parent category and a layer: the parent is added to the child's parents when the child exists and doesn't have it. It is find-or-create like everything in the seed: an edge already there is counted as existing, nothing is removed, and the child's other parents are kept (the prototype set is read and replaced with one more, with the ETag the API asks for).

`dnd5e-equipment` holds six, **Economic object on `weapon`, `armor`, `tool`, `container`, `consumable` and `gear`**: the top-level forms of the equipment layer, which is the weapon of RFC 0033's example and the other things D&D gives a price. Not on `physical-object`, which is also a mountain and a door. In C, where those forms are copies of A1's and the parent is a copy of B's, each is an attachment in the sense of ADR 0172 and travels with C. Seeded into one tenant with every layer, they are ordinary edges.

### Validation

The seed file is checked when it is loaded, so a mistake is a test failure and never a half-seeded tenant:

- A definition's group, a category's parents and tags, a recipe's node and definitions, and an attachment's two categories are in the entry's own layer or one it is built on, never in a sibling's. An entry of `dnd5e` can't name one of `dnd5e-equipment`, nor one of `equipment`.
- Slugs follow their layer's prefix, and a stat value's name is a definition of its layer or one below, of the type its value has.
- File order is still a valid creation order: the categories are listed in layer dependency order (`core`, `equipment`, `dnd5e`, `dnd5e-equipment`), and within a layer a parent before its children. Groups and definitions are made all together before any category, so their order doesn't matter.

### The commands

- **`seed --layer`** takes any of the four. Without `--layer` it seeds every layer into one tenant, in that order, as it did for two: for a table's own use, with the note that they are meant to be separate repositories for publishing. A layer whose dependency the tenant lacks is a problem that says which layer to seed first, as today. The guard of ADR 0166, a bare seed of a tenant that holds some layers and not others, applies to four.
- **A layer counts as held** when the tenant has any of its categories or stat definitions, or, for a layer made of attachments, any of them.
- **`seed` prints attachments** as an action, `attach`, with the child, the parent and the layer, and `seed --dry-run` plans them.
- **`unseed --layer dnd5e-equipment`** takes the attachments out: the parent is dropped from the child's parents and nothing else of the child is touched. `unseed` of a layer whose categories the other layers' attachments point at (B's Economic object) is refused, as it is for any category something outside the layer inherits from, unless the layer whose attachments they are is taken out in the same call (`--layer dnd5e --layer dnd5e-equipment`), which removes the attachments first.
- **`seed --list`** lists each layer's attachments, and the system root and the values on a category.
- **`repo contents`** adds an `attachments` column to the layers table (present of the seed's), found by looking at the child's parents, so it counts a repository where they are ordinary edges as well as one where they are attachments. `--json` gains the same.
- **The seed version is 2.** The README's counts follow.

### Tests

- Unit tests: the four layers load; every entry sits in the layer the tables above say, with the counts; the validation refuses a sibling layer, a wrong prefix, an attachment whose child doesn't exist and a value of the wrong type; the plan finds attachments existing and missing and creates a category with its value; unseed's order and its refusal and its exception; `--list` and `contents` show the new column.
- An end-to-end test of the stack of RFC 0033 against the real API (`tests/e2e/test_split.py`, extended): A0 seeded and published, A1 over it seeded with `equipment`, B over A0 seeded with `dnd5e`, C over A1 and B seeded with `dnd5e-equipment`, and a table that took A1 first and C later, whose Weapon then has Economic object as a parent and `price` 0, with one Weapon in the table. And a bare seed of one tenant with all four layers.

## Not in this ADR

- **The importer's two passes** and what it writes into A1 and C, RFC 0033's third slice.
- **Rebuilding the local tenants** and the setup walkthrough, its fourth.
- **Resolving through a campaign's game system.** The root only makes the data available.
- **Other systems' seeds.** A second system takes `core` and `equipment` and brings its own two layers; what it names `economic` or `price` merges with B's on its first copy, which ADR 0119 allows when the types match.

## Consequences

- **A table can hold the equipment and add D&D later**, and what D&D adds to an existing item is in the seed, not in a script.
- **Nothing is published or granted**, so the move costs a seed version and a rebuild of the local tenants. A tenant seeded by version 1 still seeds under version 2, since everything is found by name and slug: its definitions stay where they are, its parentless axis roots are reported as "exists but is not under" the root and left, and the attachments are added. Starting over is cleaner and is what RFC 0033's fourth slice does.
- **`core` is small**: one category, ten stats and two recipes. That is what RFC 0033 asks for, and the forms are one `--layer equipment` away.
- **One default is a choice that can be changed**: `price` 0 on every priced form. It is a line in the seed, and the seed's version changes with it.
