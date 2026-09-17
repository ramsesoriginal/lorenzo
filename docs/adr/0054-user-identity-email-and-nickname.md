# 0054 - User identity: Authgear-synced email + local nickname

Status: accepted

## Context

`User` ([ADR 0009](0009-identity-provider-authgear.md)/[ADR 0010](0010-user-tenant-membership-model.md)) deliberately holds nothing but a link back to Authgear's subject id - "no email, name, password... lives here, Authgear is the source of truth." That was the right call while nothing in this API needed to address a user by anything but their own opaque `user_id` (which only they can already see, via `/me`).

It stops being enough once a tenant OWNER/GM needs to invite someone they don't already have a `user_id` for, or a roster needs to show *who* a `user_id` actually is. Revisiting the decision on purpose: a user needs two more identifying attributes, each unique -

- **email** - already exists, verified, and is unique per Authgear identity; duplicating it locally is a cache of Authgear's own fact, not a second source of truth for it.
- **nickname** - has no Authgear equivalent to defer to (Authgear's own display name isn't guaranteed unique, and isn't exposed as a token claim this app requests). It's genuinely local, user-owned data.

## Decision

- `app_user` gains two nullable columns, `email: str | None` and `nickname: str | None`, each with its own partial unique index (`WHERE ... IS NOT NULL`) - global, not tenant-scoped (`User` isn't tenant-scoped either), same "optional + partial unique" shape already used for `tenant.slug` and `item_instance.slug` ([ADR 0043](0043-item-instance-slug.md)).
- `email` is synced **read-only** from the verified ID token, at the same JIT-provisioning moment `authgear_subject_id` is upserted (`dependencies.get_current_user`, [ADR 0023](0023-authgear-token-verification.md)) - only when the token's `email` claim is present **and** its `email_verified` claim is `True`. An unverified or absent email claim leaves `User.email` untouched; this app never treats an unverified email as a fact. A verified email that collides with a different existing user's email (a genuinely rare edge - e.g. Authgear allowing an email to move between identities) doesn't fail the login: the sync is attempted as its own guarded step, and a collision is logged and skipped rather than raised, so a stale/reused claim can never lock someone out of authenticating.
- `nickname` has no sync path at all - it's set directly by the user via a new `PATCH /me`, body `{nickname: str | None}`. A collision returns 409 (`NicknameConflictError`, same `ConflictProblem` shape as the existing `SlugConflictError`). No `If-Match` requirement: a single self-editable field on your own record isn't a meaningful concurrent-write risk the way the multi-writer resources [ADR 0042](0042-concurrency-token-on-reads.md) covers are.
- `MeOut` exposes both `email` and `nickname`. Tenant-roster-facing schemas (`MembershipRosterEntryOut`, `PlayerRosterEntryOut`, `GmRosterEntryOut`) gain `nickname` only, so a tenant's roster is readable without a lookup per row - **not** `email`, which stays visible only on the caller's own `/me`. A shared roster is not the place to leak other members' email addresses to each other.

## Not in scope

- Changing what Authgear itself stores or exposes as claims beyond what's already requested.
- Any endpoint to change a user's *email* - it only ever moves when Authgear's own verified claim changes, matching Authgear's role as its source of truth.
- Enforcing any particular nickname format (casing, length, charset) beyond non-empty and unique - left permissive until a real need narrows it.

## Consequences

- New Alembic migration adding the two columns and their partial unique indexes.
- `models/user.py`, `dependencies.py` (`get_current_user`), `exceptions.py` (`NicknameConflictError`), `schemas/users.py` (`MeOut`), `schemas/tenants.py` (three roster-entry schemas), `routers/users.py` (new `PATCH /me`), `routers/tenants.py` (`list_tenant_roster` now joins `User` for nickname).
- A user can be identified by nickname or email going forward, which [ADR 0055](0055-user-lookup-by-email-or-nickname.md) turns into an actual invite-time lookup.
