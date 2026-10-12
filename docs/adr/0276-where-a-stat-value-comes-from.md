# 0276 - Where a stat value comes from, and an explanation of a calculated one

Status: accepted, decided with the maintainer on 2026-10-12. Slice A1 of [RFC 0043](../rfcs/0043-the-being-sheet.md).

## Context

An entity's stats are `{name, value, own}` ([ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md)): the effective value, and whether the entity holds it itself, stored or computed. `v_effective_stat` ([ADR 0037](0037-effective-stat-resolution.md), [0266](0266-stat-tie-break-by-parent-order.md)) picks one candidate per entity and stat, but names the holder only when a formula won (`computed_entity_id`). So a page cannot say "from Dwarf" for a stored inherited value, and cannot tell an inherited formula from an inherited value, which is the usual case for armour class.

The only explanation of a computed value is `POST .../computed-stats/{id}/preview` ([ADR 0104](0104-computed-stats.md)). It is tenant-admin only, returns the values the formula read without coefficients or offset, and for a contents formula returns none ("spread over what's inside").

## Decision

- **The view names every winner.** `v_effective_stat` gains `source_entity_id`, the holder of the winning row, stored or computed, appended as the last column (`CREATE OR REPLACE VIEW`, so no dependent view changes). `computed_entity_id` stays. The rule that picks the winner is not touched.
- **`EntityStatValueOut` gains** `from_entity` (`EntitySummary`, null when the entity holds the value itself, otherwise the holder of the stored value or of the formula) and `computed` (true when a formula produced the value). `own` is now "the source is this entity". Both fields are additive.
- **An explanation read any participant may call:** `GET /tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}/explanation`, allowed to whoever may read the entity. It returns the stat's value, `computed`, `from_entity`, and, for a computed stat, the winning formula in the shape of `ComputedStatOut.formula` and the inputs it read as `{stat_definition_id, name, value}`. For a contents formula it returns `contents`, the stat it reads and the number of things directly inside, instead of one input per thing; the total is the stat's own `value`. An entity with no value for the stat is a 404. A stat that is not computed returns no formula. It reuses `stat_evaluation`; there are no new tables.

## Not in scope

An explanation per content item; a history of a value; naming every ancestor that was passed over; writing anything.

## Consequences

- A sheet can draw "From Dwarf", "Calculated" and "how was this made up" for a player as well as a GM.
- One migration. A view cannot lose a column while other views are built on it, so its downgrade leaves the column in place.
- The OpenAPI change is additive; clients are regenerated.
