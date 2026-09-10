# RFC: User, membership, player, character, and GM read REST API

Status: proposed — builds on [RFC 0003](0003-tenant-campaign-read-api.md)'s `get_campaign_context`; no schema changes

## Context

The access/role graph — who is a tenant owner/orga, who plays which campaign as which character, who GMs which campaign — is fully built ([ADR 0022](../adr/0022-user-tenant-membership.md)/[ADR 0024](../adr/0024-campaign-and-player.md)/[ADR 0025](../adr/0025-character-being-and-ownership.md)/[ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md)) but almost entirely unreadable over HTTP. The one exception, `GET /me` ([routers/users.py](../../apps/api/src/lorenzo_api/routers/users.py)), exists "purely to prove the whole pipeline end-to-end... not the start of a fuller `/users` API" (its own docstring) and returns only tenant-wide `Membership` rows — nothing about `Player`, `Being`/character, or `CampaignGm`.

This is deliberately scoped narrower than [RFC 0003](0003-tenant-campaign-read-api.md): that RFC exposes *tenant* and *campaign* as resources; this one exposes *who occupies which role in them* — the "user → owner\|orga\|member of tenant → \[player(campaign) → character \| GM(campaign)\]" graph, in the user's own framing. It deliberately does **not** re-expose entity stats/inventory (that's the existing `entities`/`items` read API, an orthogonal axis already built) — a character here is identified and rostered, not fully described.

## Decision

Every campaign-nested endpoint below is gated by [RFC 0003](0003-tenant-campaign-read-api.md)'s `get_campaign_context`, not `get_tenant_context` — an ordinary player or GM reaching their own campaign's roster has no tenant-wide `Membership` row to satisfy the older, stricter gate, exactly the gap [ADR 0022](../adr/0022-user-tenant-membership.md) named. Bare tenant-level collections stay on `get_tenant_context`, per that RFC's access-gating rule.

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

**Broadened from a pure membership list to the tenant's full roster** — every user with *any* standing in this tenant, not just its tenant-wide admins. Two variants, a discriminated union matching the `PayloadOut` precedent ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)) rather than one schema with fields that are only sometimes meaningful:

```python
class MembershipRosterEntryOut(BaseModel):
    kind: Literal["membership"] = "membership"
    user_id: uuid.UUID
    role: str  # "owner" | "orga"

class PlayerRosterEntryOut(BaseModel):
    kind: Literal["player"] = "player"
    user_id: uuid.UUID
    campaign_id: uuid.UUID
    characters: list[CharacterSummaryOut]

TenantRosterEntryOut = Annotated[
    MembershipRosterEntryOut | PlayerRosterEntryOut, Field(discriminator="kind")
]
```

One row per relationship, not per user — a user who is both `ORGA` and a player in two campaigns appears three times, once per capacity, the same flat shape `Membership`/`Player` already have as separate tables rather than one aggregated per-user summary. `PlayerRosterEntryOut` rows are sourced the same way [RFC 0003](0003-tenant-campaign-read-api.md)'s `is_tenant_participant` already queries — every `Player` row where `Player.tenant_id` matches (already denormalized, no join through `Campaign` needed), each with `characters` resolved through `character_player` exactly like `PlayerOut` below.

**Naming tension, flagged rather than silently resolved**: the path (`.../memberships`) and the old schema name both said "membership" specifically, and this response is no longer just that. Kept the path as-is here to stay a minimal, additive change rather than a rename — but `TenantMembershipOut` doesn't survive this revision, replaced outright by `TenantRosterEntryOut`. Revisit the path itself if this reads as confusing in practice.

Still gated by `get_tenant_context`, unchanged: only tenant-wide members see the *whole* roster this way, consistent with that dependency's existing scope. An ordinary player doesn't need this endpoint to find their own standing — `/me` already covers that.

