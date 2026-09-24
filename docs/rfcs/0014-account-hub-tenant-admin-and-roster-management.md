# RFC: `apps/account-hub` — tenant/campaign administration and roster reuse

Status: accepted — landed in full across [ADR 0074](../adr/0074-account-hub-campaign-visibility-and-user-lookup.md) (a)/(b), [ADR 0076](../adr/0076-account-hub-tenant-admin-actions.md) (c)/(d)/(e), and [ADR 0079](../adr/0079-account-hub-roster-reuse-and-being-handoff.md) (f)/(g); ADR 0076's addendum also added editing an existing campaign, which "What this doesn't cover" below had left out until asked for

## Context

Manual testing of the Characters sub-slice (RFC 0013) surfaced a real, structural constraint rather than a bug: `/characters` only offers "create a character" for campaigns the caller already has a `Player` row in, because `POST /tenants/{id}/campaigns/{id}/players` is gated by `can_manage_campaign` — a campaign's own GM or a tenant owner/orga, never a self-service join (the API's own docstring names this explicitly, citing RFC 0007's still-open "no invite-link/visibility mechanism exists yet that would make self-service joining safe"). A plain player genuinely cannot add themselves to a campaign's roster, and no UI change can route around that.

Working through what *is* possible surfaced a related, connected set of capabilities this app doesn't cover yet: creating campaigns, assigning/revoking GMs, inviting players into a campaign's roster, and reusing an existing character or being across campaigns in the same tenant (`character_player`'s own roster-reuse design, RFC 0002/ADR 0025). All of these are real, already-built API surface — this RFC scopes *account-hub's* access to them, not new backend work.

## Decision

Seven pieces, grouped by who acts and what they touch. All go through the existing API and its existing authorization exactly as every prior slice has — this app still never re-implements or second-guesses a permission check.

### 1. Show every campaign in a tenant on `/characters`, not just ones already played

Currently `/characters` only iterates `MeOut.players[]`. Extend it to also list every campaign from `GET /tenants/{id}/campaigns` per tenant the caller is any kind of participant in (reusing the exact aggregation `/tenants` already does), so a caller can see campaigns they don't yet have a character in. Campaigns where they already have a `PlayerContextOut` entry show the existing create/rename UI (RFC 0013, unchanged); campaigns where they don't show a "you don't play here yet" state, with an action only if there's actually something for *them* to do — none of the actions below are self-service, so a plain participant sees this as read-only context, not a dead button.

### 2. Tenant owner/orga: create a campaign

`POST /tenants/{id}/campaigns` (`CampaignCreate`: `name`, `game_system`, `slug`, `description`, `secret` — no defaults except `secret: false`, all required). Gated client-side by the caller's own `TenantSummaryOut.role` (`owner`/`orga`) matching the endpoint's real gate (`get_tenant_context` - tenant-wide membership, not per-campaign) — shown on `/tenants`, alongside that tenant's existing campaign list.

### 3. Tenant owner/orga: assign or revoke a campaign's GM

`PUT`/`DELETE /tenants/{id}/campaigns/{id}/gms/{user_id}` (idempotent either direction). Needs resolving a person to a `user_id` first — `GET /users/by-email/{email}` or `GET /users/by-nickname/{nickname}` (`UserRefOut`, ADR 0055), exact-match only, open to any authenticated caller. Shown on `/tenants`, per campaign row, gated the same way as campaign creation (tenant owner/orga) — `GET /tenants/{id}/campaigns/{id}/gms` lists current GMs so revoke has something concrete to act on, not a blind text field.

### 4. Tenant owner/orga, or that campaign's own GM: invite a player

`POST /tenants/{id}/campaigns/{id}/players` (`PlayerCreate`: bare `user_id`) — same user-lookup-by-email/nickname mechanism as (3). This is the actual fix for what manual testing found: it's not that account-hub was wrong to gate character creation, it's that inviting was never built at all. Gated client-side by "is a tenant owner/orga of this tenant, or already appears in `campaign_gm_grants` for this specific campaign" — mirrors `can_manage_campaign`'s real two-way gate rather than approximating it with just one branch.

### 5. Player: reuse an existing character across campaigns in the same tenant

Once invited into a new campaign (a `PlayerContextOut` now exists for it, per RFC 0002's `character_player` roster-reuse design), a player may already control a character in a *different* campaign in the *same* tenant and want to bring it along rather than create a new one. `PUT /tenants/{id}/characters/{character_id}/players/{player_id}` (idempotent roster-link, `CharacterOut` back) does exactly this — no new schema, the same sub-resource ADR 0036/RFC 0007 already built. On `/characters`, a campaign the caller has just been invited to (a player row with zero characters yet) offers both "create a new character" (RFC 0013, unchanged) and "use one of my existing characters in this tenant" (new — sourced from the caller's own `MeOut.players[].characters[]` across every *other* campaign in the same tenant, deduplicated by `entity_id`).

### 6. GM: hand an existing being to a player as their character in a campaign

Mechanically the same roster-link endpoint as (5), initiated from `/beings` instead: a GM picks one of the tenant's beings, picks (or invites, reusing (4)) a player in a campaign they GM, and links them. Unlike (5), the target character currently has `is_pc: false` (no `owner_player_id`) — this RFC's decision is to **also** set `owner_player_id` to the new player, via the existing `PATCH /tenants/{id}/characters/{id}` (`CharacterUpdate.owner_player_id`), immediately after the roster-link call. "Use a being as a character" is read as a real, lasting handoff — the entity stops being GM-only from that point on, indistinguishable from any other player character — not a temporary loan. If that reading turns out to be wrong in practice, this is a one-line, easily-revisited call to make optional later; recorded here so the choice is explicit rather than silently picked mid-implementation.

### What this doesn't cover

- **Revoking a player's roster link, or un-inviting a player from a campaign entirely.** `DELETE /tenants/{id}/campaigns/{id}/players/{player_id}` and the character-player `DELETE` both already exist server-side; genuinely out of scope for this RFC, not designed here, until asked for.
- **Editing a campaign's own fields after creation** (`PATCH /tenants/{id}/campaigns/{id}`) — creation only, per this RFC.
- **Any change to `apps/api` itself.** Every capability above already exists; this is entirely about `account-hub` gaining UI for API surface that was already built and already correctly authorized.

## Consequences

- `/characters` gains real write actions beyond RFC 0013's original player-only, own-campaigns-only scope: campaign creation and GM assignment are tenant-admin actions, surfaced on `/tenants`, not `/characters`.
- A user-lookup-by-email-or-nickname UI pattern (small input, exact match, clear "not found" state) is needed for both (3) and (4) — built once, reused twice, not two separate implementations.
- `/beings` gains a real cross-page dependency: handing a being to a player needs that campaign's own player roster (possibly inviting one first, capability (4)), which didn't exist when Beings shipped.
- Sub-slices, smallest first, each its own ADR as it's actually decided/built (mirroring RFC 0013's own cadence): (a) campaign visibility on `/characters`; (b) user lookup, as its own small reusable piece; (c) campaign creation; (d) GM assign/revoke; (e) player invite; (f) character roster-reuse; (g) being-to-player handoff.
