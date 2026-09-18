# 0076 - account-hub: campaign creation, GM assign/revoke, player invite

Status: accepted

## Context

Sub-slices (c)/(d)/(e) of [RFC 0014](../rfcs/0014-account-hub-tenant-admin-and-roster-management.md), grouped into one ADR because they share a home (`/tenants`) and a mechanism (the ADR 0074 user picker) - none of the three needs its own separate design decision beyond what RFC 0014 already pinned.

## Decision

All three actions render on `/tenants`, per tenant/campaign row, gated client-side to match each endpoint's real authorization - the client still never decides access itself, only avoids showing a button that would 403.

### Create a campaign - tenant owner/orga only

A form per tenant (`name`, `game_system`, `slug`, `description`, `secret` checkbox) calling `POST /tenants/{id}/campaigns` (`CampaignCreate`). Shown only when the caller's own `TenantSummaryOut.role` for that tenant is `owner` or `orga`.

### Assign or revoke a campaign's GM - tenant owner/orga only

Per campaign row: the ADR 0074 `mountUserPicker` resolves a person, then `PUT /tenants/{id}/campaigns/{id}/gms/{user_id}` grants; existing GMs are listed via `GET /tenants/{id}/campaigns/{id}/gms` (a plain array of `GmOut`, unpaginated - "inherently small and bounded by construction") with a `DELETE` next to each to revoke. Same `owner`/`orga` gate as campaign creation.

**Real limitation, checked rather than assumed**: `GmOut` is just `{user_id}` - no display name, and there is no `GET /users/{id}` reverse lookup anywhere in this API (only the forward by-email/by-nickname lookups ADR 0055 built). The revoke list can only show a raw `user_id` UUID per existing GM, not a name. Not worked around here - a reverse lookup is `apps/api` surface that doesn't exist, out of scope for a client-only RFC.

### Invite a player into a campaign - tenant owner/orga, or that campaign's own GM

Per campaign row: same picker, `POST /tenants/{id}/campaigns/{id}/players` (`PlayerCreate`, bare `user_id`). Gate is the real two-way one `can_manage_campaign` actually implements: tenant `owner`/`orga`, **or** the caller's own `user_id` appearing in that campaign's GM list (fetched alongside the revoke UI above, so this doesn't cost a second round trip).

## Consequences

- `src/lib/tenants.ts` gains `createCampaign`, `listCampaignGms`, `grantCampaignGm`, `revokeCampaignGm`, `invitePlayer` - all thin wrappers around `CampaignCreate`/`GmOut`/`PlayerCreate`, all checked against the live schema above, not guessed.
- `/tenants` becomes a real write surface for the first time (RFC 0013 shipped it read-only); its existing read-only rendering for a plain participant is unchanged - these three actions simply don't render for them.
- The GM revoke list showing raw `user_id`s rather than names is a real, visible rough edge - worth knowing about before it surprises anyone testing this slice, not a bug to "fix" client-side.
