# 0464 - The `dice` formula, and what a dice stat prints in a preview and a chip

Status: accepted, built (2026-11-13). Slice D3 of [RFC 0056](../rfcs/0056-dice-values.md), the last. Builds on
[ADR 0462](0462-the-dice-value-type.md) (the `dice` value type), [ADR 0463](0463-the-dice-value-formula.md) (`dice_value`),
[ADR 0104](0104-computed-stats.md) (formulas) and [ADR 0264](0264-link-previews.md) (the card of an entry). How a stat resolves
does not change ([ADR 0037](0037-effective-stat-resolution.md)).

## Context

A library that holds `damage_dice_count` and `damage_die` keeps them, and wants a `damage` dice stat made from them on its weapon
prototype, with nothing migrated. A dice stat should also be what a card and a text show for a damage line.

## Decision

- **A formula kind `dice`**, `{"kind": "dice", "count_stat_definition_id" | "count_constant", "sides_stat_definition_id" |
  "sides_constant"}`: a dice value built from a count and a number of sides, each a stat of the same entry or a constant, exactly
  one of the two for each (422 otherwise). A constant count is 1 to 100 and a constant number of sides 2 to 1000. A drop is not part
  of this kind: a computed stat is `count` and `sides`, and a drop is written as a value ([RFC 0056](../rfcs/0056-dice-values.md)
  section 5).
- **Types.** The target must be a `dice` stat and each stat it reads an `int` stat (a count is whole); anything else is a 422
  (`invalid-computed-stat`). Every other kind still refuses a dice target, and a select, which was missing from its table of targets,
  now says so (a 422, [ADR 0462](0462-the-dice-value-type.md)).
- **The result** is the dice, `3d8` for a count of 3 and 8 sides and `d20` for one die, read as any dice value is (the canonical
  notation, with `dice` beside it). It has **no value** when a stat has none, and none when a stat holds a number the dice cannot
  have: a limit on a constant is a 422 at the write, but a stat's own number is only known at the read, and a read does not fail.
- **It composes.** `dice_value` reads the dice a `dice` formula built, so an average or a maximum follows a count that follows a level.
  The cycle check counts the edges of both stats.
- **The API.** The kind joins the `formula` union of the formula routes, the preview, the explanation (whose `inputs` are the stats it
  reads), the dependents route (`kind: dice`; a stat is a dependent as the count or as the sides) and the delete guard of a stat.
- **Where it is stored.** `computed_stat_dice`, keyed and cascading like `computed_stat_linear`, with checks (one count, one sides,
  the limits of the constants), tenant isolation, repository read and `FORCE ROW LEVEL SECURITY`, and one line in
  `copyable_tables.py`. A copy re-points the two stats; the update engine finds a change of either as one change of the formula;
  the cycle check counts it; the release document is format 48, whose formula has `count`, `count_constant`, `sides` and
  `sides_constant` (null for every other kind), and a document of format 47 or older reads as holding none.
- **The link preview and the text chip need no code.** A dice stat's value is its notation in every read ([ADR 0462](0462-the-dice-value-type.md)),
  so the card of an item (whose template names a stat `damage`) already prints `2d6` for a dice stat of that name, and the `{damage}`
  chip of [ADR 0252](0252-lorenzoscript-stats-in-text.md), which shows the value of the entry's detail, shows the same string. A
  test holds the card; an app that draws the value says `2d6`, and one that wants the parts has `dice` beside it.

## Design

`DiceFormula(count_stat_definition_id, count_constant, sides_stat_definition_id, sides_constant)` in `stat_evaluation.py`, evaluated by
`apply_dice` with `dice.from_parts`, which holds the limits once for the notation, the parts and the formula.

## Validation and delivery

Tests: dice from stats, from a stat and a constant, from constants, following the stats; each number the dice cannot have giving no
value; a missing stat giving none; `dice_value` over built dice; preview, explanation, dependents and the delete guard; each refusal
(a target that is not dice, a source that is not an int stat, none or both of a stat and a constant, a constant beyond its limit);
a dice formula against an own dice value (409, as every formula); the card of an item; a copy and an update through a repository;
the release document at format 48 and 47. The OpenAPI change is a member of the formula union and of the dependents' `kind`; the CLI
models and `packages/api-client` are regenerated.

## Not in scope

A drop in the formula, a dice value from a formula of another type (a `text` read as dice), a flat modifier, rolling; drawing, editing
or rolling a dice value in an app or the command line; a `damage` dice stat in the seed.

## Consequences

- A library keeps its three stats and gains a `damage` that says `3d8`, from the count and die it already has, with nothing migrated.
- RFC 0056 is built: a value, two formula kinds, and the notation in every read.
- One more kind in the formula union; a count a stat holds beyond the limits is a missing value, not an error.
