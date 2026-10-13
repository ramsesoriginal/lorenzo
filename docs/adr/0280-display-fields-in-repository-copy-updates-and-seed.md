# 0280 - The display fields in repository copy, updates, digest and the seed

Status: accepted, decided with the maintainer on 2026-10-12. Slice A5 of [RFC 0043](../rfcs/0043-the-being-sheet.md); builds on [ADR 0278](0278-stat-definition-display-fields-order-and-patch.md) and [0279](0279-stat-hints.md).

## Context

A copy keeps a snapshot of each stat definition ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [0121](0121-repository-updates-and-re-sync.md)): `stat_definition_snapshot` holds the name, type, group and enum values, and updates compare it field by field. The release digest hashes it ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md)). If the new fields are not carried, a library that copies a rules repository silently loses its units, pins and hints. The CLI seed ([ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md)) defines definitions by name, type and group only.

## Decision

- **Snapshot.** `unit`, `adjustable_in_play`, `pin`, `signed` and the three hints are part of `stat_definition_snapshot`. A hint is named by origin, like the group is. `position` is **not**: it is copied when a library copies, and a library may then order its own vocabulary, so a repository reordering does not fill every library's updates.
- **Copy.** Definitions are written first with their hints empty, and the hints are set in a second pass, remapped to the library's own definitions. A hint to a definition that was not copied is dropped and reported with the other things a copy dropped, as a formula input is. Positions are copied.
- **Updates.** The new fields are diffed and applied like `name` and `value_type` are, with a hint applied only if its target is in the library (added by the same update when it is a new definition, as a formula's input is); one that cannot be is reported, never guessed.
- **Digest.** The facts the digest breaks on (removed, retyped, an enum value taken away) are unchanged. The snapshot's hash changes, so the first release of an existing repository after this lands lists its definitions as changed. That is expected once and is noted in the release.
- **Seed and CLI.** A seed's definitions can carry `unit`, `adjustable_in_play`, `pin`, `signed` and hints (by name, written after every definition exists). Their position is their order in the file. Re-seeding a library that already has a definition updates its display fields instead of skipping it. The CLI's generated client is regenerated.

## Not in scope

The authoring screens; syncing `position`. If it should be synced, it is one key added to `stat_definition_snapshot`, and the same first-release noise.

## Consequences

A repository can ship a complete sheet vocabulary. The first update after this lands shows no false changes for fields that default (unit empty, flags false, no hints), because a missing key and a default compare equal.
