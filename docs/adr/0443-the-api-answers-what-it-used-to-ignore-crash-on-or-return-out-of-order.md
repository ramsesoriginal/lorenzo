# 0443 - The API answers what it used to ignore, crash on or return out of order

Status: accepted, decided with the maintainer on 2026-11-11. One slice of fixes, found by trying stats, formulas,
repositories and several systems in one library against the API on 2026-11-10. Builds on
[ADR 0037](0037-effective-stat-resolution.md), [ADR 0104](0104-computed-stats.md),
[ADR 0390](0390-renaming-a-stat-and-an-enum-value.md) and [ADR 0437](0437-hiding-the-entries-of-a-repository-built-on-another.md).

## Context

Six things answered wrongly, each reproduced:

- `POST /stat-groups` and `POST /stat-definitions` with a name that exists answer 500 `unhandled-exception`, with the SQL
  in `detail`. `PATCH` rename already answers 409.
- `PATCH /stat-definitions/{id}` with `value_type` or `stat_group_id` answers 200 and changes nothing.
- A chain of formulas is accepted at any length, and a read of one of about 520 formulas or more fails with 500
  (`RecursionError` in the evaluator, whose docstring says it never raises).
- `PUT /entities/{id}/parents` accepts the id of an entry that a library hides (ADR 0437), which every read by address
  answers 404.
- The entity read lists `prototypes` alphabetically, while a stat's tie-break uses parent order.
- An item instance copied from a repository into a library is in the entity read and the database, and missing from
  `GET /item-instances` and 404 by id.

## Decision

- **A duplicate name on create is a 409.** `POST /stat-groups` answers `stat-group-name-taken` and
  `POST /stat-definitions` answers `stat-definition-name-taken`, the problems `PATCH` rename already gives, with the same
  fields.
- **A field that cannot change is refused.** `PATCH /stat-definitions/{id}` carrying `value_type` or `stat_group_id` answers
  422 `stat-definition-field-immutable`, naming the field. The other fields of the body are handled as today.
- **Evaluation does not fail a read.** A formula whose evaluation exceeds the recursion limit leaves its stat without a
  value, as a cycle does, and the failure is logged. A write that would give a formula a chain of more than 200 formulas
  below it answers 422 `formula-chain-too-deep`, naming the length. A chain already stored beyond 200 stays readable and
  is not touched.
- **A hidden entry is not found by id in `PUT .../parents`.** It answers 404 `entity-not-found`, as a read by address does.
- **`prototypes` is in parent order**, the order of `entity_prototype.position`, which is the order a stat's tie-break uses.
- **A copied item instance is listed and found by id.** The slice starts with a failing test for it. If the cause is a read
  rule (ADR 0040) working as designed, the slice records that and changes nothing.

## Not in scope

The named `rarity` field of an item reading `null` for an `enum` or a `text` stat (the field is a number; the hover card
shows the text), a float stat refusing a whole JSON number, a repeated `parent_id` in a query keeping the last, and the
doc/code disagreements found alongside: they are documented or belong to other work.

## Validation and delivery

A test for each: the 409 for a group and a definition, the 422 for each field, a chain of 150 and of 600 formulas (read
and write), a hidden id in `PUT .../parents`, the order of `prototypes` for parents given out of alphabetical order, a copied
item instance in the list and by id. The statement counts of
[ADR 0285](0285-api-reads-that-cost-what-they-read.md) do not rise. The OpenAPI change is the new error answers.

## Consequences

- A client that sent a duplicate name gets a 409 it can act on instead of a 500; one that sent `value_type` or
  `stat_group_id` to `PATCH` and read the 200 as success gets a 422.
- A list changes order: a client that relied on alphabetical `prototypes` sees parent order.
- A very deep chain reads as unset instead of failing the whole read.
- RFC 0052's first slice relies on the 409; if this lands first, it does not repeat it.
