# 0109 - Player knowers, knower listing, and the per-entity information list

Status: accepted

## Context

Accepts [RFC 0015](../rfcs/0015-information-metadata-shape.md) sub-slices 5 and 6 (decisions 6, 10 and 11). [ADR 0101](0101-editable-information-and-description-payloads.md) took sub-slices 1 and 3.

The read side already honours a knowledge row naming a *player* (`knowledge.knower_player_id`, [ADR 0028](0028-knowledge-and-group-membership.md)): `information_visibility` unions the caller's own `Player` ids into what they can see. Nothing can ever write one, though. The knower routes ([ADR 0038](0038-information-payload-knowledge-crud-api.md)) only take a character or group entity. A GM therefore can't tell something to a player as a person, only to one of their characters. Nobody except a tenant administrator ([ADR 0085](0085-tenant-data-export-audit-and-runbook.md)'s tenant-wide index) can see who has already been told something. And an entity's information can only be read bundled inside `GET /entities/{id}`.

[RFC 0029](../rfcs/0029-epistemic-status-of-information.md) (proposed) sets a requirement on the list endpoint that this ADR adopts regardless of how that RFC is decided: a paginated information list must filter visibility **in SQL, before pagination**. Filtering in Python afterwards returns short pages and leaks how many hidden rows exist. RFC 0029 also expects the knower listing to be where a later per-knower `confidence` would show up. The listing's shape below leaves room for that.

## Decision

### Player knowers

`PUT` and `DELETE /tenants/{tenant_id}/information/{information_id}/player-knowers/{player_id}` mirror the entity-knower pair exactly:

- **Idempotent.** `PUT` creates the row if missing; `DELETE` removes it if present.
- **Response.** Both return `200` with `InformationOut`.
- **Authorization.** The ADR 0101 edit gate applies: standing over the information's entity, plus sight of the row or authorship.
- **Validation.** `player_id` must be a `Player` in this tenant; otherwise `404`.
- **Activity log.** `information.knower_added`/`information.knower_removed` with `detail="player=<id>"`, like the entity form's `knower=<id>` (ADR 0084: who can see what).

A player's seat is per campaign ([ADR 0024](0024-campaign-and-player.md)). Nothing checks that the player's campaign has anything to do with the entity. A GM with standing over an item can tell any player in the tenant about it. That is the same looseness the entity-knower route has for characters, and ADR 0028's addendum already names the resulting cross-campaign widening on the read side.

### Who has been told: `GET /tenants/{tenant_id}/information/{information_id}/knowers`

It returns `list[KnowerOut]`, unpaginated because it's bounded by the row's own grants, oldest first. `KnowerOut` has:

- `kind`: `entity` (a character or group) or `player`.
- `knower_entity_id` or `player_id`, whichever applies.
- `name`: the entity's name, or the player's user display name falling back to their nickname. Either can be null.
- `granted_at`.

A later `confidence` field (RFC 0029's BL5) would be one more nullable field on the same row.

**Gated like editing (the ADR 0101 gate), not like reading.** Knowing who else was told is itself a secret. A player who can see a note must not learn which other characters or players can. Anyone who can grant can list, and nobody else can; everyone else gets `404`.

### An entity's information: `GET /tenants/{tenant_id}/entities/{entity_id}/information`

- **Response.** `Page[InformationOut]`, ordered by `order` then `id`, using this API's standard pagination (ADR 0020).
- **Access.** Same as `GET /entities/{id}`: any tenant participant, then filtered to what the caller can see.
- **Filters.**
  - `type` (repeatable) matches `Information.type` exactly.
  - `category` is `technical` or `gm_authored`. `technical` means the type has an `information_type` row. `gm_authored` means it doesn't: free-form types never get catalog rows (ADR 0101), so that's the only meaning it can have.

**Visibility in SQL.** `information_visibility.visible_information_clause(vis)` is the SQL form of `InformationVisibility.can_see`, applied in the `WHERE` so pagination counts only visible rows. It is built from the same resolved sets:

- the administrator bypass;
- `is_public`;
- entities a GM can reach;
- an `EXISTS` over `knowledge` for the caller's player ids and knower entity ids.

A parity test runs both forms over the same fixed matrix of callers and rows, so the Python and SQL definitions can't drift:

- an administrator and an opted-out administrator;
- a GM reaching the entity;
- a player knower, a character knower and a group knower;
- a public row and a GM-only row.

## Not in scope

- **Information in the change feed** ("a new note about your item"). [ADR 0099](0099-player-facing-change-feed.md) left it out and it stays out here. Doing it safely means deciding, per recipient and at write time, whether they can see the row. It deserves its own slice.
- **Filters beyond `type`/`category`** (RFC 0029's `?known_by`, `?confidence_*`, `?authored_by`, ...). The SQL visibility clause they all need exists after this ADR.
- **The reorder endpoint** (RFC 0015 sub-slice 7). **Payload sub-resources and binary uploads** (sub-slice 4).
- **Stopping `GET /entities/{id}` from embedding information.** It still does, unchanged; the list endpoint is additive.

## Consequences

- A GM can now tell something to a player directly. `can_see` already honoured those rows, so no read path changes.
- Who-knows-what is visible to everyone who could grant it, not just to tenant administrators through the export index.
- Visibility now has two implementations, one in Python for single rows and one in SQL for lists. The parity test is what keeps them one definition.
