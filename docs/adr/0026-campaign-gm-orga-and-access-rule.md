# 0026 - Campaign GM, orga, and the campaign access rule

Status: accepted

## Context

[RFC 0002](../rfcs/0002-campaign-player-character-model.md) deferred `campaign_gm` and tenant-level orga/opt-out out of its own "first slice," but this project's `feat/auth-users` plan pulled both back in - a GM needs a real, first-class row of their own (not a role value on `player`, since GMing and playing track different resources and aren't mutually exclusive), and tenant-wide `orga` access needs a way to opt back out of a specific campaign to just play in it. This sub-slice builds both tables plus RFC 0002's own stated access rule as a directly-testable helper, without yet wiring it into a FastAPI dependency - there is no campaign-scoped route to protect yet.

## Decision

### `campaign_gm(tenant_id, user_id, campaign_id)`

Fully separate from `player`, per RFC 0002's own reasoning - a user can hold both a `player` row and a `campaign_gm` row for the same campaign at once (rotating-GM formats, or a GM who also runs a PC). Shaped exactly like `Membership` ([ADR 0022](0022-user-tenant-membership.md)): composite primary key, no surrogate `id` (nothing needs to reference a specific grant by id), `tenant_id` leading the composite key for the same reason - RLS's per-query `tenant_id = ...` filter is served by the PK's own leading-column index for free, no second index needed. All three FKs `ON DELETE CASCADE` - a GM grant is meaningless once any side of it is gone.

### `orga_campaign_opt_out(tenant_id, user_id, campaign_id)`

Same shape as `campaign_gm` for the same reasons - a composite PK, `tenant_id` leading, all FKs `ON DELETE CASCADE`. A row's mere existence is the opt-out; there's no boolean or status column, since "opted back in" is just deleting the row.

### The access rule, as a plain async helper

RFC 0002 states the rule exactly: *"a user can access a campaign if they hold a `player` row in it, a `campaign_gm` row in it, or are tenant-orga without an opt-out for it."* `campaign_access.can_access_campaign(session, *, user_id, campaign_id, tenant_id)` implements this directly as three short-circuiting existence checks, in the same order RFC 0002 states them - the common case (an ordinary player) resolves after just the first. `tenant_id` is a required parameter rather than derived from `campaign_id` here, matching `get_entity_or_404`'s own established shape ([`dependencies.py`](../../apps/api/src/lorenzo_api/dependencies.py)) of trusting an already-validated `tenant_id` rather than re-deriving it.

This deliberately lives in its own module (`campaign_access.py`), not folded into `dependencies.py` - it's a pure domain-access-rule predicate with no HTTP-specific concerns (no path params, no typed-exception-raising), meant to be directly unit-tested against real fixture data and later wrapped by a thin `get_campaign_context` FastAPI dependency once a campaign-scoped route exists to need one. Keeping it separate now means that future dependency will *call* this function, not duplicate its logic.

## Consequences

- No FastAPI dependency or campaign-scoped route exists yet - this sub-slice is the access rule itself plus its two backing tables, matching this vertical slice's own stated scope (data model + auth mechanism first, a fuller REST surface later).
- `Membership.role == ORGA` is re-checked here rather than cached anywhere - consistent with every other RLS/access check in this codebase reading current state per-request, not a snapshotted claim.
- RFC 0002's status moves from "proposed" to "accepted" alongside this - see the RFC and [ADR 0010](0010-user-tenant-membership-model.md)'s own status line.
