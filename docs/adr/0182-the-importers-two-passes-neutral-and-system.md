# 0182 - The importer's two passes: neutral and system

Status: proposed

The third slice of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md) (its section 6), tracked in [#432](https://github.com/ramsesoriginal/lorenzo/issues/432). It builds on the seed's four layers ([ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md)) and on attachments ([ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md)), and amends [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) (the mapping, identity, plan and apply) and [ADR 0146](0146-a-richer-item-taxonomy-and-keeping-what-the-sheet-says.md) (what the sheet's attributes become).

## Context

An MPMB sheet is D&D data, and `lorenzo apply` writes all of it into one tenant: each item with its neutral facts (a name, a weight, its forms) and its D&D ones (a price, dice, a proficiency, properties) together. RFC 0033 puts them in two repositories, so that a table can take the common equipment alone and add D&D to the same items later: the **neutral** half is the equipment repository's (A1) and the **system** half is the bridge's (C), which holds a copy of A1 and attaches D&D's prototype to A1's item.

The map already says what each sheet value *means* (ADR 0144, 0146), and the seed says whose each stat and category is (ADR 0181). What is missing is the importer writing the halves apart, as two passes over the same files that can each be re-run.

## Decision

### Two parts

| Part | What it is | Of a weapon, for example |
| --- | --- | --- |
| **neutral** | True anywhere | its name and other names, the sourcebook citation, its weight, its forms (weapon, melee, a blade), its materials |
| **system** | D&D's | its proficiency and properties, damage dice and type, range in feet, ability, the price, its `description` (a property list that gives the versatile die) and `tooltip` (its special rules) |

A pack's contents, a plain item made for one of its entries and a gear item's kind (container, clothing) are neutral; the price of any item, the armour numbers, and the proficiency of a tool or a focus are the system's.

### What decides a part

The part is a property of **what is written**, not of the row that writes it, because one rule writes both (`range` gives `melee-weapon` and `ranged-weapon`, and `range_normal` and `range_long`; `name_and_price` gives a name and a price). So the draft of an item is made as it is today and then **divided**, and no rule is split.

- **A stat** has the part of its definition's layer in the seed ([ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md)): `core` is neutral, `dnd5e` is the system's. In general, a layer with a slug prefix is a system's.
- **A parent category** has the part of its node's layer: `core` and `equipment` are neutral, `dnd5e` is the system's. A category a map row mints (`create-under`) has the part of its axis, which `mapping.py` already knows: `proficiency`, `tier` and `property` are the system's, `form` and `material` are neutral.
- **Everything else a row writes**, which no layer decides (a description, an information entry, other names, a pack's contents), and a stat or a parent the seed doesn't know, has the part the row gives with **`part = "neutral" | "system"`**, and neutral when it gives none. Attribute rules (in their table form), classification rows and name rules take it. Where the seed does decide the part, a `part` on the row is a map error, so a map can't say what the seed contradicts.

The built-in map (version 2) needs it twice: a weapon's `description` and its `tooltip` are `part = "system"`. Nothing else in it does.

### The passes

`lorenzo plan` and `lorenzo apply` take **`--part neutral|system`**. Without it they write both halves onto one item, as they always have, for a repository that isn't going to be split; the two-pass flow is for publishing one, and the existing one-tenant flows and their tests stay as they are.

**The neutral pass** creates the item under its neutral parents (the forms, the materials, the kinds of gear) with its neutral stats, its description, its other names and, for a pack, its contents, and `sourcebook` last, as before. `--public-catalog` is the neutral pass's, as the RFC has it. It needs only the `core` and `equipment` layers of the seed.

**The system pass**, for each item that has something of the system's:

1. **finds the item by its neutral slug in the tenant's own copy of the equipment**, computed from the same map by the same rule as the neutral pass, so the two agree. An item that isn't there is held with that reason and a way out (run the neutral pass; take it from the equipment repository), and nothing is written for it.
2. **creates a prototype** named for the item and the system, "Longsword (D&D 5e)" (the label is `[system] label` in the map), with a slug in the system's namespace, the system's parents (its proficiency, its properties), `in_public_catalog` false, the system's stats with their groups acquired (ADR 0142), and the system's description and information, titled with the prototype's name (ADR 0165);
3. **appends the prototype to the item's parents** when it isn't there yet: it reads the item and replaces its prototype set with the old one and one more, with the ETag, as the seed does for its attachments. That is **last**, and it is what says the item is done. In the bridge the item is a copy of the equipment's, so the edge is an attachment (ADR 0172) and travels with the bridge.

An item with nothing of the system's (ammunition) is skipped by this pass, with that reason. A pack is an item like any other: the prototype carries its price. `--public-catalog` with `--part system` is a usage error: a prototype is never public.

The two passes can be run in either repository that has what they need, in order, and in one tenant that is seeded with every layer: the result there is the same graph as the split one, with the attachment an ordinary parent.

### Identity, and a second run

- **Neutral** slugs are ADR 0144's, `basic-weapons-longsword`. **Prototype** slugs are `<system namespace>-<list>-<key>`. The system namespace of a file is `[system_namespaces]` in the map (file name to namespace, like `[namespaces]`); where it has none, `srd5e` when the file's neutral namespace is the default `basic` (the sheet's own SRD data), and otherwise the neutral namespace and `-5e` (`hb-alice-5e`). Collisions take a suffix as in ADR 0144.
- A prototype's status is ADR 0144's. **`complete`** is a prototype that exists but isn't attached yet: the next run writes what it lacks and attaches it, the attachment being the marker, last, as `sourcebook` is the neutral item's. **`exists`** is one that is attached. A second run of either pass finds what the first made, writes only what is missing, and checks the item's parents before it appends, so nothing is attached twice.
- The run manifest keeps the system pass under its own keys (`system:weapons:longsword`), so a tenant holding both passes' items doesn't confuse them.
- **Held**: an issue holds an item back in the pass that needs what it couldn't read. A price that can't be read holds it in the system pass, and its neutral half imports; a weight that isn't a number holds the neutral pass. A classification value that no row knows holds the item in **both** passes, since it can't be said whose parents the row will give, until a row answers it. The review queue and the proposed map are as before and say the part.
- **Re-parenting** (`--reconcile`) replaces only the parents the importer manages (the seed's categories and those a row mints) and keeps the rest. It never takes the attached prototype off an item, nor a parent an author added, in either pass; today's equality of parent sets would flag every attached item forever.

### What `plan` and `apply` show

The header says the part ("neutral", "system", or "both halves on one item"), and `--json` has `part` (`"neutral"`, `"system"` or `"all"`). Counts and statuses are per pass. A held item says which pass held it.

### The map

Additive, so a map file written before this one is still valid: `part` on a rule, a classification row or a name rule; `[system_namespaces]`; `[system] label`. The built-in map is version 2.

## Not in scope

- **The seed and the layers** (ADR 0181), and **`repo contents` counting attachments** (ADR 0174): both exist.
- **Rebuilding the local tenants and the setup walkthrough**: the fourth slice, [#433](https://github.com/ramsesoriginal/lorenzo/issues/433).
- **Text written rather than imported.** A1's descriptions of weapons are not in the sheet; the neutral pass writes none for them.
- **Systems other than D&D 5e.** The division is by layer, so a second system's seed and map give it its own, but the built-in map is D&D's.
- **Moving an item imported both-halves-in-one into the split shape.** Don't mix the modes in one tenant: a system pass over an item that already holds its D&D values makes a prototype that its own values then beat.

## Consequences

- **Two entities per D&D item in a split stack**: the neutral one, and a prototype that is attached to it, which a table that took the equipment first gets when it takes the bridge (RFC 0033 section 2).
- **Nothing existing changes without `--part`**, so the README's one-repository flow, the importer's tests and every tenant imported so far are as they were.
- **The neutral slug is what ties the passes together.** It is computed in each tenant against what that tenant holds under the base slug, so it differs between two tenants only if one holds the base slug for something that isn't an item; the system pass then reports the item as not found, which is the safe failure.
- **A map row has one more thing to say**, a part, only where the seed can't say it.
- **Prototypes are never public**, so a player lists the neutral items and a GM, in the whole catalog, sees the prototypes too ([ADR 0073](0073-item-prototype-graph-inspection-and-bulk-editing.md) narrows by prototype).

## Tests

- **Unit**: the division of every attribute rule and every classification row of the built-in map into the two parts, from a sample entry of each list, and that the halves together are the draft that is written today; the part of a stat, a parent and a created category; a `part` the seed contradicts is a map error, and a `part` where the seed has no say works; a prototype's slug and namespace; the neutral slug the system pass computes equals the neutral pass's; a price that can't be read holds only the system pass, and an unknown classification value holds both; an item with nothing of the system's is skipped; re-parenting leaves an attached prototype; `--public-catalog` with `--part system` is refused.
- **End to end against the real API**: the equipment repository takes the neutral pass and is published, the bridge copies it, takes the system pass and is published, and a table that took the equipment first and the bridge later has one Longsword that is public, with the prototype as a parent and the damage, the price and the proficiency by inheritance; the system pass before the neutral one holds every item with the reason; a second run of each pass writes and attaches nothing; a pack has its contents in the equipment and its price from the bridge; and the one-tenant flow without `--part` is unchanged.
