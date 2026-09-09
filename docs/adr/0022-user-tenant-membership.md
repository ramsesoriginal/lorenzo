# 0022 - User, full Tenant, and Membership

Status: accepted

## Context

[ADR 0010](0010-user-tenant-membership-model.md) already decided the shape conceptually: User as a global identity linked to Authgear's subject id ([ADR 0009](0009-identity-provider-authgear.md)), Tenant as the RLS-boundary "world," Membership joining the two with a tenant-wide administrative role. [RFC 0002](../rfcs/0002-campaign-player-character-model.md) later narrowed Membership's role vocabulary to tenant-wide access only (`owner`, `orga`) now that campaign-scoped GM/player access is its own, separate concept. This ADR is where that gets built - concrete columns, constraints, and migration.

## Decision

### `app_user`, not `user`

`user` is a reserved word in Postgres - confirmed empirically, not assumed: `CREATE TABLE user (...)` fails outright with a syntax error, and even when force-created via `CREATE TABLE "user" (...)`, an unquoted `SELECT * FROM user` doesn't error - it silently resolves to the current session's role name instead (Postgres's `user` pseudo-value), returning a completely wrong result rather than failing loudly. Given this project's tests lean heavily on raw `text()` SQL (fixture setup, RLS-proof assertions, tuple-driven table lists like `test_cascades.py`'s `_CASCADE_TABLES`), requiring perpetual careful quoting everywhere forever is a real, avoidable footgun - the table is `app_user`. The Python class stays `User` (no SQL-identifier conflict at that layer); this is one deliberate exception to the usual class-name-matches-tablename convention, not a precedent for renaming anything else.

`app_user` has no `tenant_id` - the first table in this schema without one, deliberately: a User is a global identity, not scoped to any single tenant (ADR 0010). Holds only `id` and `authgear_subject_id` (globally `UNIQUE`, not per-tenant) plus timestamps - no email, name, password, or OAuth token, all of which stay in Authgear (ADR 0009's own stated boundary).

### `tenant` gains `name`

`ALTER TABLE tenant ADD COLUMN name TEXT NOT NULL SERVER DEFAULT 'Unnamed Tenant'` - safe to add `NOT NULL` with no *backfill* since no real tenant data exists yet (pre-release, confirmed against the current dev/CI/production state), but the column keeps a real server-side default rather than requiring every caller to supply one: `Tenant()` bare is the single most common fixture-constructor call across the existing test suite (46 call sites, 15 files), none of which are actually testing the tenant's name - retrofitting all of them for a column they don't care about would be pure mechanical noise. A caller that does care (none yet - no create-tenant REST flow exists in this slice) still passes it explicitly. ADR 0013's bootstrap comment anticipated this column landing eventually.

### `membership`: composite PK, role is `owner` or `orga`

```python
class MembershipRole(enum.Enum):
    OWNER = "owner"
    ORGA = "orga"
```

`membership(tenant_id, user_id, role, created_at, updated_at)` - composite primary key `(tenant_id, user_id)`, both hand-rolled `mapped_column(ForeignKey(...), primary_key=True, ondelete="CASCADE")` rather than through the shared `TenantFk`/`UuidPk` `Annotated` aliases, matching how every other composite-PK join table in this schema (`entity_stat_group`, `entity_prototype`, ...) already hand-rolls its PK-participating FK columns instead of bending the shared aliases to fit. `tenant_id` leads the composite PK (not `user_id` first) deliberately: RLS's `tenant_id = current_setting(...)` filter runs on *every* query against this table, and a composite index's leading column is what actually serves an equality filter efficiently - leading with `tenant_id` gets that for free from the PK's own index, rather than needing a second, separate single-column index the way tables where `tenant_id` sits outside the PK entirely (`entity_stat_group`) already do via `TenantFk`'s `index=True`. Ownership is a role value, not a separate `tenant.owner_id` column - the same reasoning ADR 0010 already gave for rejecting that redundancy holds unchanged.

Unlike `entity_stat_group` (where `tenant_id` sits *outside* the PK, redundant with what `entity_id` already implies transitively), `membership`'s `tenant_id` is a genuine, irreducible part of its identity - `user_id` alone implies no tenant at all (a User is global), so the (user, tenant) pair itself is what's being modeled, not a denormalized shortcut around a join.

### What this table does *not* decide

Membership only answers "does this user have tenant-wide administrative access, and at what level" - it is deliberately not where campaign-scoped access lives. RFC 0002's actual access rule ("a user can access a campaign if they hold a `player` row in it, a `campaign_gm` row in it, or are tenant-`orga` without an opt-out for it") needs `campaign`/`player`/`campaign_gm`/`orga_campaign_opt_out`, none of which exist yet (later sub-slices). A user can perfectly validly have zero `membership` rows and still legitimately access campaigns as an ordinary player - this table not having a row for them isn't a gap, it's correct. The tenant-path REST scoping this API already has (`get_tenant_context`, ADR 0020) checks *this* table only (tenant-wide access); a future campaign-scoped equivalent will need to check the fuller rule once campaign-scoped routes exist - a different, additive check, not a replacement.

## Consequences

- First table without `tenant_id` (`app_user`) - RLS doesn't apply to it at all (nothing to scope by); every other new table in this slice still gets one, no exceptions (RFC 0002's own rule).
- `membership`'s `user_id`/`tenant_id` FKs are both `ON DELETE CASCADE` - deleting a User or a Tenant cleans up their memberships automatically, consistent with ADR 0018's default.
- Invitation flow (how a GM adds a player to their tenant) remains an open question (ADR 0010) - not needed yet, since this slice's own tests create `membership` rows directly, not through a REST endpoint.
