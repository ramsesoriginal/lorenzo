# 0141 - Fractional weights in the named columns

Status: accepted

One of four small `apps/api` additions for [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R9, R11; slice 3). See [ADR 0139](0139-name-an-item-when-it-is-created.md).

## Context

A stat definition can be an `int`, `float`, `text`, `bool` or `enum`, and a `float` value is stored, resolved through inheritance, and returned by `GET .../entities/{id}` like any other. But the *named* fields on `ItemOut` and `ItemInstanceOut` (`weight`, `height`, `price`, `rarity`, `hp`, `armor`) and the values in `physical_stats` are `int | null`. They are read through a view of the integer column only, and a stat that holds a `float` reads as `null` there.

RFC 0025 R9 stores weight as a `float` because the source data has `0.05` and `0.2`, and scaling to integer hundredths would lock a unit in that nobody can read. Until this is fixed an imported bullet weighs `null` on every list and board, and only the entity detail has the number.

## Decision

The named columns and the per-group stat values return a number when the stat is a number.

- `weight`, `height`, `price`, `rarity`, `hp` and `armor` become `int | float | null`. A value stored as an `int` still reads as an `int`; one stored as a `float` reads as a `float`. The definition's `value_type` decides, as it does everywhere else.
- `StatValueOut.value` and the values in `physical_stats` (and the other per-group maps built by the same function) widen the same way.
- Nothing is stored differently. The values are already resolved in the application from the generic stat view ([ADR 0039](0039-generic-effective-stat-view.md)); the change is what the schema allows through. No migration.
- `PUT .../stats/{id}` still does not coerce: a `float` stat must be sent as `1.0`, not `1`, as today.

## Consequences

- Additive for every reader that treats the field as a number. The generated schema for these fields changes from `integer` to `number`, which a client with a strict integer type will see; both in-repo clients (`packages/api-client` for loot-bot and inventory-web, and `apps/cli`) are regenerated in the same change.
- The OpenAPI diff reports a widened response type. It is not a break for a JSON reader, and is recorded in `openapi-breaking-accepted.txt` if `oasdiff` flags it.
- A definition whose values are mixed (some entities `int`, some `float`) is not an error; the number is returned as stored.
- `own_weight` and `contents_weight` are not named columns and appear only in `physical_stats`; they are covered by the second bullet.
