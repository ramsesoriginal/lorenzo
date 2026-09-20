# 0091 - Tenant OWNER joins ORGA in the information-visibility bypass

Status: accepted

## Context

[ADR 0028](0028-knowledge-and-group-membership.md)'s addendum and [ADR 0035](0035-campaign-scoped-gm-visibility.md)/[RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md) let a tenant-wide administrator read everything regardless of visibility - but only the **ORGA** role. Tenant OWNER was left out on purpose: `information_visibility`'s own docstring says OWNER is "deliberately not folded in" because administrative capability over a campaign as an object is "a different axis from character/GM *knowledge* of it". Every other administrative predicate did widen to OWNER or ORGA ([ADR 0030](0030-tenant-campaign-read-api.md)'s `is_tenant_admin`); this bypass alone did not.

[ADR 0085](0085-tenant-data-export-audit-and-runbook.md)'s export audit found what that costs. Proven with a real request (`tests/test_owner_information_visibility.py`): the same `GET /entities/{id}` returns a GM-only information row to an ORGA and **omits it for an OWNER**. So the person with the most authority over a tenant - and the one exporting it under the project's AGPL/self-hosting promise - silently gets an export missing every GM-only fact. The distinction protected nothing in practice either: an OWNER already holds every administrative capability an ORGA does, plus membership management ([ADR 0022](0022-user-tenant-membership.md)/[0032](0032-item-and-item-instance-crud-api.md)), and can manage any campaign regardless of opt-out.

Decided with the maintainer after ADR 0085's addendum put the question to them: OWNER should read it.

## Decision

`information_visibility.resolve_information_visibility` decides its blanket bypass with `campaign_access.is_tenant_admin` (OWNER **or** ORGA) instead of `is_tenant_orga`. Everything else about the bypass is unchanged:

- **The per-campaign opt-out still suppresses it.** An administrator who plays in a campaign and does not want to see its secrets keeps using `PUT .../admin-opt-out` ([ADR 0034](0034-campaign-crud-api.md)), which already works for OWNER (it requires tenant OWNER or ORGA). As `resolve_information_visibility` documents, that suppression is coarser than its per-campaign shape: *any* active opt-out anywhere in the tenant suppresses the bypass for that caller across the whole tenant, because the read route has no campaign parameter to check against. Unchanged, but now applies to owners too.
- **GM reachability (ADR 0035/0046) is untouched.** OWNER is still not folded into the GM-reachable-set; the bypass simply makes it moot for anyone it applies to.
- `campaign_access.is_tenant_orga` stays where it is; only its use here goes.

This **supersedes the "deliberately not folded in" sentence** in `information_visibility.py`'s docstring, which is rewritten to say OWNER now bypasses and why. ADR 0035's decision that a campaign GM sees secrets without tenant membership is unaffected.

## Not in scope

- A finer per-tier authorization model for information ([ADR 0038](0038-information-payload-knowledge-crud-api.md) left it open; still open).
- Changing what an OWNER may *write*. This is read visibility only.
- Any new endpoint. ADR 0085's runbook simply becomes simpler.

## Consequences

- **A behavior change for existing owners.** An OWNER now sees GM-only information on every read that resolves visibility (`GET /entities/{id}`, item and item-instance reads). An owner who also *plays* in a campaign is exposed to that campaign's GM-only text unless they opt out - the same position an ORGA has always been in. It is worth telling owners that the opt-out exists.
- `tests/test_owner_information_visibility.py` flips from documenting the gap to asserting OWNER sees GM-only information (and still that an opted-out owner does not); ADR 0085's runbook drops its OWNER workaround; `tests/test_tenant_export_walk.py`'s deliberate `is False` becomes `is True`.
- The tenant-admin bypass is now a single predicate (`is_tenant_admin`) across campaign reachability, management, and information visibility, instead of one outlier.
