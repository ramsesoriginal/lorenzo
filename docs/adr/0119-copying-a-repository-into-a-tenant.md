# 0119 - Copying a repository into a tenant

Status: accepted

## Context

[RFC 0024](../rfcs/0024-repositories.md) §5 and §6: games run on a copy, not a live read. Copying makes a repository's content the subscriber's own, ordinary tenant data. `v_effective_stat` then resolves it with no cross-tenant join, and it survives the repository being withdrawn or deleted. The RFC's amendment adds two things this ADR has to handle. Names and slugs collide on the very first copy (A4). And each copy records a snapshot, so later updates can be diffed (A7, [ADR 0121](0121-repository-updates-and-re-sync.md)).

This ADR covers one repository with no dependencies of its own. A bridge's dependencies are [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md). The two share one algorithm, and this ADR describes it in the form ADR 0120 builds on.

## Decision

### Two routes

For any member of the subscribing tenant, the same tier that authors stat definitions ([ADR 0037](0037-effective-stat-resolution.md)):

- `GET /tenants/{tenant_id}/repositories/{repository_id}/copy-plan` writes nothing. It returns what a copy would do: how many entities, stat groups, stat definitions, and pieces of information it would bring in, plus every collision that needs a choice.
- `POST /tenants/{tenant_id}/repositories/{repository_id}/copy` copies, in one transaction. It answers `201` with the same counts, plus anything it had to leave out and why.

A repository that has already been copied answers `409 repository-already-copied`. Later changes come in through ADR 0121's updates, not a second copy.

### What is copied

The repository's **own** rows: every entity, stat group, and stat definition that isn't itself a copy of somebody else's (for a plain repository, that's everything). With them come the rows that belong to each own entity:

| Table | Belongs to its |
| --- | --- |
| `item`, `item_instance`, `being`, `character`, `entity_slug` | entity |
| `entity_prototype` | child (`entity_id`) |
| `entity_stat_group`, `entity_stat`, `computed_stat` and its two kinds | entity |
| `containment` | child |
| `ownership` | owned entity |
| `group_member` | group |
| `information`, its `payload`s and their four kinds, and its `knowledge` | entity |
| `stat_definition_enum_value` | definition |

Every row gets a fresh id and the subscriber's `tenant_id`. Every reference is re-targeted onto the subscriber's own copy. A reference whose target wasn't copied, because the subscriber chose to skip it, drops that one row. The response lists what was dropped, by kind and source id. Nothing is left pointing across tenants: [ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)'s keys would refuse it anyway.

A few columns aren't copied as they stand:

- **`created_by`** on entities, characters, and information is the member who ran the copy. It is who created these rows, and it's what [ADR 0101](0101-editable-information-and-description-payloads.md)'s "you wrote it" edit rule reads.
- **`character.owner_player_id`** is always null, since a repository has no players.
- **Knowledge** held by a player can't exist in a repository. Knowledge held by an entity (a character or a group) is copied like anything else.
- **`content_reference`** isn't copied. Each copied description is run through the same extractor [ADR 0110](0110-lorenzoscript-content-references-and-backlinks.md) uses, so backlinks resolve against the subscriber's own slugs.
- **Timestamps** are new. `item.in_public_catalog` is copied as the author set it.

What a reader then sees of the copied information follows the ordinary rules. Public text is public, and GM-only text is visible to the tenant's OWNER and ORGA. A campaign's GMs see it once their characters reach it (the amendment's A9).

### Collisions

A collision needs a choice before anything is copied:

| Collides on | Choices |
| --- | --- |
| a stat group's name | `rename` (with a new name), `merge` into the local group of that name, `skip` |
| a stat definition's name | `rename`, `merge` into the local definition (same value type only), `skip` |
| a slug | `rename` (with a new slug), `skip` (the copy gets no slug) |

- **Names claimed earlier in the same plan count.** Two repositories in one manifest that both define "Strength" collide with each other.
- **Skipping a group skips its definitions**, and every value, formula, and attachment that uses them.
- **Merging a definition** adds any enum values the local one lacks, and changes nothing else about it.
- **Renaming a slug** leaves the copied text's `[[old-slug]]` links pointing at whatever the subscriber already calls that. The copy doesn't rewrite text, and the plan says so next to the choice.

`POST .../copy` without a choice for every collision answers `409 repository-copy-needs-choices`, listing each collision and its allowed choices. The client sends `resolutions` back, one per `(kind, source_id)`. A choice that can't work, such as a rename onto another taken name or a merge across value types, answers `422` and names it.

After the copy, the tenant's formula graph is checked for cycles, as when a formula is written by hand ([ADR 0104](0104-computed-stats.md)). A merge that would close one makes the copy fail with `409` and roll back.

### What is recorded

- **`repository_copy (tenant_id, repository_tenant_id, copied_at, copied_by, synced_at)`**: one row per repository a tenant has copied. It belongs to the subscriber and is kept when a grant is removed.
- **Copy links**, one table each: `repository_copy_link_entity`, `repository_copy_link_stat_group`, and `repository_copy_link_stat_definition`. Each has `(tenant_id, <local id>, source_tenant_id, source_id, snapshot, copied_at)`, and the group and definition links also carry `mode` (`copied` or `merged`).
  - **The local side is a composite foreign key** (ADR 0117). Deleting the local row keeps the link with the local id set to null, so ADR 0121 can tell "deleted here" from "new upstream".
  - **The source side is a plain id**, not a foreign key. It is another tenant's row and may disappear.
  - **Every source is an origin**, never a copy of a copy, because only own rows are ever copied (the amendment's A8).
  - **`snapshot`** is what was copied, with ids translated to their origins. For an entity: its name, kinds, `in_public_catalog`, prototypes, stat groups, stat values, formulas, and slug. For a group: name, priority, `mandatory`. For a definition: name, value type, group, enum values. ADR 0121 diffs against it.
- These tables have `tenant_isolation` and ADR 0118's `repository_read` policy, since a bridge's subscribers have to read a bridge's links (ADR 0120).
- **The activity log** records the copy once, with counts ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)).

## Not in scope

- **Copying part of a repository.** Choosing some entities and taking their prototype chains with them is a natural next step. This version copies everything.
- **Rewriting links in copied text** after a slug rename.

## Consequences

- After a copy, nothing in play depends on the repository still existing, being published, or still being granted.
- A large repository is a large write in one transaction. Nothing here measures or limits it yet (RFC 0024's own consequence).
- The copy knows every content table by name. A new content table has to be added to it, and to ADR 0118's policy list, or it won't be copied. The test that keeps ADR 0118's list complete checks this list too.
