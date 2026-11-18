# 0490 - The importers move under `lorenzo import`

Status: accepted (2026-11-17), decided with the maintainer, not built. Slices C3 (the commands) and C10 (the names and parts) of
[RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md). Supersedes [ADR 0182](0182-the-importers-two-passes-neutral-and-system.md)'s
rule that a part is a seed layer's; amends [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) (names), [ADR 0193](0193-lorenzo-inventory-import-and-export.md)
and the calendar commands (names).

## Context

The MPMB importer holds the top-level `plan`, `apply` and `inspect`, which the library document needs ([ADR 0484](0484-the-library-document.md)).
Importing and exporting are spread over `plan`/`apply`, `inventory import|export` and `calendar import|export`. The importer decides
whether a stat or category belongs to the neutral or the system half of an item by the seed layer it came from, and writes D&D's
values to stats named before the prefix rule and the dice type.

## Decision

- **Commands**: `lorenzo import mpmb plan|apply|inspect`, `lorenzo import inventory FILE`, `lorenzo import calendar FILE`,
  `lorenzo export inventory`, `lorenzo export calendar SOURCE`. Their options and exit codes stay, under the write contract
  ([ADR 0482](0482-one-write-contract-for-every-cli-command.md)). `lorenzo export SYSTEM | neutral` is the document's.
- **Parts by system, not by layer.** A stat is the system half's when its group has a system, and neutral otherwise; a category is the
  system half's when it is under a system's root. `--part neutral|system` stays; `--system SLUG` names the system the system pass writes
  for and is required with `--part system` when the library has more than one. A map row's `part` is allowed only where the library does
  not decide (text, and stats or parents it does not have).
- **Names follow the `dnd5e` starter** ([ADR 0491](0491-starters-replace-the-seed.md)): D&D's stats are `dnd5e_`-prefixed; a weapon's
  damage is one `dice` value (`dnd5e_damage`, `1d8`) and its versatile damage another, not a count and a die; the map's `int` rows for dice
  become `dice`. The neutral stats keep their names (`own_weight`, `sourcebook`, `bundle_amount`). A library that lacks a stat the map
  names is a problem the plan names, with the starter to apply.
- The inventory importer's placeholder for a player's own item is the neutral starter's `unsorted` entry, and its advice names
  `lorenzo apply --starter neutral` instead of `seed --layer core`.

## Consequences

- `lorenzo plan` and `apply` mean one thing, the document; importing is one group with one habit.
- Which half of an item a value belongs to follows the library's systems, so a second system's importer needs no layer of its own.

## As built (slice C10)

- The MPMB importer reads its vocabulary from the `neutral` and `dnd5e` starters (`importer/vocabulary.py`) instead of the seed:
  a stat is the system's part when its group has a system, a category when it comes from the `dnd5e` document. The review queue
  records a digest of the two starters as its version.
- `builtin_map.toml` writes the `dnd5e_` stats; a versatile weapon's two-handed damage is a dice value (`1d10`).
- A library without the starters' stats is refused with the commands that add them.
- Found while building it: a validation error from the API now names its fields in the message, and a formula read back keeps the
  fields its kind requires (a linear formula's multiplier of 1 was dropped, from slice C6).
- MPMB's ways of working out armour class (2026-11-18): the map's new disposition `armor-class-way` (the armour list's `firstlist`
  and `magic`) makes an entry a feature under `dnd5e-armor-class-features`, created as an entry of the kind `feature` in the system
  pass (or a run without `--part`) and never attached to a neutral item; its tag comes from its `ac` (`10+Con`, `10+Wis`, `13`, or a
  natural number with `dex` -10). Armour with a formula AC stays an item and carries the tag.
