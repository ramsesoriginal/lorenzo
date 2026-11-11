# 0053 - Formula kinds: min, max, product, ratio, select, and aggregation over what an entry holds

Status: proposed (2026-11-11), Decision open on the questions at the end. It reopens what
[RFC 0016](0016-stats-computed-values-and-crud-api.md) leaves for "a real, concrete need", what
[ADR 0126](../adr/0126-sum-formulas.md) and [RFC 0030](0030-carrying-holding-binding-and-capacity.md) list as "not in
scope" (non-additive kinds: max, min, choose), and [ADR 0403](../adr/0403-stat-scales.md)'s exclusion of a clamp on
computed values. It changes nothing decided about how a stat resolves
([ADR 0037](../adr/0037-effective-stat-resolution.md), [ADR 0266](../adr/0266-stat-tie-break-by-parent-order.md)).

## Purpose

Say, with curated formula kinds and no expression language, the arithmetic that game systems keep needing and the four
kinds cannot say today: a cap, a floor, a product or a ratio of two stats, a value looked up from a table, a flag that
switches a bonus, the best or the worst of what an entry holds, and a count of what is switched on.

## Decided inputs

1. **Add:** a bool and an enum as numbers, `min` and `max` as kinds of their own, `product`, `ratio`, `select`, and
   aggregation over what an entry holds.
2. **The aggregation sees only what is switched on**, using the `active` switch of a held thing, so what counts is
   decided by the thing and not by a container built for the purpose. `active` is defined here, for item instances.
3. **A `select` result may be a stat** as well as a constant.
4. **An enum is both a rank and a `match` key:** a numeric formula reads an enum as a number, and `select` can match it.
5. **Curated, not general:** each kind stays a fixed, reviewed function with parameters, as RFC 0016 chose. No interpreter.
6. **"Missing counts as 0" on a sum term is not added**; a lint and a stored default stay the answer to an unset input.
7. **The limits:** five inputs or factors, 64 steps, one level of aggregation.

## What the four kinds cannot say (tried against the API, 2026-11-10)

| Need | Today |
| --- | --- |
| A dexterity cap on armour class | `min(modifier, cap)` has no kind: dexterity 18 in armour that caps the modifier at +2 gave an armour class of 20, not 18. A comparison gives only a bool or a text |
| Hit points from level times (die average + modifier) | a product of two stats: stored by hand |
| An average, a rate, a cost per unit | a ratio of two stats: none |
| A bonus when a flag is set (proficiency times a bonus) | a `bool` cannot be an input (422), a coefficient is a constant: made a trait entry that carries the formula, as a parent |
| A table by level, tier, size or category | a staircase of `linear` and `floor`, one formula per step, exact only over a bounded input; an enum cannot be an input at all |
| Only what is worn, held or switched on counts | `contents` sums every direct child: a carried spare armour counted (armour class 24, not 16); fixed by a container per level |
| The best, the worst, the count | no kind: a count of attuned items had to be a sum of ones |
| AND, OR, NOT of conditions | none: one `comparison` per bool, and a bool is not an input |

Each one has a workaround, and each workaround costs formulas, entries or intermediate stats that cannot be hidden.

## Hard invariants

- **No interpreter.** Every kind is a parameterised call into reviewed code, a table of its own, a schema, an evaluator
  and a line in the copyable-table registry ([ADR 0218](../adr/0218-the-copyable-table-registry.md)), as RFC 0016 required.
- **Resolution does not change.** A formula is still evaluated for the entry that is read, on that entry's resolved stats
  (ADR 0037, 0104). A formula still reads the same entry's stats and, for aggregation, what the entry directly holds.
- **Arithmetic is exact.** Decimal throughout, a rounding mode wherever a result may be fractional, and the same rule for
  an `int` target as today: a mode, unless every input is an `int` stat and every constant whole.
- **Stored formulas keep their meaning.** No stored formula reads a `bool` or an `enum` today (both are refused), so
  letting them in changes none of them.
- **The write-time cycle check covers every kind.** The definition-level graph gains the new kinds' same-entity inputs as
  edges; aggregation reads a level down and adds none, as `contents` does (ADR 0127).
- **A computed value is never clamped by a stat's scale** (ADR 0403). `min` and `max` are how an author clamps, on purpose.
- **Tenant isolation is by RLS** (ADR 0002); every table has `tenant_id` and same-tenant foreign keys (ADR 0117).

