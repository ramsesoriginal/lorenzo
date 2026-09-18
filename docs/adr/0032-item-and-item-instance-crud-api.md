# 0032 - Item and item-instance CRUD API

Status: accepted

## Context

Every route in `apps/api` was `GET` until now - [ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md) scoped itself explicitly to read-only, and nothing had picked up "a fuller CRUD REST surface" since. GitHub milestone #1's scenario needs actual writes: a generic Sword, a Flaming Sword prototyping it, a concrete instance ("Ashfang") owned by a character and moved between containers over the wire. This ADR accepts [RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md), close to verbatim - see it for the full reasoning trail behind each convention below. It's also the first write surface in this codebase, so several of its decisions are cross-cutting, reused by every CRUD RFC after it rather than re-decided per RFC.

## Decision

### Cross-cutting write-API conventions

`POST` → `201` + `Location` (via `request.url_for`) + the resource's own canonical `GET` shape. `PATCH` and the owner/container actions → `200` + the same. `DELETE` → `204`, except deleting the owner/container sub-resources, which return `200` + the parent (the parent survives; returning nothing would just force a follow-up `GET`). `<Resource>Create`/`<Resource>Update` schemas, the latter with every field `| None = None`, applied via `model_dump(exclude_unset=True)`. Optimistic concurrency via an optional `If-Match` header, checked against a weak ETag derived from `updated_at` (`etag.py`) - absent, last-write-wins; present and stale, `412 PreconditionFailedError`. New typed problems (`ItemPrototypeInUseError`/`InvalidItemPrototypeError`/`ItemInstanceManagementForbiddenError` → `ConflictProblem`/`UnprocessableProblem`/`ForbiddenProblem`; `PreconditionFailedError` subclasses `StatusProblem` directly, since `fastapi_problem` has no named 412 base). 404 for "no relationship to this resource at all" (existence hidden), 403 for "can already read it, lacks a specific write permission" - every check below picks one deliberately.

### `entity_access.py` (new) - the shared ownership/containment reachability walk

