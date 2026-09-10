# RFC: Tenant creation and update API

Status: proposed — builds on [RFC 0003](0003-tenant-campaign-read-api.md)'s tenant schema and [RFC 0005](0005-item-and-item-instance-crud-api.md)'s write-API conventions; resolves RFC 0003's own deferred slug/collision open question

## Context

[RFC 0003](0003-tenant-campaign-read-api.md) explicitly kept tenant creation out of scope: "A future create-tenant flow will need to populate `slug`/`description`/`name` and provision the initial `OWNER` `Membership` together; not designed here." Every other CRUD RFC (items, campaigns, users/players/characters) has since been written on the assumption that a tenant already exists to create those things *inside* — but nothing actually creates the first one. Checked against [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1): Oscar's tenant, "The Shattered Realms," has to come from somewhere before any of the rest of the scenario can happen at all. This is that RFC.

Tenant creation is structurally unlike every other `POST` in this API: every other one is gated by some pre-existing privilege *inside* a tenant (`get_tenant_context`, `can_manage_campaign`, self-or-managed) — but nothing tenant-scoped can exist before the tenant itself does, so there's no privilege to check yet. This is deliberate, not a gap to close: any authenticated user creating their own new world is the natural onboarding path for a tool aimed at "a GM juggling one campaign... a fanfic team juggling a five-author shared multiverse" ([docs/domain/README.md](../domain/README.md)) — nobody should need another human's permission to start their own.

## Decision

### `POST /tenants` — any authenticated user, no other gate

`TenantCreate{name, slug: str | None = None, description: str | None = None}`. `name` required — an "Unnamed Tenant" default exists at the column level only for pre-existing test fixtures ([ADR 0022](../adr/0022-user-tenant-membership.md)), not because a fresh create endpoint should ever produce one. `description` optional, defaults to `''` (the column's own existing server default).

One transaction creates the `Tenant` row and a `Membership(tenant_id=new, user_id=CurrentUser.id, role=OWNER)` — the caller becomes the tenant's owner atomically, the same "create the whole coherent unit in one commit" precedent every other CRUD RFC here already follows. `201 TenantOut`, `Location` pointing at `GET /tenants/{tenant_id}`.

**No cap on how many tenants one user can create.** Nothing asks for this, and rate-limiting infrastructure is already explicitly deferred project-wide until a concrete need exists ([ADR 0008](../adr/0008-deferred-taskiq-and-fastapi-limiter.md)) — revisit together if abuse ever becomes real, not preemptively here.

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

## Open questions

**Should slug validation reject anything beyond basic format checking** (a reserved-word blocklist, profanity filtering, length limits)? Not designed — real product concerns for a public-facing `/t/{slug}/...` URL scheme, but nothing this RFC needs to resolve to be internally consistent.

## Consequences

- **Needs a migration**: none beyond [RFC 0010](0010-created-by-updated-by-attribution.md)'s already-planned `tenant.created_by`/`updated_by` — no new columns of this RFC's own, since `slug`/`name`/`description` all already exist ([RFC 0003](0003-tenant-campaign-read-api.md)).
- `SlugConflictError` (`ConflictProblem`, 409) joins `exceptions.py`'s roster.
- This is the first `POST` in the entire API with no authorization check beyond "authenticated" — worth a clear comment at the route itself, not just here, so a future reader doesn't assume it was an oversight.
- `tests/conftest.py`'s `make_tenant` helper (currently a direct DB insert, bypassing the API entirely) can now optionally be implemented as a real `POST /tenants` call for tests that specifically want to exercise the endpoint — not a required change, existing direct-insert tests remain valid for everything that isn't testing tenant creation itself.
- Once this lands, [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1)'s scenario has no remaining unaddressed gaps in tenant/campaign/player/character/item structure — [RFC 0011](0011-information-payload-knowledge-crud-api.md) (information/payload/knowledge) and completing [RFC 0008](0008-effective-stat-resolution.md) (stat resolution + writing) are what's left before the scenario's own knowledge/visibility and stat-inheritance claims can actually be authored and proven, not this RFC's territory.
