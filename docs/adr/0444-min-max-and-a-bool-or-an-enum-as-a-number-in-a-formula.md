# 0444 - `min`, `max`, and a bool or an enum as a number in a formula

Status: accepted, built (2026-11-11). Slice K1 of [RFC 0053](../rfcs/0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md).
Builds on [ADR 0104](0104-computed-stats.md), [ADR 0126](0126-sum-formulas.md), [ADR 0127](0127-contents-formulas.md),
[ADR 0390](0390-renaming-a-stat-and-an-enum-value.md) and [ADR 0403](0403-stat-scales.md); it changes nothing decided about
how a stat resolves ([ADR 0037](0037-effective-stat-resolution.md), [ADR 0266](0266-stat-tie-break-by-parent-order.md)).

## Context

The four formula kinds cannot cap, floor or compare: dexterity 18 in armour that caps the modifier at +2 gave an armour class
of 20, not 18, and a flag or a tier could not be a term at all, since a `bool` or an `enum` as an input answered 422. RFC 0053
decided the kinds that say these things; this is the first of its four slices.

## Decision

- **A `bool` and an `enum` are numbers in `linear`, `sum`, `min` and `max`.** A `bool` is 1 when true and 0 when false. An
  `enum` is the `sort_order` of the value it holds, not its position, so it moves only when its author moves it. An unset stat
  has no value, as before. A `text` stat is still refused, and `comparison` still reads numbers only: its inputs are not in
  this slice.
- **`min` and `max` are kinds of their own.** `min` is the smallest and `max` the largest of two to five inputs, each a stat
  of the same entity or a constant. The body is `{"kind": "min" | "max", "inputs": [{"stat_definition_id": ...} |
  {"constant": ...}], "round_mode": ...}`. A stat input with no value gives the formula no value. The target is `int` or
  `float`. The result picks one input, so an `int` target needs a rounding mode only when an input is a `float` stat or a
  fractional constant, the rule `sum` has, with a `bool` or an `enum` counting as whole.
- **A change of an enum's order, or the removal of one of its values, is refused while a formula reads it as a number.**
  `PATCH .../enum-values/{id}` carrying a `sort_order` that differs, and `DELETE`, answer 409
  `stat-enum-order-read-by-formula` naming the formulas (`<stat> of <entry>`); a rename and a `sort_order` that does not
  change go through, since neither moves a number. The repository update engine skips a removal for the same reason.
- **The cycle check covers them.** The definition-level graph gains the stat inputs of a `min` or `max` as edges, as a `sum`'s
  terms are, and the chain limit of [ADR 0443](0443-the-api-answers-what-it-used-to-ignore-crash-on-or-return-out-of-order.md)
  counts them.
- **Preview, explanation and dependents know the new kinds.** `preview` runs an unsaved `min` or `max`, `dependents` lists the
  formulas that read a stat as `min` or `max`, and the stat explanation gains `picked`: the position of the input taken (the
  first, when several tie), its stat (null for a constant) and the value it counted as.
- **Nothing else changes.** Every existing request and response keeps its path, body and status. The relaxation is a `linear`
  or `sum` formula with a `bool` or an `enum` input, which answered 422.

## Design

- **One table pair for both kinds.** `computed_stat_extremum` (`pick` is `min` or `max`, `round_mode`) and
  `computed_stat_extremum_input` (`position`, then a stat or a constant, exactly one) hold both kinds: they have the same
  parameters, and a shared pair keeps the read of a formula at one row. RFC 0053 said each kind has a table of its own; a
  `pick` column in place of a second table is the deviation, and the other kinds of the RFC keep a table each. Both tables
  are repository content and follow [ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md) and
  [ADR 0218](0218-the-copyable-table-registry.md): `tenant_id`, same-tenant keys, RLS with `FORCE`, and a line each in
  `copyable_tables.py`. A repository copy, a merge's cycle check, a purge's count and the update engine carry them.
- **A formula's read costs what it cost.** `formula_load_options` joined into the query for the formula the kinds that hold one
  row (`linear`, `comparison`, `sum`, `contents` and the new one) and kept one more statement for each kind that holds a list
  (a sum's terms, the new inputs). The four kinds took five statements; they and the new one now take two. An enum's number
  needs the enum's values with the definition, which every read that evaluates loads: one more statement, so the statement
  counts of [ADR 0285](0285-api-reads-that-cost-what-they-read.md) and [ADR 0387](0387-the-bulk-effective-stat-read.md) fall
  and do not rise.
- **The rank is read where the value is.** `stat_evaluation.numeric_value` turns a value into what a formula reads, with
  the stat's definition: a bool becomes 1 or 0, an enum the `sort_order` of its value, and a value the enum no longer allows
  has no number.

## Validation and delivery

A test for each: a cap and a floor read against each instance, a min of constants and mixed inputs, a float input rounding for
an `int` target, a bool as a term in `linear`, `sum` and `max`, an enum numbered 10, 5, 30 read as that and not as its
position, a `text` input and a bool in a `comparison` still refused, the shape errors (one input, six, both or neither of a
stat and a constant, a read of itself, a `text` target, a fractional constant for an `int`), a cycle, a change of kind
replacing the rows, preview, explanation (a stat and a constant picked) and dependents, the guard on an enum's order, RLS on
both tables, and a min formula copied with a repository. The OpenAPI change is the two new members of the formula union and
`picked`, which the breaking-change check reports for the response union and
[`openapi-breaking-accepted.txt`](../../apps/api/openapi-breaking-accepted.txt) records with RFC 0053 as the reason. The CLI
client models and `packages/api-client` are regenerated.

## Consequences

- A cap, a floor, a flag as a term and a tier as a number are one formula each.
- An enum's order becomes something a formula depends on: reordering it is a 409 while one does.
- A formula response may be of kind `min` or `max`, which a client that switches on the kind must tolerate.
- Slices K2 to K4 add `product`, `ratio`, `select` and the options of `contents` on the same pattern.
