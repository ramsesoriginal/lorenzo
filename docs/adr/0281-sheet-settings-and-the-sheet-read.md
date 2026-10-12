# 0281 - Sheet settings and the sheet read

Status: accepted, decided with the maintainer on 2026-10-12. Slice A6 of [RFC 0043](../rfcs/0043-the-being-sheet.md); builds on [ADR 0278](0278-stat-definition-display-fields-order-and-patch.md).

## Context

A datasheet shows what a being has equipped as a table of the stats of a weapon group, and its abilities. Which stat group is the weapon group, and which type of information is an ability, depends on the game. An item read carries four fixed stat lists ([ADR 0019](0019-item-and-v-item.md)), and a being belongs to no campaign of its own: it is on the rosters of the campaigns whose players play it, and an NPC is on none.

## Decision

- **Two settings of the library (tenant):** `weapon_stat_group_id` (a stat group of the tenant, or none) and `ability_information_type` (a text, or none). They are set with `PATCH /tenants/{id}`, in the tier that sets the tenant's other settings ([ADR 0033](0033-tenant-creation-and-update-api.md)), and shown on the tenant read. They are not copied with a repository: a library sets them once after copying. The group is a composite foreign key `(weapon_stat_group_id, id)` to `stat_group (id, tenant_id)` (the tenant's own column is `id`, so `same_tenant_fk` does not fit) with `ON DELETE SET NULL (weapon_stat_group_id)`; deleting a tenant, which cascades to its stat groups ([ADR 0184](0184-deleting-a-tenant.md)), has a test of its own. Information types outside the fixed catalog are free text ([ADR 0101](0101-editable-information-and-description-payloads.md)), so the type is not a key.
- **The sheet read:** `GET /tenants/{tenant_id}/beings/{entity_id}/sheet`, with an optional `campaign_id`. It returns:
  - `weapons`: what the being has **equipped**, meaning contained directly by it ([ADR 0130](0130-the-controlled-by-listing.md)), that has at least one stat in the weapon group, each with its name, quantity and the group's stats (effective, calculated ones evaluated, contents formulas included) in the group's order;
  - `abilities`: the information of the ability type, in its order, with its payloads, as `InformationOut`;
  - `weapons_configured` and `abilities_configured`, so a client can say a setting is missing instead of showing an empty table.
- **Visibility is unchanged.** Items follow [ADR 0040](0040-item-instance-read-visibility.md): someone who cannot reach an owned item's owner sees no weapon. Another player's datasheet is empty of weapons, for now. Abilities follow the information visibility of the caller.
- **`campaign_id`** must be a campaign of the tenant that the caller can read (404 otherwise). Today it changes nothing; it is accepted so a campaign can later override the library's settings without a new route.

## Not in scope

Per-campaign overrides; entity templates; a different rule for who sees an opponent's weapons; setting these in the apps.

## Consequences

- The datasheet is one read for a being's weapons and abilities, with no read per item.
- A library that has not set the group or the type gets empty sections and the flags.
- One migration; additive OpenAPI.