### Campaign roster: players, their characters, and GMs

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}/players` | `get_campaign_context` | `Page[PlayerOut]` |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}` | `get_campaign_context` | `PlayerDetailOut` |
| GET | `/tenants/{tenant_id}/campaigns/{campaign_id}/gms` | `get_campaign_context` | `list[GmOut]` (unpaginated) |

`PlayerOut(id, user_id, characters: list[CharacterSummaryOut])` — `characters` resolved through `character_player` (join `Player.character_links` → `Being`), giving "which of my characters, in which campaign" in one call, the exact join [RFC 0002](0002-campaign-player-character-model.md) itself flagged as the roster-view's one extra hop ("an extra join, not a redesign"). `PlayerDetailOut` is the same shape; there's nothing a detail view adds beyond the list row here (`Player` has no columns the summary omits), unlike `Entity`'s list/detail split — no `EntitySummary`-style thinning is needed because `PlayerOut` is already minimal.

`GmOut(user_id)` (campaign_id/tenant_id are already in the path, no need to repeat them in every row). The GM list is **unpaginated**, matching `OwnedByResponse`'s existing precedent of skipping pagination for a collection that's inherently small and bounded by construction (a campaign realistically has a handful of GMs, not thousands) — a `Page[...]` envelope here would be pure ceremony.

### Tenant-wide character roster

| Method | Path | Access gate | Response |
| --- | --- | --- | --- |
| GET | `/tenants/{tenant_id}/characters` | `get_tenant_context` | `Page[CharacterSummaryOut]` |
| GET | `/tenants/{tenant_id}/characters/{character_id}` | `get_tenant_context` | `CharacterOut` |

Deliberately bare-tenant-scoped, not campaign-nested: a character (`Being`) has no single fixed campaign (roster reuse, [ADR 0025](../adr/0025-character-being-and-ownership.md)), so "list every character in this tenant" is the only shape that makes sense without picking one campaign arbitrarily — this mirrors [docs/domain/client-views.md](../domain/client-views.md)'s "GM gets a web view across every player and their possessions," which is exactly a tenant-wide, not campaign-scoped, view. Gating it to `get_tenant_context` is what makes that safe: only tenant-wide members (who already see everything) reach it, so there's no separate visibility filtering needed the way [ADR 0028](../adr/0028-knowledge-and-group-membership.md)'s `information_visibility` module has to do for entity descriptions — an ordinary player never reaches this endpoint at all, campaign-nested rosters above are their path.

`CharacterSummaryOut(entity_id, name, is_pc)`; `CharacterOut` adds `owner_player_id: uuid.UUID | None` and `players: list[PlayerSummaryOut]` (via `character_player` again, this time from the character's side — `Being.player_links`). `is_pc` is the derived fact RFC 0001/RFC 0002 already establish (`owner_player_id IS NOT NULL`), computed in the schema's `from_being` classmethod, not stored.

**Accepted minor redundancy**: reusing `PlayerSummaryOut` (now carrying its own `characters` list, above) for `CharacterOut.players` means each returned player entry redundantly re-includes the very character being viewed, among any others that player controls — a small, self-referential wart, not a bug, and not worth a fourth schema variant just to trim it.

New exceptions (`exceptions.py`): `PlayerNotFoundError`, `CharacterNotFoundError` — same one-per-condition convention as every existing `NotFoundProblem` subclass.

New schema modules: `schemas/players.py` (`PlayerSummaryOut`, `PlayerOut`, `PlayerDetailOut`), `schemas/characters.py` (`CharacterSummaryOut`, `CharacterOut`), plus `MembershipRosterEntryOut`/`PlayerRosterEntryOut`/`TenantRosterEntryOut`/`GmOut` added to `schemas/tenants.py`/a new `schemas/campaigns.py`-adjacent home (`GmOut` fits naturally alongside campaign-roster concerns, so it lives in `schemas/campaigns.py` rather than a one-class module of its own).

## Not in scope

**Any mutation** — creating/removing memberships, players, characters, or GM grants is [RFC 0007](0007-user-player-character-crud-api.md) (players/characters/membership) and [RFC 0006](0006-campaign-crud-api.md) (GM grants, campaign-scoped).

**Full character sheets** (stats, inventory, descriptions) — already served by the existing `entities`/`items` read API ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)); `Being.entity_id` *is* an `entity.id`, so `GET /tenants/{tenant_id}/entities/{character_id}` already answers "what does this character know/have" today. This RFC's `CharacterOut` only answers "who is this, and who plays them" — duplicating stat/inventory fields here would just be a second, driftable copy of what that endpoint already returns.

