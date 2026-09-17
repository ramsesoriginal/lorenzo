# 0049 - `mine` filter on `GET /tenants/{tenant_id}/characters`

Status: accepted

## Context

`GET /tenants/{tenant_id}/characters` returns every character in the tenant to any tenant-wide member ([ADR 0031](0031-character-table-and-read-api.md)) - there's no way for a client to ask for just "my own characters" without fetching the whole roster and filtering client-side, wasteful for a tenant with any real number of players.

## Decision

New optional query parameter `mine: bool = False`. When `true`, the result narrows to characters whose `owner_player_id` resolves to one of the caller's own `Player` rows in this tenant - **owner specifically, not the broader roster**: [ADR 0025](0025-character-being-and-ownership.md)'s roster reuse lets several `Player` rows pilot the same character (`character_player`), but `owner_player_id` is the one, singular "this is your character" fact (`CharacterSummaryOut.is_pc`'s own source column) and the one the word "owned" in the request actually named. A co-pilot who isn't the owner doesn't get that character back under `mine=true` - if a broader "characters I can act through" filter is ever needed, that's a genuinely different question (`entity_access.controlled_character_entity_ids`, already used elsewhere for authorization, not listing) and would need its own, differently-named parameter, not an overload of this one.

Resolved the same way `entity_access.py`'s own reachability helpers resolve "the caller's players in this tenant" - a plain `select(Player.id).where(Player.user_id == ..., Player.tenant_id == ...)`, then `Character.owner_player_id.in_(...)` - rather than a subquery, matching this codebase's established two-step idiom over inline correlated subqueries.

No change to the route's existing authorization (`_require_tenant_member`, unchanged) - `mine` only narrows an already-authorized read, the same relationship every other query-filter in this API (`container_id`, `q`, ...) has to its own route's gate.

## Not in scope

Filtering by an arbitrary other user's ownership (`?owner_user_id=`) - not asked for, and a GM wanting "which characters does player X own" already has that answer via the campaign roster endpoints. Extending `mine` to mean "controlled by," not just "owned by" - see Decision above.

## Consequences

- `routers/characters.py`: `list_characters` gains the `mine` query parameter and, when set, an extra `.where(Character.owner_player_id.in_(...))` clause before pagination.
- A client can now render "my characters" directly, in one call, instead of fetching the tenant's full roster and filtering it locally.
