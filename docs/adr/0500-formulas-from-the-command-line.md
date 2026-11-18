# 0500 - Formulas from the command line

Status: accepted (2026-11-17), decided with the maintainer, built (2026-11-18). Slice C6 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Keeps [RFC 0016](../rfcs/0016-stats-computed-values-and-crud-api.md) and [RFC 0053](../rfcs/0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md):
curated kinds, no interpreter.

_Originally numbered 0486; renumbered before merge - the Maps ADRs 0481, 0482, 0490 and 0491 reached `main` first, so the RFC 0057 block moved as a whole to 0495-0507. Same precedent as ADR 0050/0054/0068/0069/0087._

## Context

The API has eleven kinds (`linear`, `comparison`, `sum`, `contents`, `min`, `max`, `product`, `ratio`, `select`, `dice_value`, `dice`),
a preview that shows the value and its inputs, and a dependents read. The CLI writes only `contents` and `sum`, from the seed.

## Decision

- **No notation.** A formula is written as its kind and that kind's fields, in the document or as options. RFC 0016 rejected a text
  language by name; a notation that expands to one kind would still be one.
- **`lorenzo formula set STAT --on ENTRY --kind KIND`** with options for the kinds whose fields are flat: `--source`, `--multiplier`,
  `--offset`, `--round` (`linear`, `ratio`, `dice_value`); `--left`, `--comparator`, `--right` | `--right-value`, `--true`, `--false`
  (`comparison`); `--term STAT[*COEFF]` repeated (`sum`); `--input STAT|NUMBER` repeated (`min`, `max`); `--factor STAT` repeated
  (`product`); `--numerator`, `--denominator` | `--denominator-value` (`ratio`); `--count` | `--count-value`, `--sides` | `--sides-value`
  (`dice`); `--source`, `--aggregate`, `--only-active`, `--only-kind`, `--where`, `--if-none` (`contents`); `--as` (`dice_value`). A
  `select`, with its steps, is written in a document (`--from FILE` takes one `[[formula]]` table).
- **Limits before the API**: two to five inputs or factors, one to twenty terms, one to sixty-four steps, a dice count of 1 to 100 and
  sides of 2 to 1000, the stat types a kind accepts. The message names the limit; the API's own answer still decides.
- **`formula show STAT --on ENTRY`** prints the kind and its fields with stats by name. **`formula preview STAT --on ENTRY`** asks the API
  to evaluate it for that entry, or a formula given with the same options before it is saved, and prints the value with each input and
  its value (a dice value as its notation, `3d8`). **`formula tree STAT --on ENTRY`** prints the chain down to own values and, below it,
  the formulas that read the stat (the dependents read). **`formula delete`** follows the write contract.
- Writes send `?warnings=true` when `--warnings` is given and print the findings ([ADR 0503](0503-lorenzo-check.md)).

## Consequences

- Every kind can be written; the common ones in one line, the rest in a document that is also how they are exported.
- A formula is checked for its limits before it is sent, and previewed against a real entry before it is saved.
