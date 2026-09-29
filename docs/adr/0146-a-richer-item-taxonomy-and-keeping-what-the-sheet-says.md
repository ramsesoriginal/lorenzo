# 0146 - A richer item taxonomy, and keeping what the sheet says

Status: accepted

A follow-up to [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) after its six slices ([ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md), [0144](0144-lorenzo-import-mapping-identity-plan-apply.md), [0145](0145-pack-contents-in-the-description.md)), asked for by the maintainer while reviewing them.

## Context

Three things about the first import were poorer than the graph it writes into:

1. **The hierarchy was thin.** Weapons were `melee-weapon` or `ranged-weapon` plus `martial` or `simple`; "firearm" was a value beside ranged, not a kind of it; there was no exotic weapon, no family (blade, axe, hammer, bow…), and none of the properties the rules give a weapon (finesse, heavy, light, reach, thrown…). Gear was one node. But the graph is multiple inheritance, and an item's view shows the descriptions its prototypes carry, and the items that have a prototype are listed on it. A property that is a category can say what it means once, apply its stats to every weapon that has it, and answer "which weapons are heavy" without a table.
2. **Information was dropped.** `nameAlt`, `ability`, `abilitytodamage`, `ammo`, `special`, `tooltip`, `strReq`, `stealthdis`, `addMod`, `isMagicAmmo`, `alternatives`, `dc`, `baseWeapon`, the two-handed damage die and the amount of a bundle were all discarded, though the stat system and the information/payload model exist to hold exactly this.
3. **A pack entry that was not an item stayed text.** An alms box in a pack could not be given with the pack, since a line without a link has nothing to create.

## Decision

### The taxonomy (`builtin.toml`, 61 nodes, 40 definitions)

Core layer (rules-neutral):

- **Weapon families** under `weapon`, apart from melee/ranged: `blade`, `axe`, `hammer`, `bludgeon`, `spear`, `polearm`, `whip`. **`bow`, `crossbow`, `sling` and `firearm` are children of `ranged-weapon`**, so a firearm is a ranged weapon by inheritance and needs no second parent.
- **`consumable`** (tag `is_consumable`), with **`ammunition` beneath it**.
- **Kinds of gear** under `gear`: `clothing`, `climbing`, `nautical`, `lighting`, `writing`, `camping`, `tack`, `medicine`. An item may be several at once (a torch is a consumable and lighting).
- **Materials**, a mixin axis of their own: `silvered`, `adamantine`, each a tag.

`dnd5e` layer:

- `exotic` and `improvised` beside `simple` and `martial`.
- **Weapon properties** as a mixin axis under `dnd5e-weapon-property`: finesse, heavy, light, loading, reach, special, throwable, two-handed, versatile, and uses-ammunition. Each has a **tag** (a bool stat, so it can be searched and inherited), and a **public description** in the rules' words. The spellcasting focuses (arcane, druidic, holy symbol) are a mixin axis the same way.

A node may now carry a `description` in the seed; `lorenzo seed` writes it as the node's public description when the node has none (an action of its own, so a seeded tenant from before this gets the descriptions on the next run, and one edited by a person is left alone).

### Recognising them

- **A row can name several parents**, and an attribute can feed **more than one rule** (`description` gives both the description text and the versatile die).
- **Text rules** (`[[name_rule]]`) read any attribute (the name by default) and match with `starts_with`, `contains` or `words` (whole words; a hyphen is part of one, so `two-handed` is a word). **All matching rules apply**, except that rules sharing a `group` apply only once (the first): a crossbow is not also a bow, though it has the word in it. The families are one group, in order.
- The properties are read from the weapon's `description` (the sheet writes `Finesse, light, thrown`); materials and gear kinds from the name and the sheet's own `type`.
- **Reach follows the graph.** A weapon must come out melee or ranged; the check looks at its parents and their ancestors, so a bow, a firearm and a sling satisfy it without being told.

### Keeping what was dropped

| Sheet | Lorenzo |
| --- | --- |
| `nameAlt`, unused name variants, `alternatives` (patterns are not names) | an information entry, type `alias`, "Also known as", one name a line |
| `tooltip` | an information entry, type `note`, "Special rules" |
| `ability` 1–6 | text stat `attack_ability` (Strength…Charisma) |
| `abilitytodamage`, `dc`, `monkweapon`, `isNotWeapon`, `stealthdis`, `addMod`, `isMagicAmmo` | bool stats or property tags |
| `ammo` | text stat `ammo_type` (the property `uses-ammunition` comes from the description's word "Ammunition": a thrown flask names itself as its ammo and is not a launcher) |
| versatile die | int stat `damage_versatile_die` |
| `baseWeapon` | text stat `base_weapon` |
| `strReq` (0 means none) | int stat `strength_required` |
| `ac` as a formula | text stat `armor_formula` (the number stays `armor`) |
| `amount` of a bundle (1 means none) | int stat `bundle_amount` |

The transforms are `ability_name`, `aliases` and `information`, and `int` takes a `minimum`, so an empty or meaningless value writes nothing. Information entries are written once, beside the item, before the `sourcebook` marker (so an interrupted run still counts as unfinished), and an entry of that type already there is not written again.

### Pack entries that are not items become items

An entry no gear entry answers to is now made a **simple plain gear item** (`gear`, key = its lower-cased name, slug `<namespace>-gear-<key>`, one per name however many packs mention it, weight from the pack if it gives one), so every line of a pack links and the pack can be given complete. A row in `[pack_items]` can say `"item"` (the SRD's seven: alms box, censer, vestments…) and then nothing is reported; a name the map and the sheet do not know is made an item **and reported**, as before, with the row to add, so it can be linked instead. `"text"` remains for things that are truly not items. If a gear entry already has that key it is linked instead of duplicated. Resolution is two-phase because the plain items' slugs exist only after every item has one.

The plan's `pack.plain_text` is renamed `pack.unresolved`, since these entries are no longer text.

## Consequences

- A weapon's view now shows what its properties mean, and a property lists the weapons that have it (`instances` on the property node); `GET /items` filtered by the property's prototype answers "all heavy weapons" through descendants.
- The seed grew from 12 to 40 definitions and from 22 to 61 nodes, and `seed` has a fourth action kind. The change is additive for a tenant seeded before; `seed` finds or creates by name and slug as before.
- The parents of an imported item change (`plate` and `longsword` have more). An already imported item keeps its parents unless `--reconcile` is given, as before.
- A tenant that was imported with the old map gets the new parents and information only through `--reconcile` and a re-run; nothing is rewritten silently.
- The matching is by English words in a name or description. A homebrew sheet in another language gets no families, and says so by its items being plain, not by guessing; a project map can add rules.

## Alternatives considered

- **One flat "properties" text stat.** Simple, and unsearchable; nothing to inherit, describe or link to.
- **Properties as tags only, without nodes.** Searchable, but no description to show and nothing to attach shared stats to.
- **Dropping unmapped attributes silently, as before.** Rejected; the maintainer's point is that the stat and information models exist to hold them.
- **Leaving non-item pack entries as text.** Rejected; a pack you cannot give complete is not useful at the table.
