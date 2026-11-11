# 0446 - `select` formulas: a value from a table

Status: accepted, built (2026-11-11). Slice K3 of [RFC 0053](../rfcs/0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md).
Builds on [ADR 0444](0444-min-max-and-a-bool-or-an-enum-as-a-number-in-a-formula.md) (a `bool` and an `enum` as numbers, and the
way a kind is added), [ADR 0445](0445-product-and-ratio-formulas.md), [ADR 0104](0104-computed-stats.md) and
[ADR 0390](0390-renaming-a-stat-and-an-enum-value.md).

## Context

A table by level, tier, size or category was a staircase of `linear` and `floor`, one formula per step and exact only over a
bounded input, and an `enum` could not be an input at all. A cap that depends on a category was a `min` and a table in chains of
formulas.

## Decision

- **`select(source, mode, steps, otherwise)`.** One kind with two modes, up to 64 steps, each with a result, and the result
  when none applies.
  - **`threshold`** (a number, `bool` or `enum` source, read as ADR 0444 says): the steps are `from` values and the result is that
    of the highest `from` the source reaches. The `from` values rise, step after step, so an order is never a guess.
  - **`match`** (a `text` or an `enum` source): the steps are values, which differ, and the result is that of the step whose value
    the source holds. An enum source needs no rank: the value is matched as the text it is, and a value the enum does not allow
    is refused at write.
- **A result is exactly one of** `number`, `text`, `flag` or `stat_definition_id`. A constant is of the target's type: a number
  for `int` and `float` (whole for `int`), a flag for `bool`, a text for `text` and `enum` (an allowed value, for an `enum`). A
  stat of the same entity is for a numeric target, a stat a number reads (a `float` stat is refused for an `int` target, since a
  select does not round), and it is an input of the formula and an edge of the cycle check. `otherwise` is a result or null, and
  with null a source that matches nothing gives no value, as does a source with no value.
- **Body:** `{"kind": "select", "source_stat_definition_id": ..., "mode": "threshold" | "match", "steps": [{"from": 3 | "value":
  "heavy", "result": {"number": 2}}, ...], "otherwise": {...} | null}`. A `threshold` step has `from` and no `value`, a `match`
  step the reverse.
- **An enum's text moves with its value.** A rename of an enum value (ADR 0390) rewrites the select steps that match it (the
  source is the enum) and the steps and `otherwise` that return it (the target is the enum); removing a value is a 409 while a
  select matches or returns it, as it is for a `comparison`. A `threshold` select, or a result stat, that reads an enum as a number
  holds the enum's order like a `linear` formula does (ADR 0444).
- **Preview, explanation and dependents know it.** `preview` runs an unsaved select; `dependents` reports `select` for its source
  and every result stat; the stat explanation gains `chosen`: the position and key (the `from` or the value) of the step taken, or
  `otherwise: true` when none applied.
- **Nothing else changes.** Every existing request and response keeps its path, body and status.

## Design

Two tables as ADR 0444 sets the pattern: `computed_stat_select` (the source, the mode, and the four columns of `otherwise`, all
null for none) and `computed_stat_select_step` (`position`, a `threshold` or a `match_value` by a check, and the four columns of
the result, one set by a check). Both are repository content with `tenant_id`, same-tenant keys, RLS with `FORCE` and a line each
in `copyable_tables.py`; a repository copy, a merge's cycle check, a purge's count and the update engine carry them.
`formula_load_options` joins the select row into the formula's query and adds one statement for its steps. A release document
carries a formula's select fields from format 39; version 38 is read with none.

## Validation and delivery

A test for each: the proficiency bonus by level (below the first step, between steps, past the last), no `otherwise` and an unset
source, a `bool` and an `enum` as thresholds (an enum numbered 10, 5, 30), a match over an enum with a stat, a constant and a
constant result, a match over a text source for a number, a text and a flag, a select that returns an enum value; the shape and
type errors (no steps, 65 steps and 64 as the limit, steps that do not rise, a step with the wrong key for the mode, the wrong
source type for the mode, repeated or disallowed values, a result that is two things or none, every constant and stat result
against every target type, a read of itself); a cycle through a source and through a result stat; a change of kind replacing the
rows; preview, `chosen` and dependents; the rename and removal of an enum value a select matches or returns; the order guard for a
`threshold` over an enum; RLS on both tables; a release document round trip; and a repository copy carrying a select (the fixture
seeds one). The OpenAPI change is the new member of the formula union, `select` in the dependents' `kind`, and `chosen`, recorded
in `apps/api/openapi-breaking-accepted.txt` with this ADR as the reason; the CLI models and `packages/api-client` are regenerated.

## Consequences

- A table by level, tier or category, a value that depends on an enum, and a cap picked by a category are one formula each.
- A step whose result is a stat is a numeric conditional, so `min`, `max` and a table compose without a chain of intermediate stats.
- Nine kinds become ten; a formula response may be of kind `select`, which a client that switches on the kind must tolerate.
