# 0058 - Bulk invite to tenant

Status: accepted

## Context

`POST /tenants/{id}/memberships` (ADR 0036/RFC 0007) invites one user at a time. Onboarding several people into a tenant at once means one HTTP round trip per person today.

## Decision

`_create_membership_core(session, *, tenant_id, tenant, body: MembershipCreate, user) -> None` is extracted from `create_membership`'s existing body (the existence/conflict checks, the `Membership` insert, the `tenant_invite` notification call, ADR 0054) - core mechanics only, no commit, the same shape `_perform_split`/`_perform_set_owner` already established (`routers/item_instances.py`, ADR 0044). `create_membership` becomes a thin wrapper around it.

`POST /tenants/{id}/memberships/bulk`, body `list[MembershipCreate]`, gated by `_require_owner` **once**, up front - unlike `bulk_assign_item_instances`'s per-item re-check, membership-invite authorization ("is the caller OWNER of this tenant") is identical for every item, not item-varying the way item-instance ownership is. Each item still runs inside its own `session.begin_nested()`, catching `fastapi_problem.error.Problem` into a per-item result - the exact `bulk_assign_item_instances` pattern (ADR 0044): never all-or-nothing, one result per input, a bad entry doesn't sink the rest of the batch.

New `BulkMembershipResultItem`: `{user_id, status: Literal["ok","error"], membership: MembershipRosterEntryOut | None, problem: ProblemOut | None}` - exactly `BulkAssignResultItem`'s shape, renamed.

`ProblemOut` (previously private to `schemas/items.py`) is promoted to `schemas/common.py` - a generic `Problem.marshal()` mirror with nothing item-specific about it, now with a second consumer.

## Consequences

- `routers/tenants.py` (`_create_membership_core`, `create_membership` refactored, new bulk route); `schemas/tenants.py` (`BulkMembershipResultItem`); `schemas/common.py` (`ProblemOut`, moved from `schemas/items.py`, which now imports it).
