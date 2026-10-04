# 0167 - The API deletes an unused stat definition or stat group

Status: accepted

Amends [ADR 0014](0014-stats.md), which left no way to remove either. Decided with the maintainer on 2026-10-04, so that a seeded layer can be taken out again ([ADR 0168](0168-lorenzo-unseed.md)).

## Context

A stat definition or stat group, once created, stays: the API has no way to delete either (ADR 0014), and every copy of a repository takes them frozen ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)). That was the safe start, since a definition has values hanging off it. It also means a mistake is permanent: the maintainer's `core` repository holds 22 D&D 5e stat definitions it should never have had, unused, and every table that copies the D&D 5e repository now has to merge 22 collisions with them.

What makes deleting one dangerous is what hangs off it. Deleting a definition cascades to every value held for it and every formula for it, and a formula that *reads* it blocks the delete in the database. Deleting a group cascades to its definitions, and so to their values. An unused one has none of that.

## Decision

**Two routes, unused only**, the way a stat's enum value is already removed ([ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md)): a `409` while it is in use, and no `?force`.

- **`DELETE /tenants/{tenant_id}/stat-definitions/{stat_definition_id}`** answers `204`. It answers `409` (problem type `stat-definition-in-use`) while the definition is *in use*: any entity holds a value for it, any entity has a formula for it, or any formula reads it (a linear formula's source, a comparison's sides, a sum's terms, a contents formula's source). The detail says how many of each. The definition's enum values go with it.
- **`DELETE /tenants/{tenant_id}/stat-groups/{stat_group_id}`** answers `204`. It answers `409` (`stat-group-in-use`) while the group holds any stat definition, or any entity has acquired it.
- **Who may:** whoever may create them. Both belong to the tenant's shared stat vocabulary ([ADR 0032](0032-item-and-item-instance-crud-api.md)), and the routes sit on the same router with the same tenant context.
- **Logged**, like their creation ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)): `stat_definition.deleted` and `stat_group.deleted`, naming what went.
- **A missing one is `404`**, as for a read.

Rename and retype stay impossible. This lifts the *removal* restriction of ADR 0014, and only for what nothing uses.

### Repositories

Nothing about copies needs to change, because the link rows that track them already expect a row to vanish: a copy's link to its local row is cleared when that row is deleted ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)), and a repository's rows are remembered by id, not held by a key ([ADR 0121](0121-repository-updates-and-re-sync.md)).

- **A definition deleted in a repository** is reported to the tenants that copied it as removed upstream, by `repo updates`. Their own copies are left as they are.
- **A copied definition deleted by the tenant that copied it** is reported by its next `repo updates` as deleted locally, and can be added again.

## Not in scope

- **Deleting a definition or group that is in use**, with or without its values. A caller removes the values or the formulas first.
- **Renaming, retyping or moving** a definition between groups.
- **Telling a caller what uses a definition** beyond the counts in the `409`.

## Consequences

- `apps/api` gains two routes, two problem types, two activity actions, and tests for the guards and for `repo updates` over an upstream deletion.
- The OpenAPI document gains the two routes; the CLI's operation table follows ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)).
- The seed's own comment that definitions "can't be renamed, retyped or removed" (`builtin.toml`) reads "or removed while in use", and ADR 0014 gets an addendum pointing here.
