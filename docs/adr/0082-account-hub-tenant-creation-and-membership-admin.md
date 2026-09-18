# 0082 - account-hub: tenant creation, tenant-level membership admin, bulk invite

Status: accepted

## Context

Sub-slices (d)/(e) of [RFC 0017](../rfcs/0017-account-hub-roster-tenant-admin-and-notifications.md) - both are about who can administer a tenant itself (as opposed to a campaign within it), and both were already fully scoped by the RFC.

## Decision

### (d) Create a tenant, always shown

`POST /tenants` (`TenantCreate`: `name` required, `slug`/`description` optional) via a form rendered unconditionally at the top of `/tenants`, above the tenant list, regardless of whether the caller belongs to any tenant yet. `require_tenant_creator_role` is a platform-level Authgear role with no field anywhere in `MeOut` (or any other response this app reads) to check before deciding whether to show the form - so it isn't approximated. A 403 from the API surfaces exactly like any other authorization failure this app already handles this way.

### (e) Tenant-level membership administration + bulk invite

New `src/lib/membershipAdminUi.ts` (`renderMembershipAdmin`), shown per tenant only when `tenant.role === 'owner'` - not `isTenantAdmin`'s broader owner-or-orga check used elsewhere on this page. This is deliberate: bulk invite (`POST /tenants/{id}/memberships/bulk`) is confirmed `_require_owner`-gated server-side, and the single-item actions (`POST`/`PATCH`/`DELETE /tenants/{id}/memberships/{user_id}`) are gated identically here for consistency rather than assumed looser. Showing nothing to an `orga` who might technically have single-item rights is the safe direction of a wrong guess; a 403 shown to an `owner` who should have had access is not.

The panel has three parts: the current membership list (name, a role `<select>` that calls `updateMembership` on change, a Remove button calling `deleteMembership`); a single-invite form reusing the ADR 0074 user picker; and a bulk-invite form, where each row is its own picker instance plus a role select, "Add another" appends rows, and "Send invites" calls `bulkInviteMembers` once with every resolved row and renders one result line per input (`BulkMembershipResultItem`, never all-or-nothing per ADR 0062) rather than assuming success.

## Consequences

- `src/lib/types.ts` gains `TenantCreate`, `MembershipCreate`, `MembershipUpdate`, `BulkMembershipResultItem`, `ProblemOut`, checked against the live schema.
- `src/lib/tenants.ts` gains `createTenant`, `createMembership`, `updateMembership`, `deleteMembership`, `bulkInviteMembers`.
- `tenants.astro` stays orchestration-only per ADR 0080's stated incremental-split policy - this ADR's own UI lives entirely in `membershipAdminUi.ts`, not inline on the page.
