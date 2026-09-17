# 0059 - Group-scoped notifications

Status: accepted

## Context

[ADR 0058](0058-notifications.md) covers four scopes - platform, tenant, campaign, character - but not the existing `group` concept ([ADR 0028](0028-knowledge-and-group-membership.md)/[ADR 0045](0045-read-only-groups-api.md)): a bare `Entity` referenced by one or more `GroupMember` rows, originally built for knowledge-visibility ("known to this group"), read-only until now. A group's members are always characters (`GroupMember.character_entity_id` FKs to `character.entity_id` specifically), never arbitrary entities.

The one real design question: **who may send a notification to a group?** Groups have no owner and aren't tied to a single campaign - the existing read gate (`is_tenant_participant`, ADR 0045) is deliberately wide open ("browsing groups to pick a knowledge-visibility target"), too permissive for a broadcast write. Every other scope in ADR 0058 reuses that scope's own existing management authorization (tenant admin, campaign GM, character rename); groups have no equivalent concept to reuse directly, but their members do.

## Decision

Authorization is **per-member, fail-closed**: the caller must be authorized to manage *every* character in the group (self-control, or `can_manage_campaign` on at least one of that character's campaigns, or - for a character rostered into none - `can_manage_campaign` on any campaign in the tenant) - the exact "any one campaign is enough" rule `PATCH /characters/{id}`'s rename path already established, just required once per member instead of once. Being authorized to message *some* but not all of a group's members doesn't authorize messaging the group as a whole; an empty group trivially passes, since there's nothing to be unauthorized for.

That per-character predicate was previously private to `routers/characters.py` (`_authorize_rename`'s own inline logic). Promoted to `campaign_access.can_manage_character` so this is the *only* copy, not a second one duplicated into `routers/groups.py` - `_authorize_rename` itself is now a two-line wrapper over it.

`POST /tenants/{tenant_id}/groups/{group_entity_id}/notifications`, same `NotificationCreate` body every other scope route takes. An omitted `recipient_user_id` broadcasts to every player controlling *any* member character (the same `CharacterPlayer` roster-reuse join the character scope uses for one character, extended across every member at once) - a character in two groups' overlapping rosters is still just one row per distinct recipient, not one per membership.

## Not in scope

- Any notion of a group "owner" or dedicated management role - deliberately reusing per-member character authorization instead of inventing one.
- Coarsening authorization to "manages any campaign in the tenant" - considered, rejected: it would let a GM of an unrelated campaign message a group none of whose members they actually have standing over.

## Consequences

- `campaign_access.py` gains `can_manage_character`; `routers/characters.py`'s `_authorize_rename` now calls it instead of duplicating the check (its own `can_manage_any_of_campaigns` import is no longer needed there).
- `lorenzo_api/notifications.py` gains `create_group_notification`; `routers/groups.py` gains `_require_can_manage_group` and the new route.
