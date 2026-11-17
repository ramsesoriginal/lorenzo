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
  ([ADR 0482](0482-one-write-contract-for-every-cli-command.md)). `lorenzo export SYSTEM | --neutral` is the document's.
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
