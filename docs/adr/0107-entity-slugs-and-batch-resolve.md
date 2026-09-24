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

`ItemInstanceOut.slug` and `GET .../item-instances/by-slug/{slug}` behave as before from the outside. Creating an instance with a slug now writes an `entity_slug` row. Its uniqueness now spans every entity in the tenant, not only item instances, and it follows the grammar below.

### What a slug is

A slug matches `[A-Za-z0-9][A-Za-z0-9_-]*` and is at most 100 characters: RFC 0027 §3's grammar, so every slug can appear in `[text](slug)`. It's case-sensitive and matched exactly. The grammar is checked on every write: the new `PUT .../slug`, and `ItemInstanceCreate.slug` too.

For `ItemInstanceCreate.slug` that's a breaking change. ADR 0043 accepted any string, and CI's `openapi-diff` job reports the new pattern and maximum length on an existing request field as errors. The maintainer chose one grammar for every write over keeping that contract, and the break is accepted the way [ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md)'s addendum accepted its new enum value:

- **`apps/api/openapi-breaking-accepted.txt`** lists the two findings, so any other breaking change still fails the job.
- **Versioning.** The change ships in a commit with a `BREAKING CHANGE:` footer. ADR 0103 already makes `apps/api`'s next release 1.0.0, so this adds a changelog entry, not another major version.
- **Repo clients.** None sets a slug when creating an instance, and their typed clients are regenerated in the same change.

Existing slugs aren't re-validated. One that doesn't fit still resolves by exact match; it just can't be written as a link, or set again.

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

- Two parts aren't additive. One is the grammar on `ItemInstanceCreate.slug`, above. The other is the migration's change to `item_instance`, as RFC 0015 said. Its downgrade restores item instances' slugs from `entity_slug`; slugs on other entities have nowhere to go and are dropped.
- Any entity, a being or a place-to-be, can now be linked from text by slug, and `kinds` lets a client decide where that link goes.
- The migration was written on top of `b28ed28ca209`, like ADR 0103's and ADR 0104's. Those reached `main` first, so it's re-parented onto `5fade6f98352`, the usual Alembic single-head rule.
- The OpenAPI schema grows, so the typed clients (`apps/loot-bot`, `apps/inventory-web`) are regenerated in the same change.
