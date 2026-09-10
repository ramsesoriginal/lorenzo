# RFC: Tenant creation and update API

Status: proposed — builds on [RFC 0003](0003-tenant-campaign-read-api.md)'s tenant schema and [RFC 0005](0005-item-and-item-instance-crud-api.md)'s write-API conventions; resolves RFC 0003's own deferred slug/collision open question; gates creation on an Authgear role, revised from this RFC's own first "any authenticated user" draft

## Context

[RFC 0003](0003-tenant-campaign-read-api.md) explicitly kept tenant creation out of scope: "A future create-tenant flow will need to populate `slug`/`description`/`name` and provision the initial `OWNER` `Membership` together; not designed here." Every other CRUD RFC (items, campaigns, users/players/characters) has since been written on the assumption that a tenant already exists to create those things *inside* — but nothing actually creates the first one. Checked against [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1): Oscar's tenant, "The Shattered Realms," has to come from somewhere before any of the rest of the scenario can happen at all. This is that RFC.

Tenant creation is structurally unlike every other `POST` in this API: every other one is gated by some pre-existing privilege *inside* a tenant (`get_tenant_context`, `can_manage_campaign`, self-or-managed) — but nothing tenant-scoped can exist before the tenant itself does, so there's no *tenant-scoped* privilege to check yet.

**Revised**: this RFC's first draft concluded from that structural fact that creation should be open to any authenticated user — that's the wrong conclusion, not the only one available. What's actually wanted is a *platform-level* gate, independent of any tenant (since none exists yet to scope one to) — and [ADR 0010](../adr/0010-user-tenant-membership-model.md) already anticipated needing exactly this shape of permission without designing it: "A platform-admin flag on `User`, separate from tenant-scoped roles, is anticipated for future cross-tenant moderation/support access — not needed yet, deliberately not designed further now." This RFC is the first concrete use of that anticipated need — and picks Authgear's own role system as the mechanism, not a new `app_user` column, for the reasons below.

## Decision

### `POST /tenants` — gated by an Authgear role, not by anything in this app's own tables

