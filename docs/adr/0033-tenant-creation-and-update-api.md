# 0033 - Tenant creation and update API

Status: accepted

## Context

Every CRUD RFC so far ([RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md), and every RFC after it) has assumed a tenant already exists to create things *inside* - but nothing actually creates the first one. [RFC 0003](../rfcs/0003-tenant-campaign-read-api.md) explicitly deferred this: "A future create-tenant flow will need to populate `slug`/`description`/`name` and provision the initial `OWNER` `Membership` together; not designed here." Checked against [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1): Oscar's tenant, "The Shattered Realms," has to come from somewhere before the rest of that scenario can happen at all. This ADR accepts [RFC 0012](../rfcs/0012-tenant-creation-and-update-api.md), close to verbatim - see it for the full reasoning trail, including the revision from its own first "any authenticated user" draft.

## Decision

### `POST /tenants` gated by an Authgear role, not by anything in this app's own tables

Tenant creation is structurally unlike every other `POST` here: every other one is gated by some pre-existing privilege *inside* a tenant, but nothing tenant-scoped can exist before the tenant itself does. The gate is instead platform-level and tenant-independent: a new `Settings.tenant_creator_role_key: str = "tenant-creator"`, read off Authgear's own per-user role claim (`https://authgear.com/claims/user/roles` in the verified JWT) via a new `require_tenant_creator_role(user: CurrentUser) -> None` dependency. No new `app_user` column, no sync mechanism - Authgear stays the single source of truth, the same boundary [ADR 0009](0009-identity-provider-authgear.md) already draws in the other direction. This is the first concrete use of the "platform-admin flag" [ADR 0010](0010-user-tenant-membership-model.md) anticipated without designing, and sets the mechanism (an Authgear role, not a new app-side flag) for any future need of the same shape.

**Flagged for empirical verification, not fully certain from Authgear's docs alone** (the JWT claims reference page doesn't list `roles` among its documented defaults): confirm against a real token from this project's Authgear Cloud project before relying on this in production, the same empirical-check discipline [ADR 0023](0023-authgear-token-verification.md) already applied to the `aud` claim.

`403 TenantCreationForbiddenError` (`ForbiddenProblem`), not `404` - there's no tenant-scoped existence to hide behind here, the caller just lacks a specific, nameable platform privilege, the same 403-not-404 reasoning [RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md) established for "can read, can't write."

**Implementation nuance affecting the existing test fixture**: `tests/conftest.py`'s `client` fixture overrides `get_current_user` directly and never invokes real token verification, so a dependency reading `TokenClaimsDep`/`verify_token`'s own output separately would silently need a *real* signed token under that fixture. Fixed by having `get_current_user` itself attach the roles claim as a plain, non-persisted attribute on the `User` it already returns - `user.authgear_roles: frozenset[str]`, not a mapped column, never written back. `require_tenant_creator_role` reads that attribute, so the `client` fixture's `_fake_current_user` override can set it directly like any other test double. `models.User` needs `__allow_unmapped__ = True` for this bare (non-`Mapped[]`) annotation to coexist with its mapped columns - confirmed empirically after SQLAlchemy's declarative scanning rejected the annotation outright without it (`ClassVar[]`, its other suggested fix, would make mypy reject the per-request instance assignment this needs).

`TenantCreate{name, slug: str | None = None, description: str | None = None}`. `name` required. One transaction creates the `Tenant` row and a `Membership(role=OWNER)` for the caller - the same "create the whole coherent unit in one commit" precedent every other CRUD RFC here follows. `201 TenantOut`, `Location` pointing at `GET /tenants/{tenant_id}`. No cap on how many tenants one role-holding user can create - rate-limiting stays deferred project-wide ([ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md)).

### Slug: auto-derived by default, resolving RFC 0003's own open question

