# 0107 - Entity slugs, and resolving them in one request

Status: accepted

## Context

LorenzoScript names entities by slug: `[text](ashfang)`, `[[Ashfang]]` ([RFC 0027](../rfcs/0027-lorenzoscript.md) §3, [ADR 0105](0105-lorenzoscript-entity-references-and-resolver.md)). Today only item instances can have one: `item_instance.slug` ([ADR 0043](0043-item-instance-slug.md)), set once at creation.

[RFC 0015](../rfcs/0015-information-metadata-shape.md) decision 5 already proposed generalizing it to an `entity_slug` table, with a lookup and a set/clear surface. RFC 0027 §7 accepted that decision as its stage 5, and added a batch resolve, so rendering one text costs one request rather than one full `EntityDetailOut` per link.

## Decision

### `entity_slug`

`entity_slug(entity_id, tenant_id, slug)`:

- `entity_id` is the primary key and a foreign key to `entity.id` with `ON DELETE CASCADE`. One slug per entity, as in ADR 0043; this isn't an alias system.
- `tenant_id` is a foreign key to `tenant.id` with `ON DELETE CASCADE`.
- `UNIQUE(tenant_id, slug)` is a plain constraint. "No slug" is simply no row, so the partial index ADR 0043 needed for `NULL`s disappears.
- ENABLE plus FORCE row-level security with the usual `tenant_isolation` policy ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)).

The migration:

1. Copies every `item_instance.slug` into `entity_slug`.
2. Drops the column and its index.
3. Recreates `v_item_instance` to read the slug from `entity_slug`.

`ItemInstanceOut.slug`, `GET .../item-instances/by-slug/{slug}`, and `ItemInstanceCreate.slug` behave as before from the outside. Creating an instance with a slug now writes an `entity_slug` row, and its uniqueness now spans every entity in the tenant, not only item instances.

### What a slug is

A slug matches `[A-Za-z0-9][A-Za-z0-9_-]*` and is at most 100 characters: RFC 0027 §3's grammar, so every slug can appear in `[text](slug)`. It's case-sensitive and matched exactly.

The grammar is checked by the new `PUT .../slug` only. `ItemInstanceCreate.slug` keeps ADR 0043's contract and accepts any string. The first draft of this ADR tightened that field too, since no client in this repo sets it. CI's breaking-change check (oasdiff) rightly rejected adding a pattern and a maximum length to an existing request field: a client outside this repo may rely on it, the same reasoning [ADR 0042](0042-concurrency-token-on-reads.md) applied to `If-Match`.

So a slug outside the grammar can exist: existing ones, and new ones set at creation. It still resolves by exact match through every lookup here. It just can't be written as a LorenzoScript link, and it can't be set again through `PUT`.

### Endpoints

All four are under `/tenants/{tenant_id}/entities`, next to the rest of the entity surface:

- **`GET /by-slug/{slug}`** returns the same `EntityDetailOut` as `GET /{entity_id}`, behind the same gate (a tenant participant). An unknown slug is `404 EntitySlugNotFoundError`, the same whether it's missing or in another tenant.
- **`GET /resolve?slug=…&slug=…`** takes 1 to 100 slugs and returns `[{slug, entity_id, name, kinds}]` for those that exist, in the order asked, once each. The gate is the same tenant-participant check. `kinds` lists which of `item`, `item_instance`, `being`, `character` the entity is, so a client can check a view hint (`being/ashfang`) and choose where a link leads. A slug that doesn't resolve is simply absent: no error, and no difference between "missing" and "not yours".
- **`PUT /{entity_id}/slug`** sets or replaces the slug, as `{"slug": …}`, and returns `{entity_id, slug}`. Another entity already holding the slug is `409 EntitySlugConflictError`. Setting the entity's own current slug again changes nothing.
- **`DELETE /{entity_id}/slug`** clears it and returns `204` whether or not there was one.

Writing uses `authorize_entity_write`'s self-or-managed tier, the one information and knowledge writes use ([ADR 0038](0038-information-payload-knowledge-crud-api.md)). It fails as `403 EntitySlugManagementForbiddenError`; the helper now takes the error to raise.

`EntityDetailOut` gains `slug: str | None`, so a client showing an entity knows how to link to it.

Neither the activity log nor the change feed records slug changes. A slug names an entity, like its name, and renames are exactly what [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md) leaves out of the log. The feed's kinds ([ADR 0099](0099-player-facing-change-feed.md)) describe what happened to belongings, not how they're addressed.

### What "can't see it" means here

RFC 0027 §3 wants an entity a reader can't see to resolve exactly like one that doesn't exist. Resolving shares `GET /entities/{id}`'s gate rather than having one of its own. Today that gate is tenant participation: any participant can read any entity's name and see only the information they're cleared for. So a slug resolves for exactly the readers who could already open the entity by id. Hiding entities themselves from some participants would be a change to that one gate, and both lookups would follow it.

## Not in scope

- Several slugs per entity, and redirects from an old slug after a change.
- Slugs across tenants (repositories, [RFC 0024](../rfcs/0024-repositories.md)).
- Suggesting or searching slugs: `slugify` exists in `@lorenzo/lorenzoscript` for clients that want to propose one from a name.
- Finding texts that link to a slug: stage 7's `content_reference`.

## Consequences

- The one non-additive part is the migration's change to `item_instance`, as RFC 0015 said. Its downgrade restores item instances' slugs from `entity_slug`; slugs on other entities have nowhere to go and are dropped.
- Any entity, a being or a place-to-be, can now be linked from text by slug, and `kinds` lets a client decide where that link goes.
- Other open branches also add migrations on top of the same head, `b28ed28ca209`. Whichever merges second re-parents its migration onto the first, the usual Alembic single-head rule.
- The OpenAPI schema grows, so the typed clients (`apps/loot-bot`, `apps/inventory-web`) are regenerated in the same change.
