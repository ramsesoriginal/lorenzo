# 0081 - account-hub: campaign roster view, being search, self-service leave

Status: accepted

## Context

Sub-slices (a)/(b)/(c) of [RFC 0017](../rfcs/0017-account-hub-roster-tenant-admin-and-notifications.md), grouped into one ADR because all three are read-mostly, player/GM-facing additions to `/tenants`, `/beings`, and `/characters` that were already fully scoped by the RFC - no design debate left to record beyond confirming what was actually built.

## Decision

### (a) Campaign roster view, and a "while here" name upgrade

`GET /tenants/{id}/memberships` (`RosterEntry`, a discriminated union on `kind`) is fetched once per tenant in `tenants.astro` and filtered client-side, per campaign, to `kind === 'player' || kind === 'gm'` rows matching that campaign's id. Rendered via a new `src/lib/campaignRosterUi.ts` (`renderCampaignRoster`), showing each entry's resolved display name (`displayNameFor`, `format.ts`) and, for players, their characters. Visible to every tenant-wide member, not gated to admin/GM, matching `list_tenant_roster`'s own gate.

The same roster fetch resolves real names for two pre-existing raw-`user_id` displays: the GM-revoke list (`gmAndPlayerUi.ts`'s `renderGmManagement`, ADR 0076) and the being-handoff existing-player list (`beings.astro`'s `renderHandoffPanel`, ADR 0079) - both now take the fetched roster and call a new `resolveDisplayName(roster, userId)` (`format.ts`) instead of printing the bare id.

### (b) Being search

`beings.astro`'s per-tenant section gained a `<input type="search">`, debounced 300ms, calling the already-existing `listBeings(tenantId, q)` (ADR 0079). No new API surface - the results area is re-rendered independently of the create-form below it, so a search in progress doesn't disturb "create a new being."

### (c) Self-service leave a campaign

`characters.astro`'s per-campaign section gained a "Leave this campaign" button, shown whenever the caller has a `PlayerContextOut` there, behind a `window.confirm()` naming the consequence (every character link that player row grants is removed, not just an inbox item). Calls `DELETE /tenants/{id}/campaigns/{id}/players/{player_id}` (`leaveCampaign`, `tenants.ts`) with the caller's own player id, then refreshes.

## Consequences

- `src/lib/format.ts` gains `displayNameFor` (the `display_name ?? nickname ?? user_id` chain) and `resolveDisplayName` (looks a `user_id` up across a `RosterEntry[]`), both pure and unit-tested (`format.spec.ts`).
- `src/lib/types.ts` gains `RosterEntry` (`MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut`), checked against the live schema.
- `src/lib/tenants.ts` gains `listTenantRoster` and `leaveCampaign`.
- No behavior change to the create/rename flows already on `/beings`/`/characters` - these are additive.
