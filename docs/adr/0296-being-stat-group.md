# 0296 - The tenant's being stat group

Status: accepted, scoped with the maintainer on 2026-10-15.

## Context

The library already chooses a weapon stat group and an ability information type ([ADR 0281](0281-sheet-settings-and-the-sheet-read.md)); a being currently displays stats across all its groups. A designated being group can identify its primary stat line without changing its values or hiding other groups. The maintainer asked for the tenant setting and CLI authoring, with no frontend changes.

The campaign parameter is accepted and validated, as it is for the existing sheet read. The maintainer clarified that campaign overrides are a later feature: this slice neither stores nor applies an override.

## Decision

- Add nullable `tenant.being_stat_group_id`. It names a stat group of the same tenant, enforced by a composite foreign key `(being_stat_group_id, id)` to `stat_group (id, tenant_id)`, as the weapon group does. Deleting a group clears only the reference column, never the tenant's id. Existing RLS policies and permissions remain in force; there is no new tenant table.
- `PATCH /tenants/{id}` sets or clears the field. Omitted means unchanged; null means unset. The existing tenant administrator gate applies. Missing or foreign groups return the existing `422 invalid-sheet-setting` error. Record the changed field through the existing activity log.
- Tenant detail and the being sheet read return additive `being_stat_group_id`. The sheet always reports the tenant's setting. An explicitly supplied `campaign_id` must still identify a campaign of the tenant that the caller can read; it does not change the selected group. No campaign is guessed from a being's rosters. This field selects a group; it does not filter existing stat reads or change visibility.
- Extend `lorenzo tenant sheet-settings TENANT` with `--being-stat-group GROUP` and `--clear-being-stat-group`, using the existing id-or-exact-name resolution, read/write permissions and JSON output. Omitted options preserve settings; setting and clearing together is refused. No campaign setting command is introduced.
- The group is a library presentation setting, not repository content: it is not copied or synced with a repository. Generate the Python and TypeScript API schemas and check mobile's consumed contracts; no frontend behavior changes.

## Not in scope

Campaign override storage or behavior, including weapon and ability overrides; a frontend editor or display change; selecting several primary groups; templates; modifying stat values or making the designated group mandatory.

## Consequences

A library can designate a primary group without adopting a game-specific model. Clients can discover it through the existing sheet read when they later use it. One migration and additive API fields; campaign override semantics remain deferred.