**Group knowers** (`group_member`) — [ADR 0028](../adr/0028-knowledge-and-group-membership.md) built groups purely as a knowledge-visibility mechanism with no REST surface of their own; this RFC doesn't add one, since nothing asked for group management specifically.

## Open questions

**Tenant-admin opt-out visibility.** There's no dedicated `GET .../admin-opt-outs` endpoint here — a caller's own opt-out state is implicit in whether they show up as a player/GM elsewhere, and a dedicated listing wasn't asked for. [RFC 0006](0006-campaign-crud-api.md) covers the mutation side (opting in/out, `TenantAdminCampaignOptOut` — renamed from `OrgaCampaignOptOut` once [RFC 0003](0003-tenant-campaign-read-api.md) let `OWNER` share the same bypass); a read endpoint for "which campaigns has this admin opted out of" can be added later without redesigning anything here if it turns out to be needed.

**Should `CampaignGm` grants be a third roster variant** (`kind="gm"`, alongside `membership`/`player` above)? Not added here — only players were asked for, and today's tenant-wide roster genuinely doesn't show GMs at all, same gap it had before this revision. The discriminated-union shape makes adding one a small, additive change later, not a redesign.

**`PlayerOut.characters` versus roster-reuse across campaigns.** A character linked to a player in *this* campaign might also appear in a sibling campaign's roster (same tenant, [ADR 0025](../adr/0025-character-being-and-ownership.md)'s reuse mechanism) — this endpoint doesn't flag that fact anywhere in the response. Not addressed here; the tenant-wide `GET /tenants/{tenant_id}/characters/{character_id}` is where a client would discover every campaign a character is linked to, by design (that's exactly what its own `players` field, unioned across campaigns, is for).

## Consequences

- No migration: every table this RFC reads (`membership`, `player`, `being`, `character_player`, `campaign_gm`) already exists.
- Closes the gap [ADR 0022](../adr/0022-user-tenant-membership.md) and [ADR 0026](../adr/0026-campaign-gm-orga-and-access-rule.md) both explicitly flagged and deferred: an ordinary player or GM can now reach data about their own campaign membership without needing (and wrongly failing) a tenant-wide `Membership` check.
- `PlayerOut`/`CharacterOut`/`PlayerSummaryOut`/`PlayerRosterEntryOut`'s eager-load chains (`character_links`/`player_links`/`owned_beings`) need the same `selectinload`-up-front discipline as every other relationship in this codebase (`lazy="raise_on_sql"`, [ADR 0018](../adr/0018-sqlalchemy-modeling-conventions.md)) — skipping it raises, it doesn't silently N+1. `GET /me` and the tenant roster both gain a real eager-load chain they didn't need before this revision (`User.players`/tenant-wide `Player` query → `character_links` → `Being` → `Entity`, for each row's `characters` list).
- `tests/conftest.py` has no `make_campaign`/`make_being`/`make_campaign_gm` helper today — every existing test constructs these inline, repeatedly, across 8+ files. Implementing this RFC's tests is a natural point to promote shared helpers, mirroring how `make_tenant`/`make_player` were themselves promoted after duplication was noticed ([ADR](../adr/0023-authgear-token-verification.md) history) — not this RFC's decision to make, but worth flagging so it isn't rediscovered as a surprise mid-implementation.
