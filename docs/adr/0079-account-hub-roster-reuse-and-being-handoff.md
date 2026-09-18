# 0079 - account-hub: character/being roster reuse across campaigns

Status: accepted

## Context

Sub-slices (f)/(g) of [RFC 0014](../rfcs/0014-account-hub-tenant-admin-and-roster-management.md), grouped into one ADR because they're mechanically the same write (`character_player` roster-link, RFC 0002/ADR 0025) initiated from two different pages by two different actors.

Also incorporates a just-landed, directly relevant piece of `apps/api` surface found while researching this ADR: [ADR 0078](0078-being-listing-and-search-endpoint.md)'s new `GET /tenants/{id}/beings` superseded the workaround the Beings sub-slice ([ADR entries under RFC 0013](../rfcs/0013-account-hub-app.md)) had to use (`list_characters` filtered client-side to `is_pc: false`, since no dedicated "list beings" endpoint existed yet). Picked up here rather than left stale, since it directly improves this ADR's own being-picker (below).

## Decision

### `/beings` listing upgraded to the real endpoint

`GET /tenants/{id}/beings?q=` (`BeingSummaryOut`: `entity_id`, `name`, `is_pc: bool | null` - `null` means no `Character` row exists at all, distinct from `false`) replaces the `listCharacters`-and-filter workaround in `src/lib/characters.ts`. A pure improvement, not a behavior change the user asked for directly, but the honest byproduct of not letting a known workaround go stale once its real fix ships.

### Player: reuse an existing character across campaigns in the same tenant

On `/characters`, a campaign the caller has been invited to (a `PlayerContextOut` exists with zero `characters`) offers two actions side by side: the existing "create a new character" (RFC 0013), and new - "use one of my existing characters in this tenant." The second lists the caller's own characters from every *other* campaign in the same tenant (`MeOut.players[].characters[]`, deduplicated by `entity_id`, tenant-matched via each player context's own `tenant_id`), and on pick, calls `PUT /tenants/{id}/characters/{character_id}/players/{player_id}` (idempotent roster-link, `CharacterOut` back) - the target `player_id` is the *new* campaign's own `PlayerContextOut.id`, not the source one.

### GM: hand an existing being to a player as their character in a campaign

On `/beings`, per being: a "Use as a played character" action. The GM picks a campaign they GM (reusing `campaignRoleFor`'s existing 'gm' filter), the picker then either selects an existing player in that campaign or reuses the ADR 0076 invite flow if the target user has no player row there yet, and on confirmation:

1. `PUT /tenants/{id}/characters/{character_id}/players/{player_id}` - the same roster-link (5) uses.
2. `PATCH /tenants/{id}/characters/{character_id}` (`CharacterUpdate.owner_player_id`) - **also** sets ownership, per RFC 0014's own decision: "a real, lasting handoff... not a temporary loan." After this, the entity is indistinguishable from any other player character (`is_pc` flips to `true` for good) - it stops appearing in `/beings`' own listing from that point on, which is the correct, expected consequence of a real handoff, not a bug.

Both calls run in sequence, not parallel - if the roster-link succeeds but the ownership PATCH fails, the being is left linked-but-not-owned, a recoverable partial state (the GM can retry "make owner" alone, since the link already exists and the PUT is idempotent) rather than the reverse partial state (owned but not linked), which is undefined - `owner_player_id` pointing at a player row that '`character_player` doesn't actually list is a real inconsistency, not a lesser variant of the same failure worth risking on a race for the sake of speed.

## Consequences

- `src/lib/characters.ts`: `listCharacters` (the old workaround) replaced with `listBeings(tenantId, q?)` calling the new endpoint; `linkCharacterToPlayer(tenantId, characterId, playerId)` added for the shared roster-link write both sub-slices use.
- `BeingSummaryOut` added to `types.ts`, replacing `beings.astro`'s reliance on `CharacterSummaryOut` for its listing (the two shapes now genuinely differ: `is_pc` is nullable on one, never on the other).
- `beings.astro`'s "no beings yet" empty state and rename flow are otherwise unchanged - only the data source and the new handoff action are new.
- This is the last of RFC 0014's seven sub-slices ((a) through (g)) - once built, RFC 0014 is complete.