## Design (proposed)

### 1. A bool and an enum are numbers in a formula

In `linear`, `sum` and the kinds below, a `bool` counts as 1 when true and 0 when false, and an `enum` counts as the
`sort_order` of the value it holds. An unset stat has no value, as before. A `text` stat is still refused; `select` reads
it (section 5).

A bool is what turns a flag into an arithmetic term: AND is `product` or `min`, OR is `max`, NOT is `linear` with a
multiplier of -1 and an offset of 1.

An enum's number is the `sort_order` its author gave the value, and it moves only when the author moves it. A change of an
enum value's `sort_order`, or the removal of a value, is refused while a formula reads the enum as a number, and the
refusal names the formulas (ADR 0390 does the same for a value a formula returns). Renaming a value changes no number.

### 2. `min` and `max`

`min(inputs, round_mode)` and `max(inputs, round_mode)`: two to five inputs, each a stat or a constant; the result is the
smallest or the largest. `min(a, b)` is a cap, `max(a, 0)` is a floor, and `min(max(a, lower), upper)` is a clamp in two
formulas. The target is `int` or `float`. A result that picks one input is whole when every input is whole, so an `int`
target takes a mode only when an input is a `float` stat or a fractional constant.

### 3. `product` and `ratio`

`product(factors, multiplier, offset, round_mode)`: two to five stats multiplied, then times a constant, plus an offset,
rounded as `sum` rounds. A flag is a factor of 0 or 1. Hit points from level are `product(level, average)` with `average`
a `sum`.

`ratio(numerator, denominator, multiplier, offset, round_mode)`: a stat divided by a stat (or a constant), times a
constant, plus an offset. A zero denominator gives no value, as an unset input does. A ratio is never always whole, so an
`int` target needs a mode.

### 4. `select`: a value from a table

`select(source, mode, steps, otherwise)`, with a result for each step and one when none matches. A step's result is a
constant of the target's type, or, for a numeric target, a stat of the same entry (the stat is an input of the formula and
an edge of the cycle check).

- **`threshold`** (a numeric, `bool` or `enum` source): steps are `from` values in order; the result is that of the highest
  `from` the source reaches. A table by level, a stepped points cost, a lifting table, a damaged profile by wounds are one
  formula each.
- **`match`** (a `text` or `enum` source): steps are values; the result is that of the value the source holds. A cap by
  armour category, an experience value by challenge rating, or a label by tier is one formula, and the enum's rank is not
  needed.

Up to 64 steps. The target may be `int`, `float`, `bool`, `text` or `enum`; a `text` or `enum` target holds only the step
constants, validated as a `comparison` validates its two values. A step whose result is a stat gives a numeric
conditional: the dexterity cap in one formula that picks the cap by category.

### 5. `contents`, with options

`contents` keeps its meaning and gains options, each with the default that is today's behaviour:

| Option | Values | Default |
| --- | --- | --- |
| `aggregate` | `sum`, `min`, `max`, `count` | `sum` |
| `only_active` | true: skip a held thing whose `active` switch is off | false |
| `only_kind` | a kind of the held thing (`item_instance`, later `feature_instance`) | any |
| `where` | a `bool` stat that must be true on the held thing | none |
| `if_none` | a constant for `min` and `max` of nothing | no value |

`sum` and `count` of nothing are 0, as `contents` is today; `min` and `max` of nothing have no value, or `if_none`. `count`
ignores the stat. Armour class from worn armour is `max` over active armour of `armor`, with `if_none` for the unarmoured
case; a dexterity cap is `min` over active armour of its cap; attunement used is `count` over active things where
`requires_attunement`. Quantity still multiplies a `sum` (a stack of five); `min`, `max` and `count` ignore it.

### 6. `active` on a held item instance

An item instance has a `bool` switch `active`, true by default. A prototype may say that its instances start inactive, as an
item that needs attunement does. The switch is the holder's to flip, by the rule that already governs the instance. It
does not move or free the thing: weight, size and capacity (ADR 0128) count it either way, and a binding is unchanged.
The features RFC gives feature instances the same switch.

### 7. Reading, preview and explanation

`explanation` names the step a `select` took, the input a `min` or `max` picked, and the things an aggregation counted;
`preview` runs the new kinds before they are saved, as for the first four; `dependents` lists the new kinds.