Confirmed against Authgear's own documentation (not assumed — this project's own history has a near-identical gotcha with the `aud` claim, [ADR 0023](../adr/0023-authgear-token-verification.md), so the same care applies here): Authgear supports assigning **roles** to a user (Portal: User Management → a user → Roles tab → Add Roles; or the Admin API's GraphQL mutations) and includes them in both the `UserInfo` response and the JWT access token itself, as an array under `https://authgear.com/claims/user/roles` — [Authgear's own roles/groups guide](https://docs.authgear.com/admin-and-operations/user-management/manage-users-roles-and-groups) states this directly.

**Flagged for empirical verification during implementation, not fully certain from docs alone**: the dedicated JWT-access-token claims reference page doesn't list `roles` among its documented default claims, only three unrelated ones (`can_reauthenticate`/`is_anonymous`/`is_verified`) — plausibly because `roles` only appears once a user actually has one assigned, plausibly a documentation gap between two doc sections. Either way, confirm against a real token from this project's own Authgear Cloud project before relying on it, the same way [ADR 0023](../adr/0023-authgear-token-verification.md) confirmed the `aud` claim's actual behavior empirically rather than trusting the docs alone.

No new `app_user` column, no sync mechanism — Authgear stays the single source of truth for this, matching [ADR 0009](../adr/0009-identity-provider-authgear.md)'s own boundary ("Authgear never needs to know this app's tenant/membership model exists") in the other direction: this app doesn't need its own copy of what's fundamentally an identity-provider-side fact, either. The role's name is a new `Settings.tenant_creator_role_key: str = "tenant-creator"` — Authgear-Portal-configured, not fixed by this codebase beyond that one setting, mirroring `authgear_issuer`/`authgear_jwks_url`/`authgear_audience`'s existing pattern for IdP-adjacent config.

**Implementation nuance, named precisely because it affects the existing test fixture**: `tests/conftest.py`'s `client` fixture overrides `get_current_user` directly and never invokes real token verification — a new dependency that separately read `TokenClaimsDep`/`verify_token`'s own output would silently require a *real* signed token under that fixture, breaking every existing test that uses it. Fix: `get_current_user` itself attaches the roles claim as a plain, non-persisted attribute on the `User` it already returns (`user.authgear_roles: frozenset[str]` — not a mapped column, never written back, purely Authgear's own data passed through for the duration of the request). A new `require_tenant_creator_role(user: CurrentUser) -> None` dependency then reads `user.authgear_roles` — which the test fixture's existing `_fake_current_user` override can set directly like any other test double, no second override mechanism needed. Defaults to an empty `frozenset` if the claim is absent entirely — no role granted, no access, matching the closed-by-default behavior this revision exists for.

`403 TenantCreationForbiddenError` (`ForbiddenProblem`) if the role is missing — not `404`: there's no existence to hide here (`POST /tenants` itself is the one endpoint with nothing tenant-scoped to leak), the caller just lacks a specific, nameable platform privilege — the same 403-not-404 reasoning [RFC 0005](0005-item-and-item-instance-crud-api.md) already established for "can read, can't write."

`TenantCreate{name, slug: str | None = None, description: str | None = None}`. `name` required — an "Unnamed Tenant" default exists at the column level only for pre-existing test fixtures ([ADR 0022](../adr/0022-user-tenant-membership.md)), not because a fresh create endpoint should ever produce one. `description` optional, defaults to `''` (the column's own existing server default).

One transaction creates the `Tenant` row and a `Membership(tenant_id=new, user_id=CurrentUser.id, role=OWNER)` — the caller becomes the tenant's owner atomically, the same "create the whole coherent unit in one commit" precedent every other CRUD RFC here already follows. `201 TenantOut`, `Location` pointing at `GET /tenants/{tenant_id}`.

**No cap on how many tenants one role-holding user can create.** Nothing asks for one, and rate-limiting infrastructure is already explicitly deferred project-wide until a concrete need exists ([ADR 0008](../adr/0008-deferred-taskiq-and-fastapi-limiter.md)) — revisit together if abuse ever becomes real, not preemptively here.

### Slug: auto-derived by default, resolving RFC 0003's own open question

If `slug` is omitted, it's generated from `name` (lowercased, non-alphanumeric runs collapsed to a single `-`) and **auto-suffixed on collision** (`my-world`, `my-world-2`, `my-world-3`, ...) — creating a tenant never fails just because someone else already picked a similar name. If `slug` is given explicitly, it's validated (format) and checked for uniqueness *without* auto-suffixing — `409 SlugConflictError` if taken, since silently rewriting something the caller explicitly asked for would be the wrong failure mode for an explicit choice. This asymmetry is deliberate: auto-generated values get a forgiving fallback, explicit ones get a hard error, matching ordinary REST expectations either way.

**Renaming later does not regenerate the slug.** `slug` and `name` are independent once a tenant exists — resolving the other half of RFC 0003's open question ("does renaming change the slug, breaking old links, or leave it pinned"): pinned, always, unless the caller explicitly `PATCH`es `slug` itself. A link nobody asked to break shouldn't break as a side effect of an unrelated rename.

### `PATCH /tenants/{tenant_id}` — any tenant-wide member

`TenantUpdate{name, slug, description: str | None = None}`, all optional. Gated by the existing `get_tenant_context` — unchanged, no narrower `OWNER`-only restriction the way [RFC 0007](0007-user-player-character-crud-api.md) narrows membership-role changes: renaming or re-describing the world is squarely "tenant-wide administrative access," exactly what `ORGA` already means ([ADR 0010](../adr/0010-user-tenant-membership-model.md)), not something to reserve for `OWNER` alone. Changing `slug` here goes through the same explicit-collision-check path `POST` uses — no auto-suffix once the tenant already exists and a specific new slug is being asked for by name.

### Attribution ([RFC 0010](0010-created-by-updated-by-attribution.md)) — `tenant` moves from excluded to covered

RFC 0010 excluded `tenant` from `created_by`/`updated_by` for exactly one reason: "nothing writes one yet." That's no longer true. `tenant` gains the full pair, same shape as `campaign`/`membership`/`player`: `POST /tenants` sets both to `CurrentUser.id`; `PATCH` updates `updated_by`. `TenantOut` gains `created_by`/`updated_by` fields to match.

## Not in scope

**Tenant deletion.** [ADR 0018](../adr/0018-sqlalchemy-modeling-conventions.md) named this exact moment directly: "deleting a `Tenant` now cascades through every table that (transitively) references it... acceptable now because no tenant-deletion API exists yet... revisit before any real deletion endpoint ships if a softer/guarded delete is wanted instead." That revisit is real work — a tenant cascade dwarfs campaign deletion's own guard ([RFC 0006](0006-campaign-crud-api.md)) by every table in the schema, not just a handful — and deserves its own careful pass, not a rushed footnote here. A tenant, once created, is permanent through this API for now.

**Transferring ownership without going through `Membership`** — already fully covered by [RFC 0007](0007-user-player-character-crud-api.md)'s membership-role `PATCH` (making someone else `OWNER` is already just changing a role value, [ADR 0010](../adr/0010-user-tenant-membership-model.md)'s own point); nothing new needed here.

**Multiple owners at creation time** (inviting co-owners as part of the same `POST`) — `POST /tenants` always creates exactly one `Membership(role=OWNER)`, the caller's own; adding others is a separate `POST /memberships` call ([RFC 0007](0007-user-player-character-crud-api.md)), not folded into tenant creation itself.

**Granting/revoking the `tenant-creator` role itself** — entirely Authgear's own concern (its Portal or Admin API), not something `apps/api` exposes, manages, or has any awareness of beyond reading the claim it's handed. No in-app "make this user a tenant creator" endpoint exists or is proposed.

## Open questions

**Should slug validation reject anything beyond basic format checking** (a reserved-word blocklist, profanity filtering, length limits)? Not designed — real product concerns for a public-facing `/t/{slug}/...` URL scheme, but nothing this RFC needs to resolve to be internally consistent.

**Should `GET /me` ([RFC 0004](0004-user-membership-player-character-gm-read-api.md)) expose whether the caller holds the `tenant-creator` role**, so a client can conditionally show or hide a "create a new world" button instead of discovering it by attempting `POST /tenants` and handling `403`? Not designed here — a small, natural follow-up to that RFC, not this one.

## Consequences

- **Needs a migration**: none beyond [RFC 0010](0010-created-by-updated-by-attribution.md)'s already-planned `tenant.created_by`/`updated_by` — no new columns of this RFC's own, since `slug`/`name`/`description` all already exist ([RFC 0003](0003-tenant-campaign-read-api.md)), and the role check needs no `app_user` column at all.
- `SlugConflictError`/`TenantCreationForbiddenError` (`ConflictProblem`/`ForbiddenProblem`) join `exceptions.py`'s roster.
- **Bootstrapping is now a manual, human step, not a cold API call.** Before anyone can call `POST /tenants` at all, a project maintainer has to sign into the Authgear Portal and grant the `tenant-creator` role to whichever account(s) should have it — there's no self-granting or chicken-and-egg path, by design. Worth a line in [docs/operations/deployment-setup.md](../operations/deployment-setup.md) once this is built, matching how that doc already covers other one-time, human-confirmed setup steps ([ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)'s role rotation).
- **Sets a precedent worth reusing, not just a one-off fix**: the next time this codebase needs a cross-tenant/platform-level permission ([ADR 0010](../adr/0010-user-tenant-membership-model.md)'s own anticipated "platform-admin" case, or anything like it), an Authgear role is the established mechanism now, not a new `app_user` column reinvented per permission.
- `tests/conftest.py`'s `client` fixture needs updating alongside this — `_fake_current_user` has to set `user.authgear_roles` (defaulting to include `tenant-creator`, so existing tests unrelated to this RFC aren't newly blocked) and a way for the specific negative-case test to override it to an empty set.
- `tests/conftest.py`'s `make_tenant` helper (currently a direct DB insert, bypassing the API entirely) can now optionally be implemented as a real `POST /tenants` call for tests that specifically want to exercise the endpoint — not a required change, existing direct-insert tests remain valid for everything that isn't testing tenant creation itself.
- Once this lands, [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1)'s scenario has no remaining unaddressed gaps in tenant/campaign/player/character/item structure — [RFC 0011](0011-information-payload-knowledge-crud-api.md) (information/payload/knowledge) and completing [RFC 0008](0008-effective-stat-resolution.md) (stat resolution + writing) are what's left before the scenario's own knowledge/visibility and stat-inheritance claims can actually be authored and proven, not this RFC's territory.
