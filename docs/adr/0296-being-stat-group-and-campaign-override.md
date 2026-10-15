# 0296 - A being stat group, with a campaign override

Status: accepted, scoped with the maintainer on 2026-10-15.

## Context

The library already chooses a weapon stat group and an ability information type ([ADR 0281](0281-sheet-settings-and-the-sheet-read.md)); a being currently displays stats across all its groups. A designated being group can identify its primary stat line without changing its values or hiding other groups. The maintainer asked for the setting, a campaign override and CLI authoring, with no frontend changes.

Campaign overrides for the weapon group are not implemented on current main: ADR 0281's campaign parameter is validated but otherwise ignored. This slice introduces an override for the being group only.

## Decision

- Add nullable `being_stat_group_id` to `tenant` and `campaign`. Each names a stat group of the same tenant, enforced by a composite foreign key. Campaign uses `same_tenant_fk`; the tenant uses its own `id`, as its weapon group does. Deleting a group clears only the reference column, never `tenant_id`. Existing RLS policies and permissions remain in force; there is no new tenant table.
- `PATCH /tenants/{id}` and `PATCH /tenants/{id}/campaigns/{id}` set or clear the respective field. Omitted means unchanged; null on a campaign means inherit the tenant, and null on the tenant means unset. The existing tenant administrator and campaign management gates apply. Missing or foreign groups return the existing `422 invalid-sheet-setting` error. Record the changed field through the existing activity log.
- Tenant and campaign detail reads return their stored values. The being sheet read returns additive `being_stat_group_id`, resolved from a non-null override of the explicitly supplied, readable `campaign_id`, otherwise from the tenant. No campaign is guessed from a being's rosters. No campaign means the tenant default. Clearing or deleting an override's group restores inheritance. This field selects a group; it does not filter existing stat reads or change visibility.
- Extend `lorenzo tenant sheet-settings TENANT` with `--being-stat-group GROUP` and `--clear-being-stat-group`, with the existing id-or-exact-name resolution. Optional `--campaign ID_OR_SLUG` reads or edits the campaign override; its JSON also identifies the effective being group. Weapon and ability options stay tenant-only and are refused with `--campaign`. Campaign writes re-read and send the campaign's ETag. The setting is configured after creation, as the existing sheet settings are.
- The group is a library/campaign presentation setting, not repository content: it is not copied or synced with a repository. Generate the Python and TypeScript API schemas and check mobile's consumed contracts; no frontend behavior changes.

## Not in scope

Campaign overrides of the weapon group or ability type; a frontend editor or display change; selecting several primary groups; explicitly disabling a tenant default in one campaign; templates; modifying stat values or making the designated group mandatory.

## Consequences

A library can designate a primary group and a campaign can choose another, without adopting a game-specific model. Clients can discover the effective group through the existing sheet read when they later use it. One migration and additive API fields; a null campaign value consistently means inheritance.
