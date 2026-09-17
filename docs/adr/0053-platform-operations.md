# 0053 - Platform operations: a platform-operator role, admin listing, and account suspension

Status: accepted

## Context

Every list this API offers today is deliberately scoped to "what the caller can already see": `GET /tenants` is every tenant the caller personally belongs to (ADR 0030), `GET /users/by-email`/`by-nickname` (ADR 0051) is exact-match only, open to any authenticated user but disclosing nothing beyond one id. None of that lets anyone actually operate the platform itself - list every tenant that exists, browse/search users, or suspend an account. A real ops tool for Lorenzo needs a genuinely platform-scoped capability, orthogonal to tenant membership entirely.

## Decision

A new Authgear-Portal-configured role, `platform-operator`, gates a new set of `/admin/*` routes - the exact same mechanism [ADR 0033](0033-tenant-creation-and-update-api.md) already established for `tenant-creator`: a role claim on the verified token, checked against `user.authgear_roles`, with no DB row of its own to manage or a "last one" to protect (that lives in Authgear, not here).

- `GET /admin/tenants` - every tenant on the platform, no membership filter. Reuses `TenantOut` as-is; there is no per-tenant "role" to compute for a caller who need not be a member at all.
- `GET /admin/users` - a real browse/search (`?q=` `ILIKE` against nickname/email), unlike ADR 0051's deliberately exact-match, no-search public lookup - this sits behind the new role instead of being open to any authenticated user, so a broader query surface is an acceptable, deliberate widening here.
- `PUT`/`DELETE /admin/users/{id}/suspend` - suspend/unsuspend an account. A suspended user is rejected on their *very next* request, anywhere in the API: `dependencies.get_current_user` checks `suspended_at` immediately after its own upsert, before anything else runs, so this is one central chokepoint rather than a check scattered per-router.

## Not in scope

- Any "God-mode" read access into a tenant's own data (rosters, campaigns, content) for support purposes - not asked for, and a materially bigger trust boundary than list/search/suspend. If needed later, it deserves its own explicit decision, not a side effect of this role.
- Granting/revoking the `platform-operator` role itself via this API - stays an Authgear Portal action, mirroring `tenant-creator`.
- Any distinction between "suspend" and "ban" beyond one boolean-ish state (`suspended_at` set or not) plus a free-text reason - a finer severity model is real future work, not decided here.

## Consequences

- `config.py`: `platform_operator_role_key`. `dependencies.py`: `require_platform_operator_role`, and `get_current_user`'s new suspension check.
- `models/user.py` gains `suspended_at`, `suspended_by`, `suspension_reason` (nullable; a fresh auto-provisioned user is never suspended by construction).
- New `routers/admin.py`, `exceptions.py` (`PlatformOperatorRoleRequiredError`, `AccountSuspendedError`), `schemas/admin.py` (`AdminUserOut`).
