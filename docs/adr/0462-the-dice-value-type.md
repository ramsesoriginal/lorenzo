# 0462 - The `dice` value type

Status: accepted, built (2026-11-13). Slice D1 of [RFC 0056](../rfcs/0056-dice-values.md). Adds a value type to what
[ADR 0014](0014-stats.md) and [ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md) define. How a stat resolves does not
change ([ADR 0037](0037-effective-stat-resolution.md)).

## Context

A dice expression is three stats by convention today (a count, a die, a type), and nothing can say "four six-sided dice without the
lowest". One stat should hold it, in the notation tables use, in English or German, and every read, copy and release should carry it.
Lorenzo states dice; it never rolls them.

## Decision

- **A value type `dice`** beside `int`, `float`, `text`, `bool` and `enum`. A definition of it takes no unit, scale or enum values: a
  scale and enum values are refused as for `text` (the existing 422s), and a unit is a 422 `invalid-dice`. As for every type, a
  definition's type does not change.
- **Stored as parts**, in four nullable columns of `entity_stat` next to the other value columns: `dice_count`, `dice_sides`,
  `dice_drop_mode` (`lowest`, `highest`) and `dice_drop_count`. The "exactly one value is set" check counts `dice_count` as the fifth
  alternative, and a second check holds the parts together (a count with sides, a mode with a count, count 1 to 100, sides 2 to 1000,
  a drop from 1 to count minus 1).
- **The notation**, case-insensitive, spaces around the whole value ignored: `[count] (d|w) sides [d [l|h] number]`. `W` is accepted
  for the die marker only; the drop marker is `D` alone. A bare `d` before the number drops the lowest (`4d6d1` is `4d6dl1`). The
  **canonical form** is lowercase `d`, the count left out when it is 1, and an explicit `dl` or `dh`: `d20`, `2d6`, `4d6dl1`,
  `4d6dh1`. A value written in any accepted form is read back in the canonical one.
- **Writing.** `PUT /entities/{e}/stats/{d}` takes the notation, `{"value": "4W6DL1"}`, or the parts,
  `{"value": {"count": 4, "sides": 6, "drop": {"mode": "lowest", "count": 1}}}`. Anything outside the limits, or that is not dice, is
  a 422 `invalid-dice` whose detail begins with the part that failed (`notation`, `count`, `sides` or `drop`). A number, a boolean or
  the parts given to a stat of another type, and a number or boolean given to a dice stat, are the 422
  `invalid-stat-value-type` they were. The tag routes and relationship standings are not changed; a relationship standing takes the
  notation like any string.
- **Reading.** `value` of a dice row is the canonical notation, a string, in every read that carries a stat row: the entry read, the
  effective-stats grid, the explanation, the copy of an item's stats, the export. A row of a dice stat also has `dice`, the parts
  (`count`, `sides`, `drop` as `{mode, count}` or null); a row of any other type has no `dice` key at all (`exclude_if` on the field),
  so no existing answer changes. `previous` of a write is the canonical notation too, so undoing a write is putting it back.
- **A dice value is not a number.** A numeric formula refuses a dice source as it refuses `text`, and no formula produces a dice value
  yet (D2 reads one, D3 builds one).
- **Copy, update, release.** A copy brings the four columns; an update finds a changed value as one field `stats:<definition>` whose
  `base` and `upstream` are the notations (clean or conflicting as for any value) and applies it as parts; the release document is
  format 46, whose stat value has the four columns, and a document of format 45 or older reads as holding none. Merging identical
  pieces compares dice values.
- **The view.** `v_effective_stat` carries the four columns, appended last (as `source_entity_id` was), so `CREATE OR REPLACE VIEW`
  accepts it and `v_item` and `v_item_instance` are untouched. The rule that picks the winner is not changed.

## Design

`dice.py` holds `Dice` (a frozen value: count, sides, drop mode and count), `parse`, `from_parts`, `of_row` and `columns`, with
`InvalidDice(part)`. The write route normalises every accepted form to the canonical notation before it compares with the previous
value (a write of the same dice in another spelling moves nothing) and stores parts. The evaluated value of a dice stat is its
notation, so the evaluation, the explanation and the templates carry a string and need no new type; `dice_out` makes the parts of a
row from it. The migration adds the enum member, the columns and the two checks and replaces the view; its downgrade restores the view
with the columns as nulls (a view cannot lose a column while others are built on it) and removes the rows that hold a dice value.

## Validation and delivery

Tests: every accepted form and its canonical reading, each rejected form naming its part, the limits for the notation and for the
parts; a write in each form read back by the entry, the grid and the explanation, an inherited value, `previous`, the row after an
overwrite; a stat of another type having no `dice`; the type mismatches in both directions; a definition without a unit, scale or enum
values; a formula refusing a dice source; the table's checks; a copy and an update through a repository; the document of format 45.
The OpenAPI change is `dice` among the value types and the request `value` taking the parts, recorded in
`openapi-breaking-accepted.txt` with this RFC as the reason; the CLI models and `packages/api-client` are regenerated.

## Not in scope

Reading a dice value in a formula and building one from stats (D2, D3), the link preview and the text chip (D3), rolling, a flat
modifier in the notation, and anything in an app or the command line.

## Consequences

- A weapon's damage can be one stat that reads `1d8` or `4d6dl1`, in the notation people write; the three-stat convention stays valid
  and the seed is not touched.
- A sixth value type for every read, copy and release to carry, and a fifth alternative in the stat table's constraint.
- The same dice in two spellings are the same value everywhere: a write, a merge and an update compare the canonical notation.
