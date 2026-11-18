# 0491 - Starters replace the seed

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C10 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Supersedes [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md), [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md),
[ADR 0166](0166-a-bare-seed-refuses-to-add-a-layer-to-a-tenant-that-holds-another.md), [ADR 0168](0168-lorenzo-unseed.md),
[ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md) and [ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md),
and the `seed --list` and per-layer half of [ADR 0169](0169-seed-list-and-repo-contents.md).

## Context

The seed is four layers (core, equipment, dnd5e, dnd5e-equipment) for RFC 0033's four repositories. It predates systems: D&D's groups
and stats take roles by name and so become neutral, `damage_dice_count` and `damage_die` are two ints, nothing creates a system row,
and the file cannot say a role, a bound, a dice type, a template, a feature or a formula kind beyond `contents` and `sum`. `unseed`
exists to take a layer out. Before launch there is no data to keep.

## Decision

- **Three starters**, library documents ([ADR 0484](0484-the-library-document.md)) that ship in the wheel:
  - **`neutral`**: the groups `physical` and `tags` (holding their roles) and `sourcebook`; `own_weight`, `weight` (role `weight`),
    `contents_weight`, `bundle_amount`, `height` (role `height`), `is_container` (role `is_container`), `is_consumable`, `is_magical`,
    `is_silvered`, `is_adamantine`, `sourcebook`; the weight recipe (`contents` and `sum`) on `physical-object`; the forms and materials
    (the equipment layer's 32 categories); the `unsorted` placeholder. Roles are set explicitly, never taken by name.
  - **`dnd5e`** (requires `neutral`): the system `dnd5e` on the root `dnd5e-system`; its groups and `dnd5e_`-prefixed stats, among them
    the six ability scores (1 to 30) and their modifiers (`linear`, half, minus five, floor), level (1 to 20) and the proficiency bonus by
    level (`select`), armour class from a base, a Dexterity modifier capped by the armour (`min`) and a shield, price in copper, range,
    weapon damage and versatile damage as `dice`, and the weapon properties; the 30 categories of the D&D layer under the root and the six
    parents it added to the equipment's forms; a character sheet template and a weapon template; a Fighter entry whose grant rule offers
    one fighting style of two. Content is from the SRD 5.1 under CC-BY-4.0, with its attribution in the document and in the README.
  - **`wrath-and-glory`** (requires `neutral`): the system `wg`; attributes (1 to 12) and skills (0 to 8) with their bounds; Tier and Rank;
    Defence, Resilience, Determination, Wounds, Shock, Resolve, Conviction, Passive Awareness, Influence and Wealth as formulas, armour
    from what is worn (`contents`, `max`, active only); a dice pool per skill (`sum` of the attribute and the skill) and its roll (`dice`,
    sides 6); weapon damage, extra damage dice and armour penetration; Wrath, Glory and Corruption; a character sheet template; an example
    archetype with a talent and a choice. Mechanics, numbers and stat names only: no rules text, setting text, keywords or names of the
    setting. Every value is marked for checking against the rulebook in review.
- **Applied to a repository and copied.** `lorenzo apply --starter dnd5e -t dnd5e-rules` writes it into a repository, which is published;
  libraries copy it and take its updates. Applying a starter straight into a library is for its own use.
- **Removed**: `lorenzo seed`, `--layer`, `seed --list` (now `lorenzo starter list|show`), `lorenzo unseed` (a library is wiped by
  deleting it, a system by `--prune` or deleting its rows), `builtin.toml`, the layer code and the bare-seed refusal.
- **The walkthrough** of RFC 0033 becomes: create a repository, apply `neutral`, import the neutral half of the gear, publish; create a
  repository, copy it, apply `dnd5e`, import D&D's half, publish; a table copies them. `tests/e2e/test_setup.py` follows it.

## Consequences

- A library gets D&D 5e or Wrath & Glory as a system with its roles, bounds, dice, formulas, templates and features, from a published
  repository, and a second system beside it without a collision.
- The starters are content to keep correct; their numbers are reviewed like code.
- Nothing is seeded by the API: a starter is a document a person chooses to apply.

## As built (slice C10)

- Three starters ship in `apps/cli/src/lorenzo_cli/starters/`: `neutral`, `dnd5e` (system `dnd5e`, root `dnd5e-system`) and
  `wrath-and-glory` (system `wg`). `dnd5e` requires `neutral` and attaches its Economic object to the neutral forms; every D&D
  stat is prefixed `dnd5e_`, and damage is one dice stat (`dnd5e_damage = "1d8"`) instead of a count and a die.
- `seed`, `unseed`, the `seed/` package and its tests are gone; `tenant create` points to `lorenzo apply --starter neutral`.
- The four published repositories are two: the equipment (`neutral` and the neutral pass) and the rules, which copy the equipment
  and add `dnd5e` and the system pass. `repo contents` no longer counts seed layers.
- The `wrath-and-glory` starter holds names and numbers only, checked against the core rulebook and its character sheets
  (2026-11-18): an attribute is a rating, a bonus and their total, which the skills and traits read; every trait but Corruption
  is at least 1, written as a `max` over a step stat (group `wg_steps`); armour's Bulk lowers Speed and Powered adds to
  Strength; a ranged weapon has three ranges; Glory is the group's pool, so no character holds it. A character starts with the
  book's values (attributes 1, skills 0, Speed 6, Average size, 2 Wrath).
