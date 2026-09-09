# 0024 - Campaign and Player

Status: accepted

## Context

[RFC 0002](../rfcs/0002-campaign-player-character-model.md) splits Tenant (the persistent world, ADR 0022) from Campaign (a specific play-through inside it - a team can run several LARPs in the same setting, or a homebrew world can host both a long campaign and an unrelated one-shot, all the same tenant). This ADR builds the two tables RFC 0002's own "scope for the first slice" lists first: `campaign` and `player`.

## Decision

### `campaign(id, tenant_id, name, game_system, created_at, updated_at)`

`game_system` is required, no default - RFC 0002's own stated reason: it's "the natural home for RFC 0001's open question about multi-game-system stats" - which prototype variant ("Sword (D&D 5e)" vs. "Sword (Blades in the Dark)") a campaign's entities resolve through is a property of the campaign, not the entity. Unlike `tenant.name` (ADR 0022), no server-side default: `campaign` is a brand-new table, so there are no existing bare-constructor test call sites to avoid retrofitting - every test can and does pass a real `game_system` from the start.

### `player(id, user_id, campaign_id, tenant_id, created_at, updated_at)`

Matches RFC 0002's own literal column list (`player(id, user_id, campaign_id)`) - a surrogate `id`, not a composite PK like `membership`'s: the RFC treats Player as its own addressable entity (referenced later by `character_player`/`campaign_gm` in upcoming sub-slices), not a pure join row. `UNIQUE(campaign_id, user_id)` added on top - not in the RFC's text, but a reasonable minimal safeguard (matching e.g. `stat_definition`'s `UNIQUE(tenant_id, name)`, `information`'s `UNIQUE(entity_id, type)`): a user having two Player rows in the same campaign would be a broken, ambiguous state ("which one is *the* player controlling my characters here?").

`tenant_id` is a direct column here, not just reachable via `campaign_id` - RFC 0002's own blanket rule ("every table introduced in this RFC gets its own tenant_id column and RLS policy, no exceptions") applies. This makes `player.tenant_id` a denormalized copy of `campaign.tenant_id` (the same shape as `entity_stat_group.tenant_id` relative to `entity.tenant_id`) rather than an irreducible part of its identity (unlike `membership.tenant_id`, ADR 0022) - kept consistent by application code, not a DB-level constraint, matching this schema's existing precedent (no such cross-FK consistency CHECK exists anywhere else in it either).

Both tables get the standard `ENABLE`+`FORCE` RLS + `tenant_isolation` policy, identical in shape to every table before them - no self-access carve-out like `membership`'s (ADR 0023): nothing about Campaign/Player needs cross-tenant reads the way `GET /me` did.

## Consequences

- `campaign_gm` (a future sub-slice) will reference `campaign.id` directly, alongside `player`, as RFC 0002's own next step once GM scope is built.
- No REST endpoints in this sub-slice - matching the vertical slice's own stated scope (data model + auth mechanism first, a fuller REST surface is explicitly deferred).
