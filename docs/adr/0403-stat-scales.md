# 0403 - Stat scales: an optional minimum and maximum

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slice 3. Builds on [ADR 0278](0278-stat-definition-display-fields-order-and-patch.md) and
[ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md).

## Context

A standing such as honor or Concordance has a scale: minus ten to ten, zero to five. A stat definition has a unit, a
sign flag and an order, and an enum has ordered values, but nothing says how far a number may go. Without it the
matrix cannot bound an input or draw a value against its range, and a typo of 1000 for 10 is stored.

## Decision

- **Two nullable columns on `stat_definition`**, `min_value` and `max_value` (numeric), for `int` and `float`
  definitions only (a 422 on any other type). Each is optional, and `min_value <= max_value` when both are set.
- **A write is checked.** `PUT .../stats/{id}` and the bulk write of [ADR 0400](0400-relationship-kinds-standings-and-direction.md)
  refuse a value outside the bounds with a 422 that names them. A computed value is not clamped: a formula result
  outside the range is shown as it is.
- **Setting or changing a bound** is `PATCH /stat-definitions/{id}` (tenant-admin tier, as ADR 0278). A bound that
  existing own values would break is a 409 with the number of entries. Neither is recorded in the activity log.
- **Repositories carry them**: the bounds travel through copy, update and release with the other display fields
  (ADR 0280's path), with a release-format bump and a digest that includes them. A library that copied a definition
  takes a changed bound as any changed field, by review.
- **The interface** bounds an input to the range, draws a value against it in the matrix and in a stat editor, and
  with no bounds shows the value and colors by the visible range, saying so.
- An enum's ladder is unchanged: ordered labels, no number.

## Validation and delivery

Tests: each type, the 422 and 409, a bound set before and after values exist, the bulk write, copy, update and
release, the older reader, and that an unbounded stat reads exactly as today. The OpenAPI change is additive.

## Excluded

A step or a precision, a clamp on computed values, bounds on a bool, text or enum, and a per-entry scale.
