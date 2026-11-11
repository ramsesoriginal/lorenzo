# 0445 - `product` and `ratio` formulas

Status: accepted, built (2026-11-11). Slice K2 of [RFC 0053](../rfcs/0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md).
Builds on [ADR 0444](0444-min-max-and-a-bool-or-an-enum-as-a-number-in-a-formula.md) (a `bool` and an `enum` as numbers,
and the way a kind is added), [ADR 0126](0126-sum-formulas.md) and [ADR 0104](0104-computed-stats.md).

## Context

A product of two stats and a quotient of two stats had no kind: hit points from level times the average of a die were stored by
hand, a bonus that applies when a flag is set needed a trait entry carrying a formula, and an average or a rate could not be
said at all.

## Decision

- **`product(factors, multiplier, offset, round_mode)`.** Two to five stats of the same entity multiplied, then times a
  constant, plus an offset, rounded as `sum` rounds. A stat may be a factor twice (`level x level`). A `bool` is a factor of
  1 or 0 and an `enum` its `sort_order` (ADR 0444), so a flag as a factor switches a term. Body:
  `{"kind": "product", "factors": [stat ids], "multiplier": 1, "offset": 0, "round_mode": "none"}`.
- **`ratio(numerator, denominator, multiplier, offset, round_mode)`.** A stat divided by a stat or a constant, exactly one of
  the two, times a constant, plus an offset. A stat with no value, or a zero denominator, gives no value, as an unset input
  does; a constant 0 is refused at write. The quotient is rounded at 28 digits, Python's default, before the multiplier,
  the offset and the mode apply, and the stat explanation says so when it did: `division_rounded` is true when the division
  lost digits and false when it did not (null for any other kind). Body: `{"kind": "ratio", "numerator_stat_definition_id":
  ..., "denominator_stat_definition_id": ... | "denominator_constant": ..., "multiplier": 1, "offset": 0, "round_mode":
  "none"}`.
- **Types.** Both produce a number, so the stat is `int` or `float`. The inputs are numbers, `bool`s or `enum`s; a `text`
  stat is refused. An `int` target takes a product without a mode when every factor is whole (an `int`, `bool` or `enum`) and
  the multiplier and offset are, as `sum` does; a ratio is never always whole, so an `int` target needs a mode other than
  `none`.
- **The cycle check, the chain limit, preview, dependents and the enum guard cover them.** The stat inputs are edges of the
  definition-level graph; `dependents` reports `product` and `ratio`; moving or removing a value of an enum that a product or a
  ratio reads is a 409 `stat-enum-order-read-by-formula` (ADR 0444).
- **Nothing else changes.** Every existing request and response keeps its path, body and status.

## Design

Three tables, as the pattern of ADR 0444 sets: `computed_stat_product` (`multiplier`, `offset`, `round_mode`) with
`computed_stat_product_factor` (one row per factor, keyed by `position`, a stat), and `computed_stat_ratio` (the numerator, a
denominator stat or a denominator constant by a check, `multiplier`, `offset`, `round_mode`). All three are repository content
with `tenant_id`, same-tenant keys, RLS with `FORCE` and a line each in `copyable_tables.py`; a repository copy, a merge's cycle
check, a purge's count and the update engine carry them. `formula_load_options` joins the ratio and the product's row into the
formula's query and adds one statement for the factors, so a read still costs no more than before ADR 0444.

## Validation and delivery

A test for each: hit points from level, the average and an offset read against each instance; a repeated factor; a flag as a
factor; the rounding rule for an `int` target of a product and of a ratio; the shape errors (one factor, six, a `text` factor,
a read of itself, a `text` target, both or no denominators, a constant 0, a `text` numerator and denominator); a cycle through
a product and a ratio; a change of kind replacing the rows; preview, `division_rounded` for 1/3 and 3/2, and dependents; the
enum guard through a product and a ratio; RLS on the three tables; and a repository copy carrying both (the fixture seeds
them). The OpenAPI change is the two new members of the formula union, `product` and `ratio` in the dependents' `kind`, and
`division_rounded`; the breaking-change findings are recorded in `apps/api/openapi-breaking-accepted.txt` with this ADR as the
reason, and the CLI models and `packages/api-client` are regenerated.

## Consequences

- Hit points from level, a flag-switched bonus, an average and a rate are one formula each.
- Seven kinds become nine with K3's `select` still to come; each is a place a rule can be wrong.
- A formula response may be of kind `product` or `ratio`, which a client that switches on the kind must tolerate.
