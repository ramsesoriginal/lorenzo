# 0463 - The `dice_value` formula

Status: accepted, built (2026-11-13). Slice D2 of [RFC 0056](../rfcs/0056-dice-values.md). Builds on
[ADR 0462](0462-the-dice-value-type.md) (the `dice` value type), [ADR 0104](0104-computed-stats.md) (formulas) and
[ADR 0445](0445-product-and-ratio-formulas.md) (a quotient at 28 digits). How a stat resolves does not change
([ADR 0037](0037-effective-stat-resolution.md)).

## Context

A dice value is not a number, so a numeric formula refuses it. A library still wants the numbers a dice value stands for: the least
a weapon can do, the most, what it does on average, to add a bonus to, compare against or show next to the notation.

## Decision

- **A formula kind `dice_value`**, `{"kind": "dice_value", "source_stat_definition_id", "as", "round_mode"}`: a number read from a
  `dice` stat of the same entry. `as` is `min`, `max` or `average`; `round_mode` is as for every formula (default `none`).
- **What it reads.** For `count` dice of `sides` sides with a drop of `z`: the minimum is the dice that are kept (`count - z`), the
  maximum those times `sides`, and the average the exact expectation of the kept dice, from the order statistics of the dice
  (`d20` 10.5, `2d6` 7, `4d6dl1` 15869/1296). The average is computed in whole numbers over `sides ** count` and made one fraction, memoised by value, so a drop
  of `100d1000dl50` costs a fraction of a second once and nothing after. It is divided at 28 digits, as a ratio is, then rounded by the
  mode.
- **Types.** The source must be a `dice` stat, and the target an `int` or `float`; anything else is a 422 (`invalid-computed-stat`).
  An `int` target needs a rounding mode other than `none` for an `average`, as it does for a ratio: whether an average is whole
  depends on the dice the entry holds, which a write cannot see, so `none` is refused for it (a `min` and a `max` are always whole
  and take `none`). The result is `float` for a `float` stat.
- **No value** when the dice stat has none, as for every formula; a value that is not dice (data written around the API) gives none.
- **The API.** `as` is the field's name in the body (`as_` in the schema, as `from` is for a select step). The kind joins the
  `formula` union of the formula routes, the preview, the explanation (whose `inputs` show the source's notation), the dependents
  route (`kind: dice_value`) and the delete guard of a stat (a dice stat a formula reads is a 409 until the formula goes).
- **Where it is stored.** One table, `computed_stat_dice_value`, keyed and cascading like `computed_stat_linear`, with tenant isolation,
  repository read and `FORCE ROW LEVEL SECURITY`; one line in `copyable_tables.py` (repository content, carried by `computed_stat`).
- **Copy, update, release.** A copy brings the row, its source re-pointed to the library's own stat; the update engine finds a change
  of `as` or `round_mode` as one change of the formula and applies it; the cycle check counts its edge; the release document is format
  47, whose formula has `read_as` (null for every other kind), and a document of format 46 or older reads as holding none.

## Design

`DiceValueFormula(source_stat_definition_id, read_as, round_mode)` in `stat_evaluation.py`, evaluated by `apply_dice_value` from the
source's notation (parsed by `dice.parse`); `Dice.minimum`, `maximum` and `average` in `dice.py`. A test counts every roll of small
dice and compares it with the average, for drops of the lowest and of the highest.

## Validation and delivery

Tests: the three readings of `d20`, `W20`, `2d6`, `4d6dl1` and `4d6dh1` against exact fractions; the four rounding modes of `d20`'s
average on an `int`; no value without dice and the value following the dice; the formula read back with `as`, explained and previewed;
each refusal (a source that is not dice, a target that is not a number, `average` on an `int` with no mode, an unknown `as`, no `as`);
the dependents route and the delete guard; the kind replaced by another and back; the average against a count of every roll and the
cost of the largest dice; a copy and an update through a repository; the release document at format 47 and 46. The OpenAPI change is a
member of the formula union and of the dependents' `kind`; the CLI models and `packages/api-client` are regenerated.

## Not in scope

Building a dice value from stats (D3), the link preview and the text chip (D3), a flat modifier, rolling.

## Consequences

- "What is the most this weapon does?" and "what does it do on average?" are numbers a formula, a comparison or a sheet can use, and
  they follow the dice when the dice change.
- An average that is not whole needs a rounding mode on an `int`, so the author says which way it goes.
- One more kind in the formula union, each a place a rule can be wrong.
