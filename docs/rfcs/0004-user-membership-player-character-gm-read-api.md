# RFC: User, membership, player, character, and GM read REST API

Status: proposed — builds on [RFC 0003](0003-tenant-campaign-read-api.md)'s `get_campaign_context`; now needs a migration (a new `character` table layered under `being`, plus retargeted FKs) and an ER diagram update, unlike this RFC's first draft

## Context

The access/role graph — who is a tenant owner/orga, who plays which campaign as which character, who GMs which campaign — is fully built ([ADR 0022](../adr/0022-user-tenant-membership.md)/[ADR 0024](../adr/0024-campaign-and-player.md)/[ADR 0025](../adr/0025-character-being-and-ownership.md)/[ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)) but almost entirely unreadable over HTTP. The one exception, `GET /me` ([routers/users.py](../../apps/api/src/lorenzo_api/routers/users.py)), exists "purely to prove the whole pipeline end-to-end... not the start of a fuller `/users` API" (its own docstring) and returns only tenant-wide `Membership` rows — nothing about `Player`, `Being`/character, or `CampaignGm`.

**Revised after noticing a real gap while reviewing this RFC**: there's no dedicated `character` table, only `being` ([ADR 0025](../adr/0025-character-being-and-ownership.md)), which covers every sentient entity — PC or background NPC — identically, with nowhere to add character-specific richness later without bloating that one table for everything sentient, tracked or not. [ADR 0019](../adr/0019-item-and-v-item.md)'s `item`/`item_instance` split, plus its `v_item`/`v_item_instance` views, had no equivalent here at all. This revision adds both.

This is deliberately scoped narrower than [RFC 0003](0003-tenant-campaign-read-api.md): that RFC exposes *tenant* and *campaign* as resources; this one exposes *who occupies which role in them* — the "user → owner\|orga\|member of tenant → \[player(campaign) → character \| GM(campaign)\]" graph, in the user's own framing. It deliberately does **not** re-expose entity stats/inventory (that's the existing `entities`/`items` read API, an orthogonal axis already built) — a character here is identified and rostered, not fully described.

## Decision

Every campaign-nested endpoint below is gated by [RFC 0003](0003-tenant-campaign-read-api.md)'s `get_campaign_context`, not `get_tenant_context` — an ordinary player or GM reaching their own campaign's roster has no tenant-wide `Membership` row to satisfy the older, stricter gate, exactly the gap [ADR 0022](../adr/0022-user-tenant-membership.md) named. Bare tenant-level collections stay on `get_tenant_context`, per that RFC's access-gating rule.

### Schema addition: the `character` table

`character(entity_id, tenant_id, owner_player_id)` — **layered directly under `being`**, not a sibling extending `entity` the way `item`/`item_instance` are: `character.entity_id` is PK **and** FK to `being.entity_id` (`ON DELETE CASCADE`), not to `entity.id` directly. This is the first three-level class-table-inheritance chain in this schema (`entity` → `being` → `character`) — every other concrete type extends `entity` in one hop; this is deliberately different, since "is this being also being tracked as a full character" is layered on top of "is this entity sentient at all," not a parallel fact about it. A bare `being` with no `character` row is still perfectly valid — an unnamed monster stub, background NPC, or anything not worth individual tracking. Standard `tenant_id` + `ENABLE`/`FORCE ROW LEVEL SECURITY` + `tenant_isolation` policy, no exceptions, matching every tenant-scoped table so far.

**`owner_player_id` moves here from `being`**, keeping its exact existing shape (nullable, `FK → player.id`, `ON DELETE SET NULL` — losing the owning player still just leaves the character player-less, an NPC, not destroyed). Reasoning: only a tracked, named individual is ever player-owned — a bare background `being` was never a meaningful target for `owner_player_id` in the first place, so the column belongs on the layer that actually needs it.