Built to serve both this ADR's self-or-managed authorization *and* [RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md)'s GM-reachable-set from day one, per RFC 0005's own flagged follow-up - one implementation, not two independent copies. `controlled_character_entity_ids` (a user's own characters, via `Player`→`CharacterPlayer`), `reachable_entity_ids` (a root set, plus everything `Ownership`-owned by it, plus everything reachable via `Containment`, recursively), `can_self_manage_entity` (is a given entity in the reachable set rooted at the caller's own characters). The recursive containment CTE moves here from `routers/item_instances.py`, generalized to start from a *set* of roots rather than one container - that router's own container-filtered listing now imports and reuses it instead of keeping a second copy.

### `campaign_access.can_manage_campaign`, pulled forward from RFC 0006

Instance authorization below needs it (assigning/managing an item tied to a specific campaign), and campaign CRUD ([RFC 0006](../rfcs/0006-campaign-crud-api.md)) will consume the exact same predicate for its own mutations rather than each RFC keeping its own copy - built once, here, since this ADR needs it first. `can_manage_campaign`: a `CampaignGm` row, or tenant-wide `OWNER`/`ORGA`, regardless of any `TenantAdminCampaignOptOut` (administrative capability over a campaign is a different axis from *play* visibility). Alongside it: `can_manage_any_campaign_in_tenant` (the ownerless-creation fallback), `campaign_ids_for_character`, `can_manage_any_of_campaigns` ("any one is enough", per RFC 0005's own reasoning that a character's inventory is already shared uniformly across every campaign it's rostered into).

### Catalog vs. instance authorization

**Catalog** (`item`): `get_tenant_context` unchanged - authoring the shared vocabulary is a tenant-admin concern. `POST/PATCH/DELETE /tenants/{tenant_id}/items[/{id}]`, `ItemCreate{name, prototype_ids}`/`ItemUpdate{name}`. `DELETE` guarded: `409 ItemPrototypeInUseError` if any `item_instance` still directly prototypes it - [ADR 0018](0018-sqlalchemy-modeling-conventions.md)'s blanket cascade would otherwise silently strip inherited stats from every such instance.

**Instances - revised to self-or-managed**, matching RFC 0005's own text: self-service if reachable from one of the caller's own characters (via `entity_access.can_self_manage_entity`, checked against the entity's *current* state); assigning to someone else's character needs `can_manage_campaign` on any one of that character's campaigns; no owner reachable at all falls back to `can_manage_campaign` on any campaign in the tenant. `POST/PATCH/DELETE /tenants/{tenant_id}/item-instances[/{id}]` plus `PUT`/`DELETE .../owner` and `.../container` as singular sub-resources (replace/clear, matching `ownership`/`containment`'s own "no row means no relation" shape). `POST /item-instances` validates `prototype_id` resolves to an `Item` (`422 InvalidItemPrototypeError` otherwise) and creates `Entity`+`ItemInstance`+`EntityPrototype`, plus `Ownership`/`Containment` if given, one transaction.

### Read authorization for item-instances, revised from `get_tenant_context` to `get_tenant_or_404` + `is_tenant_participant`

**Not explicitly specified by RFC 0005** (which only tables the write endpoints' auth), but a real, concrete requirement surfaced by checking the milestone directly: Xavier and Yvonne (plain `Player`s controlling Alice/Bob) must be able to `GET` an item instance, and neither role implies a tenant-wide `Membership` row (ADR 0022) - the exact gap RFC 0005's own Context section names for writes applies identically to the pre-existing `GET` routes on this router. Fixed the same way [ADR 0030](0030-tenant-campaign-read-api.md) already fixed the identical shape for campaigns: router-level `get_tenant_or_404` (existence + RLS only), each `GET` route applying its own explicit `is_tenant_participant` check (a `Membership`/`Player`/`CampaignGm` row anywhere in the tenant - broader than `get_tenant_context`, still not wide open to an unrelated authenticated user). Catalog (`item`) reads are unaffected, still `get_tenant_context` - the milestone's own `GET item` calls resolve to the instance, "Ashfang," not its catalog prototypes.

### RLS context after a mid-request commit

**A real bug found and fixed while implementing, not part of RFC 0005's own text**: `get_tenant_context`/`get_tenant_or_404` set `app.tenant_id` via `set_config(..., is_local=true)`, scoped to the transaction active when the dependency ran. Every route until now was read-only and never committed, so the setting survived for the whole request. A write route that commits and then re-reads its own row (to return the canonical `GET` shape, per this ADR's own convention above) ends that transaction, silently losing RLS's tenant scoping for the post-commit read - confirmed the hard way (`invalid input syntax for type uuid: ""` from inside the RLS policy itself, not from any bound parameter). Fixed with a new `dependencies.set_tenant_rls_context`, called again after every commit that's followed by a read.

### Attribution

`ItemOut`/`ItemInstanceOut` gain `created_by`/`updated_by`, read off `entity.created_by`/`updated_by` (already eager-loaded via `VItem.entity`/`VItemInstance.entity`, no view migration needed). `POST` sets both to `CurrentUser.id`; `PATCH` (a rename) updates `updated_by`. The owner/container actions never touch `entity.updated_by` - moving an item isn't "updating" it in the sense that column tracks ([ADR 0029](0029-attribution-created-by-updated-by.md)).

## Not in scope

Everything RFC 0005 itself excludes: stat/information mutation, prototype-graph editing on an existing item, bulk operations. See that RFC for the reasoning.

## Consequences

- No migration - `item`/`item_instance`/`entity_prototype`/`ownership`/`containment` and `entity.created_by`/`updated_by` ([ADR 0029](0029-attribution-created-by-updated-by.md)) all already exist.
- `entity_access.py` is now a real dependency for [RFC 0009](../rfcs/0009-campaign-scoped-gm-visibility.md) to build on rather than design fresh - its GM-reachable-set is the identical `reachable_entity_ids` walk, rooted at a campaign's characters instead of the caller's own.
- `campaign_access.can_manage_campaign`/`can_manage_any_of_campaigns`/`campaign_ids_for_character`/`can_manage_any_campaign_in_tenant` exist ahead of campaign CRUD's own ADR (0034) landing - that ADR consumes them rather than defining them.
- `dependencies.set_tenant_rls_context` is now the established pattern every future write route must follow after its own commit, not just this ADR's two routers.
- `routers/campaigns.py`'s `get_tenant_or_404` + `is_tenant_participant` shape is now precedent used twice, not once - future routers needing "any participant, not just tenant-wide members" reach for the same pair rather than reinventing it.