### What it costs on a read

Evaluation stays pure Python, memoised, with no new query on the read path except the formula's own rows. The evaluator
loads each kind's tables with the formula ([ADR 0285](../adr/0285-api-reads-that-cost-what-they-read.md),
[ADR 0387](../adr/0387-the-bulk-effective-stat-read.md)): new kind tables must not raise the statement counts those tests
assert, and if loading each kind separately would, they are loaded in one query. The slice that adds them carries the
test.

### The Bench

A pane for each, in the vocabulary of [ADR 0253](../adr/0253-bench-formulas-and-the-stat-vocabulary.md): "Lowest",
"Highest", "Multiply", "Divide", "Pick by", and "Highest/Lowest/Count of what it holds". Pick-by takes a pasted list of
`from` and result pairs.

## Recipes this replaces

The guide "Modelling a game system" documents workarounds that this makes unnecessary: a staircase becomes one `select`;
a trait entry that carries a formula becomes a `product` with a flag; a worn-gear container becomes `contents` with
`only_active`; an enum needing a numeric twin becomes a rank or a `match`. It is updated when a kind is built.

## Delivery

Each slice is its own ADR.

1. **K1.** A bool and an enum as numbers; `min`; `max`.
2. **K2.** `product`; `ratio`.
3. **K3.** `select`, both modes.
4. **K4.** `contents` options; `active` on item instances.
5. **K5.** The Bench panes, the preview and explanation, and the guide update.

## Not in scope

- An expression language, a general operation tree (RFC 0016's option D), or nesting one kind inside another: a longer rule
  stays a chain of named stats.
- Dice, random numbers and text built from stats.
- Aggregation beyond one level down, over group members, over a relationship's ends, or across the prototype graph.
- "Missing counts as 0" (decided out).
- Clamping a computed value by a stat's scale (ADR 0403).
- Grants, features and the `feature_instance` kind: their own RFC, which uses `only_kind` and `active`.

## Open questions

1. **The enum rank and an enum's order.** The rank is the author's `sort_order` (proposal); the alternative is the position
   in the list, which moves when a value is inserted. The refusal to reorder or remove a value that a formula reads as a
   number is part of the proposal.
2. **`ratio` rounding.** Division is the one operation that is not exact in Decimal; the proposal rounds at the
   default precision before the offset and the mode apply, and says so in the explanation when it does.
3. **An aggregation of `min` and `max` over held things of mixed kinds.** `only_kind` is how a rule says which; without it
   a stat that one kind does not carry simply contributes nothing.

## Alternatives considered

- **A general expression tree** (RFC 0016's option D). It would make every case above one formula, at the price of an
  interpreter, a validator for it, a Bench editor for it and a new place for bugs. The kinds above cover every case met in
  the tests; the tree is still there to reach for if chaining proves unwieldy.
- **One `bound` kind with a lower and an upper limit.** Covers min, max and clamp in one table; two kinds were chosen because
  `min` and `max` are the names a person looks for, and a clamp is two formulas either way.
- **Make `comparison` return numbers.** A ternary kind with two stat or constant results; `select` is the same idea with a
  table and a match, so one kind is enough.
- **An enum only through `match`.** Keeps an enum free of numbers, but a rank is what "at least the third tier" means.
- **Clamp by the stat's scale.** Rejected in ADR 0403, and a scale is the input's rule, not the result's.
- **An aggregation kind apart from `contents`.** Same reads, same cycle rule and same loading; options keep one place.
- **Counting only what a container holds.** Works today and costs a container for each rule; the `active` switch puts the
  decision on the thing.

## Consequences

- Rules that need a cap, a table, a flag or an average are one formula instead of several, with fewer intermediate stats on
  a sheet.
- Four kinds become nine, each with its tables, schema, evaluator, Bench pane and registry line, and each a place a rule can
  be wrong.
- An enum's order becomes something a formula can depend on, so reordering it is guarded.
- The response union of a formula gains members, which the OpenAPI breaking-change check reports; the slice records it in
  `openapi-breaking-accepted.txt` with this RFC as the reason.
- A held thing grows a switch, and a library's sheets and boards may show it.
- Deeper rules still mean longer chains, and a very long chain already fails on read; a write-time depth cap is wanted whatever
  this RFC decides.