**`character_player.character_entity_id` and `group_member.character_entity_id` both retarget from `being.entity_id` to `character.entity_id`.** Consequence, stated plainly: a `being` now has to be "promoted" to a `character` row before it can be rostered to a player or added to a knowledge group — a plain, untracked NPC can't be. This is a real behavior change from [ADR 0025](../adr/0025-character-being-and-ownership.md)/[ADR 0028](../adr/0028-knowledge-and-group-membership.md)'s original design (either could target any `being` before); accepted here as the correct tightening, not a side effect to route around, since roster-piloting and group-knowing are both squarely "full character" concerns — flagged again in Open questions and Consequences below, not silently absorbed.

No new columns beyond `owner_player_id`'s move, deliberately — "we might add custom fields to `character` later" was the stated motivation for this table existing at all, but none are specified yet; adding them speculatively here would be designing ahead of an actual need, which this codebase's own discipline avoids.

### `v_character`

Mirrors `v_item`/`v_item_instance` ([ADR 0019](../adr/0019-item-and-v-item.md)): a maintained, `security_invoker=true` view over `character` (joined up through `being`/`entity`) exposing commonly-needed computed/joined data as plain columns, so a client doesn't hand-assemble it from four tables on every read.

- `entity_id`, `tenant_id`
- `description_id`, `title` — from the entity's `Information` row where `type = 'description'`, identical to `v_item`'s own resolution.
- `owner_player_id` — straight off `character` itself now, the one column genuinely specific to this view (mirroring how `v_item_instance` singles out `owner_entity_id` as "the one column that's genuinely specific to instances").
- `container_entity_id` — from `containment`, where this entity is the child (where this character is physically located).

Named RPG-flavored stat columns (an `hp`, say) are deliberately **not** proposed here — `v_item`'s own `weight`/`price`/`rarity`/`hp`/`armor` were specific choices made for that slice, not a template to copy blindly, and which stats matter enough to deserve a dedicated named column on `v_character` is a product call this RFC doesn't make. Anything beyond the four columns above stays reachable the general way, through the shared stat-group mixin below.

**`ItemViewMixin` generalizes to `EntityViewMixin`.** Its properties (`descriptions`, `physical_stats`/`economic_stats`/`destroyable_stats`/`damaging_stats`, `tags`) were already generic — built on `Entity`'s own relationships, nothing item-specific about the implementation itself, just the names of the `stat_group`s a tenant happens to use. Renaming and sharing it between `VItem`/`VItemInstance` and the new `VCharacter` avoids a second, drifting copy of the identical logic. Same caller-must-eager-load-first discipline as today, unchanged.

Same grant gotcha `v_item` already hit and documented ([ADR 0019](../adr/0019-item-and-v-item.md)): `security_invoker=true` means the querying role needs `SELECT` on every underlying table the view touches (`character`, `being`, `entity`, `information`, `payload*`, `entity_stat`, `stat_definition`, `containment`), not just the view itself — already covered automatically here, since `lorenzo_app`'s `ALTER DEFAULT PRIVILEGES` grant ([ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)) applies to every table including ones this RFC adds, but worth restating since it was a real, previously-hit surprise the first time.

### `GET /me`, extended

`MeOut` ([schemas/users.py](../../apps/api/src/lorenzo_api/schemas/users.py)) gains two fields alongside the existing `memberships`:

- `players: list[PlayerSummaryOut]` — every `Player` row this user holds, across every tenant/campaign (`User.players`, already a `back_populates` relationship, just not eager-loaded/exposed yet).
- `campaign_gm_grants: list[CampaignSummaryOut]` — every campaign this user GMs (`User.campaign_gms`, joined through to `Campaign`, reusing [RFC 0003](0003-tenant-campaign-read-api.md)'s `CampaignSummaryOut`).

`PlayerSummaryOut(id, tenant_id, campaign_id, characters: list[CharacterSummaryOut])` — a bare `Player` row alone (just ids) wouldn't answer anything useful here; a caller reading their own `/me` needs to know not just *which* campaigns they're in but *which characters they play there*, resolved through `character_player` the same way `PlayerOut` (below) resolves it for the campaign-scoped roster view. Unlike `PlayerOut`, this one carries its own `tenant_id`/`campaign_id` explicitly — `/me` spans every tenant, so there's no URL scoping to infer them from the way a campaign-nested route already has both in its path.

This one response is the concrete answer to "user → owner\|orga\|member of tenant → \[player(campaign) \| GM(campaign)\]" for the caller's own identity — the single place a client reads "everything I am, everywhere," matching this endpoint's existing "prove identity end-to-end" spirit rather than adding a second, competing "who am I" shape elsewhere.

### Tenant-wide roster

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants/{tenant_id}/memberships` | `get_tenant_context` | `Page[TenantRosterEntryOut]` |

**Broadened from a pure membership list to the tenant's full roster** — every user with *any* standing in this tenant, not just its tenant-wide admins. Three variants, a discriminated union matching the `PayloadOut` precedent ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)) rather than one schema with fields that are only sometimes meaningful:

```python
class MembershipRosterEntryOut(BaseModel):
    kind: Literal["membership"] = "membership"
    user_id: uuid.UUID
    role: str  # "owner" | "orga"
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

class PlayerRosterEntryOut(BaseModel):
    kind: Literal["player"] = "player"
    user_id: uuid.UUID
    campaign_id: uuid.UUID
    characters: list[CharacterSummaryOut]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

class GmRosterEntryOut(BaseModel):
    kind: Literal["gm"] = "gm"
    user_id: uuid.UUID
    campaign_id: uuid.UUID
    created_by: uuid.UUID | None

TenantRosterEntryOut = Annotated[
    MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut, Field(discriminator="kind")
]
```

`created_by`/`updated_by` ([RFC 0010](0010-created-by-updated-by-attribution.md)) — `MembershipRosterEntryOut`/`PlayerRosterEntryOut` get both (`membership`/`player` each have the full pair); `GmRosterEntryOut` gets `created_by` only, matching `campaign_gm`'s own lighter, create-only shape (a grant is never "updated," only made or revoked).

One row per relationship, not per user — a user who is `ORGA`, GMs one campaign, and plays in another appears three times, once per capacity, the same flat shape `Membership`/`Player`/`CampaignGm` already have as separate tables rather than one aggregated per-user summary. `PlayerRosterEntryOut` rows are sourced the same way [RFC 0003](0003-tenant-campaign-read-api.md)'s `is_tenant_participant` already queries — every `Player` row where `Player.tenant_id` matches (already denormalized, no join through `Campaign` needed), each with `characters` resolved through `character_player` exactly like `PlayerOut` below. `GmRosterEntryOut` rows are sourced the same way, one per `CampaignGm` row in the tenant (`CampaignGm.tenant_id`, denormalized the same way) — no `characters` field, since GM-ing isn't itself tied to any character; a GM who also plays a PC in some campaign already gets their own separate `player`-kind row for that.

**Naming tension, confirmed rather than resolved by renaming**: the path (`.../memberships`) still says "membership" specifically, and this response is broader than that now — flagged, and deliberately kept as-is anyway, a minimal, additive change rather than a rename plus whatever churn that implies for anything already calling it. `TenantMembershipOut` itself doesn't survive this revision either way, replaced outright by `TenantRosterEntryOut`.

Still gated by `get_tenant_context`, unchanged: only tenant-wide members see the *whole* roster this way, consistent with that dependency's existing scope. An ordinary player doesn't need this endpoint to find their own standing — `/me` already covers that.

### Campaign roster: players, their characters, and GMs

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}/players` | `get_campaign_context` | `Page[PlayerOut]` |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}` | `get_campaign_context` | `PlayerDetailOut` |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}/gms` | `get_campaign_context` | `list[GmOut]` (unpaginated) |

