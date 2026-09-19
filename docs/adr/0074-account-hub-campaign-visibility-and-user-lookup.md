# 0074 - account-hub: campaign visibility on /characters, and shared user lookup

Status: accepted

## Context

First two sub-slices of [RFC 0014](../rfcs/0014-account-hub-tenant-admin-and-roster-management.md), foundational to the rest: showing every campaign in a tenant (not just ones already played), and a single, reusable "resolve a person to a `user_id`" mechanism that campaign-GM-assignment and player-invite (both later sub-slices) will each need.

## Decision

### `/characters`: list every campaign per tenant, not just `MeOut.players[]`

Reuses the exact aggregation `/tenants` already does (`listMyTenants()` + `listTenantCampaigns()` per tenant) instead of iterating `me.players` alone. For each campaign: if the caller already has a `PlayerContextOut` for it, render exactly what RFC 0013 already built (existing characters, create-new form). If not, render a "you don't play here yet" row with no action — per RFC 0014, no self-service join exists, so this is context, not a dead button.

### Shared user lookup: `src/lib/users.ts`, exact-match only

```ts
export async function findUserByEmail(email: string): Promise<UserRefOut | null>
export async function findUserByNickname(nickname: string): Promise<UserRefOut | null>
```

Wraps `GET /users/by-email/{email}` / `GET /users/by-nickname/{nickname}` (`UserRefOut`: `id`/`nickname`/`display_name`, ADR 0055). Both are exact-match, 404-on-miss per that ADR's own design (no partial search exists) - callers get `null` back for a 404 specifically (not a thrown `ApiError`), so a "not found, try again" UI state doesn't need to catch-and-inspect an error object for every lookup.

A single shared `<UserPicker>`-shaped widget (a text input, a type toggle for email-vs-nickname, a "look up" button, and a resolved `{id, display_name ?? nickname}` result or a "not found" message) is built once as its own small vanilla-TS module (`src/lib/userPicker.ts`, exposing a `mount(container, onResolved)` function rather than a component-framework component - still no framework, ADR 0071) and reused unmodified by both the GM-assignment and player-invite UIs in later sub-slices, rather than copy-pasted per page.

## Consequences

- `PlayerCreate`/`UserRefOut`/`CampaignCreate` types land in `types.ts` now even though only `UserRefOut` is consumed by this slice - the other two are needed by the very next sub-slice and were already fully checked against the live schema while researching RFC 0014, so there's no guessing to redo later.
- No new API surface - both lookup routes and the campaign-list route already exist and are already used elsewhere in this app.
