# 0459 - Findings: an unset input, and an own value that shadows a formula

Status: accepted, built (2026-11-12). Slice V2 of [RFC 0055](../rfcs/0055-vocabulary-check.md). Builds on
[ADR 0458](0458-the-vocabulary-check-route-and-its-first-findings.md) (the route and how a page is scanned),
[ADR 0037](0037-effective-stat-resolution.md) and [ADR 0104](0104-computed-stats.md). Resolution does not change.

## Context

Two things go wrong silently in a library's stats: a computed stat whose input has no value has no value itself (it is absent from the
entry's read, and its explanation is not found), and a value written on an entry that has a formula only on a prototype is stored and
wins, with nothing to say a formula was passed over.

## Decision

- **`unset-input`** (`warning`): a stat whose winner is a formula, and which has no value on the entry because a stat that formula reads
  on the same entry has none. The entry holding the formula is a prototype or the entry itself; the prototype is told too, since it has
  no value either. `details`: `formula_entry_id`, `kind` (the formula's kind), `inputs_without_value` (stat ids). No finding when every
  input has a value and the stat has none for another reason (a contents or select formula with nothing to take, a cycle).
- **`own-value-shadows-formula`** (`warning`): an entry holds a stat by a value of its own (stored on it, not computed), and an entry on
  its prototype walk holds a formula for the same stat, which that value is winning over. `details`: `own_value` and `formula_entry_id`,
  the first such ancestor by id. An entry with a formula of its own, or one that inherits a value, has none.
- **What the caller reads.** An entry named in `details` that the caller may not see (a library's hide, ADR 0437) has `formula_entry_id`
  null and `formula_entry_hidden` true.
- **Cost.** Both come from the page's loading and cost a fixed number of statements: the page's ancestors in one walk and its formulas
  in one query (only when `own-value-shadows-formula` is asked), and one query for the names of the inputs. A test says it does not grow
  with the entries.
- `code` accepts both, and they are in the default set. No `warning` is refused or stored.

## Design

`scan_entries` evaluates the page, takes the stats it holds by an own value, finds their formulas above in two queries
(`_formulas_above`, reusing the prototype walk of ADR 0456) and the inputs without a value from the formula's own rows
(`ComputedStat.source_stat_definition_ids`). The scan now takes the caller's visibility.

## Validation and delivery

A test for each: a computed stat with no value naming the input without one, for the entry and for the prototype that holds the
formula, and none for an entry whose input is set; an own value shadowing a formula, with none for an entry without one, one with a
formula of its own and the prototype itself; the statements not growing with the entries. The OpenAPI change is two more values of the
`code` parameter and of `code` in a finding; the CLI models and `packages/api-client` are regenerated.

## Not in scope

`tie` (V3), warnings on writes (V4); naming the nearest of several ancestors that hold a formula.

## Consequences

- "Why has this stat no value?" and "why did my formula not apply?" have an answer in one read.
- A prototype that holds a formula but no input reports once, and an author who means it filters it with `code`.