`PlayerOut(id, user_id, characters: list[CharacterSummaryOut], created_by: uuid.UUID | None, updated_by: uuid.UUID | None)` — the last two per [RFC 0010](0010-created-by-updated-by-attribution.md). `characters` resolved through `character_player` (join `Player.character_links` → `Character`, retargeted from `Being` — see the schema addition above), giving "which of my characters, in which campaign" in one call, the exact join [RFC 0002](0002-campaign-player-character-model.md) itself flagged as the roster-view's one extra hop ("an extra join, not a redesign"). `PlayerDetailOut` is the same shape; there's nothing a detail view adds beyond the list row here (`Player` has no columns the summary omits), unlike `Entity`'s list/detail split — no `EntitySummary`-style thinning is needed because `PlayerOut` is already minimal.

`GmOut(user_id)` (campaign_id/tenant_id are already in the path, no need to repeat them in every row). The GM list is **unpaginated**, matching `OwnedByResponse`'s existing precedent of skipping pagination for a collection that's inherently small and bounded by construction (a campaign realistically has a handful of GMs, not thousands) — a `Page[...]` envelope here would be pure ceremony.

### Tenant-wide character roster

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants/{tenant_id}/characters` | `get_tenant_context` | `Page[CharacterSummaryOut]` |
| GET | `/tenants/{tenant_id}/characters/{character_id}` | `get_tenant_context` | `CharacterOut` |

**Now specifically a roster of `Character` rows, not every `Being`.** A bare `being` with no `character` row (an unnamed monster stub, a background NPC never worth individual tracking) doesn't appear here at all — this endpoint lists tracked individuals, matching what "a character" means in the domain sense the rest of this RFC already uses that word for. Deliberately bare-tenant-scoped, not campaign-nested: a character has no single fixed campaign (roster reuse, [ADR 0025](../adr/0025-character-being-and-ownership.md)), so "list every character in this tenant" is the only shape that makes sense without picking one campaign arbitrarily — this mirrors [docs/domain/client-views.md](../domain/client-views.md)'s "GM gets a web view across every player and their possessions," which is exactly a tenant-wide, not campaign-scoped, view. Gating it to `get_tenant_context` is what makes that safe: only tenant-wide members (who already see everything) reach it, so there's no separate visibility filtering needed the way [ADR 0028](../adr/0028-knowledge-and-group-membership.md)'s `information_visibility` module has to do for entity descriptions — an ordinary player never reaches this endpoint at all, campaign-nested rosters above are their path.

`CharacterSummaryOut(entity_id, name, is_pc)`; `CharacterOut` adds `owner_player_id: uuid.UUID | None`, `players: list[PlayerSummaryOut]` (via `character_player` again, this time from the character's side — `Character.player_links`, retargeted above), and `created_by`/`updated_by: uuid.UUID | None` ([RFC 0010](0010-created-by-updated-by-attribution.md) — `character`'s own columns, recording who *promoted* this character, not who created the underlying `being`; see that RFC's own open question for why the two are kept distinct). `name` is still plain `Entity.name` (the internal/reference name, [ADR 0012](../adr/0012-entity-table.md)), not `v_character.title` — this endpoint is identity/roster, not the fuller narrative view `v_character` exists for; reaching for the view here would just be a second, unnecessary join for data these two schemas don't need. `is_pc` is the derived fact RFC 0001/RFC 0002 already establish (`owner_player_id IS NOT NULL` — now read off `Character`, not `Being`), computed in the schema's `from_character` classmethod, not stored.

**Accepted minor redundancy**: reusing `PlayerSummaryOut` (now carrying its own `characters` list, above) for `CharacterOut.players` means each returned player entry redundantly re-includes the very character being viewed, among any others that player controls — a small, self-referential wart, not a bug, and not worth a fourth schema variant just to trim it.

New exceptions (`exceptions.py`): `PlayerNotFoundError`, `CharacterNotFoundError` — same one-per-condition convention as every existing `NotFoundProblem` subclass. `CharacterNotFoundError` now also covers "this is a `being` with no `character` row" the same non-enumerable way every other not-found condition in this codebase collapses distinct causes into one response.

New schema modules: `schemas/players.py` (`PlayerSummaryOut`, `PlayerOut`, `PlayerDetailOut`), `schemas/characters.py` (`CharacterSummaryOut`, `CharacterOut`), plus `MembershipRosterEntryOut`/`PlayerRosterEntryOut`/`TenantRosterEntryOut`/`GmOut` added to `schemas/tenants.py`/a new `schemas/campaigns.py`-adjacent home (`GmOut` fits naturally alongside campaign-roster concerns, so it lives in `schemas/campaigns.py` rather than a one-class module of its own).

## Not in scope

**Any mutation** — creating/removing memberships, players, characters, or GM grants is [RFC 0007](0007-user-player-character-crud-api.md) (players/characters/membership) and [RFC 0006](0006-campaign-crud-api.md) (GM grants, campaign-scoped).

**Full character sheets** (stats, inventory, descriptions) — already served by the existing `entities`/`items` read API ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)); `Being.entity_id` *is* an `entity.id`, so `GET /tenants/{tenant_id}/entities/{character_id}` already answers "what does this character know/have" today. This RFC's `CharacterOut` only answers "who is this, and who plays them" — duplicating stat/inventory fields here would just be a second, driftable copy of what that endpoint already returns.

**Group knowers** (`group_member`) — [ADR 0028](../adr/0028-knowledge-and-group-membership.md) built groups purely as a knowledge-visibility mechanism with no REST surface of their own; this RFC doesn't add one, since nothing asked for group management specifically.

**Custom fields on `character`.** The whole reason this table exists is to have somewhere to add them later — none are added now; designing them ahead of an actual need would be exactly the speculative work this codebase's own discipline avoids.

**Updating RFC 0007's character-creation flow.** [RFC 0007](0007-user-player-character-crud-api.md)'s `POST /characters` currently creates `Entity`+`Being`+`CharacterPlayer` links; it now also needs to create the `Character` row in the same transaction, and needs to decide what `DELETE /characters/{id}` means now that "delete just the `character` layer, demoting back to a plain `being`" and "destroy the whole entity" are two different, both-meaningful operations. Flagged for that RFC, not resolved here.

## Open questions

**Tenant-admin opt-out visibility.** There's no dedicated `GET .../admin-opt-outs` endpoint here — a caller's own opt-out state is implicit in whether they show up as a player/GM elsewhere, and a dedicated listing wasn't asked for. [RFC 0006](0006-campaign-crud-api.md) covers the mutation side (opting in/out, `TenantAdminCampaignOptOut` — renamed from `OrgaCampaignOptOut` once [RFC 0003](0003-tenant-campaign-read-api.md) let `OWNER` share the same bypass); a read endpoint for "which campaigns has this admin opted out of" can be added later without redesigning anything here if it turns out to be needed.

**`PlayerOut.characters` versus roster-reuse across campaigns.** A character linked to a player in *this* campaign might also appear in a sibling campaign's roster (same tenant, [ADR 0025](../adr/0025-character-being-and-ownership.md)'s reuse mechanism) — this endpoint doesn't flag that fact anywhere in the response. Not addressed here; the tenant-wide `GET /tenants/{tenant_id}/characters/{character_id}` is where a client would discover every campaign a character is linked to, by design (that's exactly what its own `players` field, unioned across campaigns, is for).

**Should a bare-`being` listing exist for what this RFC's roster now excludes?** Not built — nothing asked for a "list every background NPC too" view, and the tenant-wide `entities` read API ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)) already lists every entity regardless of concrete type, just without `character`'s richer shape.

**Is retargeting `character_player`/`group_member` to require a `Character` row the right call?** Flagged in the schema-addition section above as a deliberate tightening rather than a side effect — but it's a genuine reversal of what [ADR 0025](../adr/0025-character-being-and-ownership.md)/[ADR 0028](../adr/0028-knowledge-and-group-membership.md) originally allowed (any `being`, tracked or not, could be rostered or grouped). Revisit if a GM wants to roster or group-link a plain background NPC without first "promoting" it to a full character.

## Consequences

- **This RFC now needs a migration**, unlike its first draft: a new `character` table (`entity_id` PK/FK → `being.entity_id` `ON DELETE CASCADE`, `tenant_id`, `owner_player_id`) plus its `tenant_isolation` RLS policy; `being.owner_player_id` dropped (moved to `character` — trivial pre-release, no real character data exists yet); `character_player.character_entity_id`/`group_member.character_entity_id` retargeted from `being.entity_id` to `character.entity_id`; a new `v_character` view (`security_invoker=true`, excluded from Alembic autogenerate the same way `v_item`/`v_item_instance` already are, [ADR 0019](../adr/0019-item-and-v-item.md)); `ItemViewMixin` renamed `EntityViewMixin` and shared by all three views. [ADR 0025](../adr/0025-character-being-and-ownership.md) (`being`'s original shape, `character_player`'s original target) and [ADR 0028](../adr/0028-knowledge-and-group-membership.md) (`group_member`'s original target) both need superseding notes once this becomes an ADR.
- **`docs/architecture/diagrams/domain-model-er.md` needs a real update**: a new `CHARACTER` box layered under `BEING` (not a sibling extension of `ENTITY` the way every other concrete type is drawn), `owner_player_id` moving boxes, and `character_player`/`group_member`'s edges retargeting. Not done as part of this RFC — the ER-diagram step of the usual slice process, once this is actually picked up.
- [RFC 0010](0010-created-by-updated-by-attribution.md) adds `created_by`/`updated_by` to this same new `character` table, plus to `membership`/`player` — one combined migration in practice once both RFCs are actually built, not two separate ones.
- [RFC 0007](0007-user-player-character-crud-api.md) needs a follow-up pass — flagged above, not fixed here, to keep this revision scoped to RFC 0004 itself.
- [RFC 0009](0009-campaign-scoped-gm-visibility.md)'s reachability walk ("every `Being` linked via `CharacterPlayer` to a `Player`") needs a terminology pass — the join target is now `Character`, though the actual entity-id set it produces is unaffected (a `Character`'s `entity_id` still just *is* an `entity.id`, same as before).
- `membership`/`player`/`campaign_gm` are unaffected by any of the above — no migration need beyond `character`/`being`/`character_player`/`group_member`.
- Closes the gap [ADR 0022](../adr/0022-user-tenant-membership.md) and [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md) both explicitly flagged and deferred: an ordinary player or GM can now reach data about their own campaign membership without needing (and wrongly failing) a tenant-wide `Membership` check.
- `Player.owned_beings` (the relationship backing `owner_player_id`) follows the column to `Character` and is renamed `Player.owned_characters` accordingly — a plain `being` was never a valid target for it, so nothing meaningful is lost by the rename, just made accurate.
- `PlayerOut`/`CharacterOut`/`PlayerSummaryOut`/`PlayerRosterEntryOut`'s eager-load chains (`character_links`/`player_links`/`owned_characters`) need the same `selectinload`-up-front discipline as every other relationship in this codebase (`lazy="raise_on_sql"`, [ADR 0018](../adr/0018-sqlalchemy-modeling-conventions.md)) — skipping it raises, it doesn't silently N+1. `GET /me` and the tenant roster both gain a real eager-load chain they didn't need before this revision (`User.players`/tenant-wide `Player` query → `character_links` → `Character` → `Being` → `Entity`, for each row's `characters` list — one hop longer than before this revision, now that `Character` sits between `CharacterPlayer` and `Being`).
- `tests/conftest.py` has no `make_campaign`/`make_being`/`make_character`/`make_campaign_gm` helper today — every existing test constructs these inline, repeatedly, across 8+ files. Implementing this RFC's tests is a natural point to promote shared helpers, mirroring how `make_tenant`/`make_player` were themselves promoted after duplication was noticed ([ADR](../adr/0023-authgear-token-verification.md) history) — not this RFC's decision to make, but worth flagging so it isn't rediscovered as a surprise mid-implementation.
