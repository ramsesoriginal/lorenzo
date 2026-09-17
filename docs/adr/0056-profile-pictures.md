# 0056 - Profile pictures for User, Tenant, and Campaign

Status: accepted

## Context

Users, tenants, and campaigns all want an uploadable profile picture; a user without one falls back to a computed Gravatar (based on their verified email, [ADR 0054](0054-user-identity-email-and-nickname.md)) - tenants and campaigns have no email to fall back to, so they simply have no picture until one is uploaded.

There is no upload endpoint anywhere in this API yet: `payload_picture`/`payload_document` ([ADR 0017](0017-information-and-payloads.md)) are read-only - nothing has ever accepted binary content over HTTP. Routing this through that existing system was considered and rejected: `Tenant` has no `entity_id` at all (it's the RLS boundary, not a member of the entity graph it contains), and `Campaign`'s own `entity_id` would pull a profile picture through `information`'s knowledge/visibility machinery ([ADR 0028](0028-knowledge-and-group-membership.md)/[ADR 0035](0035-campaign-scoped-gm-visibility.md)) - built for GM secrets, the wrong fit for something that should simply always be visible to anyone who can see the tenant/campaign at all.

## Decision

### Storage: one shared table, three link tables

- `profile_picture(id, data: bytea, file_type, created_at, updated_at)` - no `tenant_id`, no RLS. A row here can belong to a `User` (global, no tenant) or a `Tenant`/`Campaign` (tenant-scoped); there is no single RLS predicate that correctly covers both, the same reason `app_user` itself carries no RLS ([ADR 0022](0022-user-tenant-membership.md)). Real tenant isolation lives on the link tables below.
- `user_profile_picture(user_id PK/FK -> app_user, profile_picture_id UNIQUE FK -> profile_picture)` - no `tenant_id`/RLS, matching `app_user`.
- `tenant_profile_picture(tenant_id PK/FK -> tenant, profile_picture_id UNIQUE FK -> profile_picture)` - RLS'd (`tenant_isolation` policy, same shape every RLS'd table in this schema already uses).
- `` campaign_profile_picture(campaign_id PK/FK -> campaign, tenant_id (denormalized, RLS-only - same pattern `player`/`campaign_gm` use), profile_picture_id UNIQUE FK -> profile_picture) `` - RLS'd.
- Every link's `profile_picture_id` is `UNIQUE NOT NULL`: a picture row is never shared between two owners, true 1:1.
- Upload upserts in place (update the existing `profile_picture` row if a link exists, otherwise insert both); delete removes the `profile_picture` row and lets its `ON DELETE CASCADE` take the link with it - the same "delete the base, let the FK cascade the leaf" idiom `delete_campaign` already uses for `Campaign`/`Entity`.
- Deleting a `User` or `Campaign` cascades away the *link* row via its own FK, but would leave `profile_picture` orphaned (nothing points back). `delete_me`/`delete_campaign` each gain one explicit extra step to clean that up. Tenant deletion stays deferred ([ADR 0033](0033-tenant-creation-and-update-api.md)), so no cleanup path is needed there yet.

### Bytes in Postgres, not object storage

Same `BYTEA` choice `payload_picture` already made, for the same reason: no new infrastructure (bucket, credentials, signed-URL flow) for this slice. Revisit if storage volume ever becomes a real problem, not preemptively - identical framing to ADR 0017's own.

### Upload validation

`UploadFile.content_type` checked against an allow-list (`image/png`, `image/jpeg`, `image/webp`, `image/gif`); size capped at a new `Settings.profile_picture_max_bytes` (default 2 MiB). Either violation is a 422 `InvalidProfilePictureError`. No deep image-content sniffing - trusting the client-declared content type is the same level of trust `payload_picture`/`payload_document`'s own `file_type` already gets.

### Serving is public, unauthenticated - the first exception in this API

Every other route requires a Bearer token. A plain `<img src="...">` can't send one, so if picture-serving required auth too, a web frontend couldn't render an avatar directly and would need to fetch bytes via authenticated JS and build a blob URL instead. Upload/delete stay fully authenticated and authorized exactly as normal (self for a user, the same manage-gate `update_tenant`/`update_campaign` already use for a tenant/campaign) - only *reading the bytes back* is open, matching how most public APIs (GitHub, Gravatar itself) already treat avatars as non-secret.

**Named, accepted consequence**: a tenant or campaign's picture-serving route becomes an *existence oracle* - 200 vs 404 reveals whether that id is real, for ids that are membership-gated (404-not-403, indistinguishable from "doesn't exist") everywhere else in this API. Not solved here; a real id is already far from guessable (a random UUID), and nothing else about the tenant/campaign is disclosed through this route beyond bare existence.

Because `routers/campaigns.py`'s router applies `Depends(get_tenant_or_404)` at the router level (which itself requires `CurrentUser`), a public route can't simply be added there without forcing auth regardless of its own signature. The three public `GET .../picture` routes live in a new, dependency-free `routers/pictures.py` instead.

### Gravatar default (user only)

When a user has no uploaded picture: if `email` is set, 302-redirect (not 301 - so a later custom upload isn't cached past) to `https://www.gravatar.com/avatar/{sha256(email.strip().lower())}?d=mp&s=200` - Gravatar accepts either MD5 or SHA256 of the email as its lookup key; SHA256 is used so this doesn't rely on a broken hash even for a non-cryptographic lookup. `d=mp` ("mystery person") means this always resolves to *something*, even for an email that never registered with Gravatar - so the only real 404 is a user with no email at all and no upload. No resizing or proxying of the Gravatar image itself - the redirect target is Gravatar's own problem, not this API's.

## Not in scope

- Any resizing/cropping/thumbnailing - the original uploaded bytes are served as-is.
- Object storage - explicitly deferred, see above.
- A Gravatar-equivalent default for tenants/campaigns - they have no email to derive one from, by design.

## Consequences

- New migration (`profile_picture` + three link tables + RLS on the tenant/campaign-scoped two); `models/profile_picture.py` and three link models.
- `exceptions.py`: `InvalidProfilePictureError`, `ProfilePictureNotFoundError`. `config.py`: `profile_picture_max_bytes`.
- `routers/users.py` (`PUT`/`DELETE /me/picture`, `delete_me` cleanup), `routers/tenants.py` (`PUT`/`DELETE /tenants/{id}/picture`), `routers/campaigns.py` (`PUT`/`DELETE .../campaigns/{id}/picture`, `delete_campaign` cleanup), new `routers/pictures.py` (the three public `GET` routes).