Omitted `slug` is generated from `name` (lowercased, non-alphanumeric runs collapsed to a single `-`) and auto-suffixed on collision (`my-world`, `my-world-2`, ...) - creating a tenant never fails just because someone already picked a similar name. An explicit `slug` is validated for basic format (a pydantic `Field(pattern=...)` on `TenantCreate`/`TenantUpdate` - lowercase alphanumeric segments joined by single hyphens; deeper checks like a reserved-word blocklist are explicitly out of scope, per RFC 0012's own open questions) and checked for uniqueness with *no* auto-suffix - `409 SlugConflictError` if taken, since silently rewriting an explicit choice would be the wrong failure mode. **Renaming later never regenerates the slug** - `slug`/`name` are independent once a tenant exists, resolving the other half of RFC 0003's deferred question.

### `PATCH /tenants/{tenant_id}` stays gated by `get_tenant_context`

Unchanged, not narrowed to `OWNER`-only - renaming/re-describing the world is ordinary tenant-wide administrative access, exactly what `ORGA` already means ([ADR 0010](0010-user-tenant-membership-model.md)). `TenantUpdate{name, slug, description: str | None = None}`, all optional. Changing `slug` here goes through the same explicit-collision-check path `POST` uses (no auto-suffix).

### Attribution: `tenant` moves from excluded to covered ([ADR 0029](0029-attribution-created-by-updated-by.md))

`tenant` gains the full `created_by`/`updated_by` pair, same shape as `campaign`/`membership`/`player`: `POST` sets both to `CurrentUser.id`, `PATCH` updates `updated_by` (only when a write route field actually changed - a no-op `PATCH` with an empty body doesn't stamp a new editor). `TenantOut` gains both fields.

**A real, pre-existing gap found while implementing, not part of RFC 0012's own text**: `tenant` never actually had `created_at`/`updated_at` at all - its original minimal bootstrap ([ADR 0013](0013-tenant-table-bootstrap.md)) predates `created_at`/`updated_at` becoming a uniform convention ([ADR 0018](0018-sqlalchemy-modeling-conventions.md)), and nothing before this needed either column enough to retrofit them. Both are needed now regardless of the attribution pair: `PATCH`'s `If-Match` support ([ADR 0032](0032-item-and-item-instance-crud-api.md)'s `etag.py`) is derived from `updated_at`. All four columns (`created_at`, `updated_at`, `created_by`, `updated_by`) land together in one migration, closing this gap rather than deferring it further.

## Not in scope

**Tenant deletion.** [ADR 0018](0018-sqlalchemy-modeling-conventions.md) already named this moment directly: a tenant cascade dwarfs every other delete guard in this schema and deserves its own careful pass, not a rushed footnote here. A tenant, once created, is permanent through this API for now.

**Multiple owners at creation, or transferring ownership** - `POST /tenants` always creates exactly one `Membership(role=OWNER)`, the caller's own; both are already covered by a plain `Membership` `PATCH`/`POST` once that CRUD lands ([RFC 0007](../rfcs/0007-user-player-character-crud-api.md)).

**Granting/revoking the `tenant-creator` role itself** - entirely Authgear's own concern; no in-app endpoint exists or is proposed.

**Deeper slug validation** (reserved-word blocklist, profanity filtering, length limits) and **exposing the `tenant-creator` role on `GET /me`** - both named as real, explicitly deferred follow-ups, not resolved here.

## Consequences

- New migration: `tenant` gains `created_at`/`updated_at`/`created_by`/`updated_by` (nullable pair, `ON DELETE SET NULL`, indexed - identical shape to `entity`'s own pair).
- `SlugConflictError`/`TenantCreationForbiddenError` (`ConflictProblem`/`ForbiddenProblem`) join `exceptions.py`'s roster.
- `Settings.tenant_creator_role_key` joins the Authgear-adjacent config trio (`authgear_issuer`/`authgear_jwks_url`/`authgear_audience`).
- `models.User` carries a non-mapped `authgear_roles: frozenset[str]` attribute and `__allow_unmapped__ = True`, attached per-request by `get_current_user` (or a test double) - the established pattern for any future claim that needs to ride along on the same `User` object without a real signed token in every test that touches it.
- **Bootstrapping is now a manual, human step, not a cold API call.** A project maintainer has to grant the `tenant-creator` role to an account via the Authgear Portal before `POST /tenants` can be called at all - worth a line in [docs/operations/deployment-setup.md](../operations/deployment-setup.md) as a follow-up, matching how that doc already covers other one-time, human-confirmed setup steps.
- `tests/conftest.py`'s `client` fixture now sets `user.authgear_roles` to include `"tenant-creator"` by default (so existing tests aren't newly blocked), with a separate `client_without_tenant_creator_role` fixture for the 403 negative case.
- Sets the precedent for any future platform-level permission: an Authgear role, not a new `app_user` column, is now the established mechanism.

## Addendum: role keys can't contain hyphens, only underscores

The empirical verification this ADR's Decision section flagged as outstanding ("confirm against a real token... before relying on this in production") turned up a real mismatch, not just confirmation: Authgear's Portal accepts `-` in a role's display *name*, but its *key* - the identifier that actually lands in the `https://authgear.com/claims/user/roles` claim `require_tenant_creator_role` reads - silently rewrites any `-` to `_` on save. A role named "tenant-creator" in the Portal ends up with the key `tenant_creator`, not `tenant-creator`.

`Settings.tenant_creator_role_key`'s default was still `"tenant-creator"` (a key no real Authgear project can ever actually produce), which meant the platform-level gate would reject *every* real production caller by default, role granted or not - the mismatch was silent because nothing before this had a live Authgear project to check it against. Fixed by changing the default to `"tenant_creator"` and updating every test fixture that simulates the real claim to match (`tests/conftest.py`, `tests/test_api_tenants.py`, `tests/test_milestone_scenario.py`). The setting itself is still fully overridable via env var, same as before - this only changes what a deployer gets without setting one.
