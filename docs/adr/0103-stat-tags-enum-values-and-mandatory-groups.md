# 0103 - Stats: tag endpoints, enum values, and mandatory groups

Status: accepted

## Context

Accepts [RFC 0016](../rfcs/0016-stats-computed-values-and-crud-api.md) sub-slices 1 to 3. Each is small and independent, and none of them changes how a stat's value is resolved ([ADR 0037](0037-effective-stat-resolution.md)/[ADR 0039](0039-generic-effective-stat-view.md)). Computed stats (sub-slices 4 and 5) come in a separate ADR.

- **Tags** are already possible as a `bool` `stat_definition` set to `true`, but writing one takes the generic `PUT .../stats/{id}` with a JSON body. That route also leaves the gap ADR 0037 named: nothing ever acquires the stat's group for the entity (`entity_stat_group`).
- **Enum-constrained values** (rarity, size, class) have no home. `text` holds `"rare"` but nothing checks it against an allowed set.
- **Mandatory groups**: a client drawing a character sheet has no way to know which groups should always be shown, even when they're empty.

## Decision

### Mandatory groups

`stat_group.mandatory` (boolean, default `false`). `StatGroupCreate` accepts it and `StatGroupOut` returns it. It is display-only: the database never checks that a mandatory group's stats are filled in, and nothing else reads it.

### Tag endpoints

`/tenants/{tenant_id}/entities/{entity_id}/tags/{stat_definition_id}`, three verbs for the three states a tag can be in:

- **`PUT`** sets the entity's own value to `true`.
- **`PATCH`** sets it to an explicit `false`: an override, not silence. Example: a door built on the `wood` prototype but since rebuilt in metal.
- **`DELETE`** removes the entity's own row, so the value is inherited through the prototype chain again. It returns `200` with the entity, like the stat `PUT`, and is idempotent.

None of the three takes a body. The stat definition must be `bool`, otherwise `422 InvalidStatValueTypeError`. `PUT` and `PATCH` also add the stat's group to the entity (`entity_stat_group`) if it's missing. That closes ADR 0037's gap for tags; the generic stat `PUT` keeps its current behavior. `DELETE` leaves group acquisition alone, since other stats in the group may still need it.

Everything else matches `PUT .../stats/{id}`:

- The same self-or-managed authorization.
- `If-Match` checked against the existing `entity_stat` row, if there is one.
- The full `EntityDetailOut` as the response.
- Not logged in the activity log (stat values are descriptive content, [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)).

The two write paths share one helper for setting a value, so they can't drift.

### Enum values

- **`stat_value_type` gains `enum`.** An enum value is stored in `entity_stat.value_text`, so `entity_stat`'s "exactly one value column" check and `v_effective_stat` are unchanged, and resolution works exactly as for `text`.
- **A new table, `stat_definition_enum_value(id, tenant_id, stat_definition_id, value, sort_order)`**, with `UNIQUE(stat_definition_id, value)`. It carries `tenant_id` and the standard `tenant_isolation` policy with `FORCE ROW LEVEL SECURITY`. `sort_order` is a display hint (`common` before `legendary`) and is not unique.
- **`StatDefinitionCreate` gains `enum_values: list[str]`.** It is required and non-empty for `value_type = enum`, and must be absent or empty for any other type (`422`). The values are created in the same transaction as the definition, with `sort_order` following list position. Duplicates in the list return `422`.
- **`StatDefinitionOut` gains `enum_values`**, ordered by `sort_order` then `value`. It is empty for non-enum stats.
- **Growing or shrinking the vocabulary** is tenant-admin tier, like the rest of `routers/stats.py`:
  - `POST /tenants/{tenant_id}/stat-definitions/{stat_definition_id}/enum-values` (`{value, sort_order?}`) adds a value. An omitted `sort_order` is placed after the last. A duplicate returns `409`; a non-enum definition returns `422`.
  - `DELETE .../enum-values/{enum_value_id}` removes one. If any entity currently holds that value directly, it returns `409` rather than leaving stored values outside the allowed set.
- **Writing a value.** `PUT .../stats/{id}` on an enum stat takes a JSON string that must be one of the allowed values, otherwise `422 InvalidStatValueError`. Reads return the string, just like a `text` stat.

## Not in scope

- Computed stats, their resolution, and their authoring tools (sub-slices 4 and 5, a separate ADR). The unified stat bundle endpoint (sub-slice 6).
- `PATCH`/`DELETE` for stat groups and stat definitions, including flipping `mandatory` on an existing group or renaming or reordering an enum value. There is still no update route for either resource. Add one once a client needs it.
- `v_item`/`v_item_instance`'s named `rarity` column still reads an `int` stat called `rarity`. A tenant that defines `rarity` as an enum sees it in `stats` (and `GET /entities/{id}`), not in `ItemOut.rarity`.
- Changing an existing definition's `value_type` to or from `enum`.

## Consequences

- Adding a value to the `stat_value_type` Postgres enum is easy; removing one isn't. The downgrade rebuilds the type and refuses to run while any `enum` definition exists.
- Typed API clients see a new `value_type` member. A client that switches exhaustively on it needs an `enum` branch, which for display is the same as `text`.
- Tags now have a way to stay tied to their group, but the generic stat `PUT` still doesn't acquire groups. The two write paths differ in that one respect, on purpose, until the unified bundle endpoint (sub-slice 6) decides it for every stat.
