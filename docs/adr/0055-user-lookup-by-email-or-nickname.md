# 0055 - Exact-match user lookup by email or nickname

Status: accepted

## Context

[ADR 0054](0054-user-identity-email-and-nickname.md) gives every user a unique email and (optionally) a unique nickname, so an OWNER/GM can now plausibly know *who* they want to invite. But every invite-shaped endpoint that already exists - `POST /tenants/{tenant_id}/memberships`, player creation - takes a raw `user_id` UUID, which nobody but that user can already see (it's not printed anywhere, and shouldn't be guessable). Something has to resolve "the person whose email is X" to that UUID before those endpoints are reachable at all.

## Decision

Two new routes, `GET /users/by-email/{email}` and `GET /users/by-nickname/{nickname}`, each returning a minimal `UserRefOut {id, nickname}` on an exact match, 404 (`UserNotFoundError`) otherwise. Deliberately narrow:

- **Exact match only** - no partial/prefix/fuzzy search, no pagination. A caller who doesn't already know the precise value gets nothing, the same shape Slack/GitHub's own "invite by exact email" flows use to avoid exposing a directory-scraping surface.
- **Open to any authenticated user**, not gated by tenant membership or an OWNER/ORGA role - resolving an identifier to a `user_id` isn't itself a tenant-scoped privilege (nothing tenant-specific is disclosed - not even whether the target belongs to any tenant), so it isn't nested under `/tenants/{tenant_id}/...`, the same reasoning that already keeps `/me` unnested.
- `UserRefOut` never echoes `email` back (the caller already supplied it to look it up) - only `id` and `nickname`, kept minimal on purpose.
- The existing invite endpoints are **unchanged** - this only adds the resolution step a client performs before calling them with the real `user_id`.

## Not in scope

- Any form of search/browse (`?q=`, prefix match, "did you mean") - a deliberately different, heavier feature this ADR doesn't build.
- Folding email/nickname directly into `POST /tenants/{tenant_id}/memberships`'s own request body as an alternative to `user_id` - keeping resolution as its own step means every future invite-shaped endpoint (campaign player creation, group invites, ...) gets the same lookup for free rather than each reimplementing its own email/nickname branch.

## Consequences

- `routers/users.py` gains the two routes; `schemas/users.py` gains `UserRefOut`; `exceptions.py` gains `UserNotFoundError`.
- A client can now go from "the email/nickname I was told" to a real invite, in two calls, without either party needing to already know or share a `user_id`.
