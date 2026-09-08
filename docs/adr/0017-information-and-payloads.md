# 0017 - Information and payloads

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) designs `information` as "the metadata container for a single piece of information about an entity... The actual content is one or more `payload`s attached to it (a description, an image, a claim, a note, a document, each individually typed)." This ADR promotes a deliberately narrowed slice of that design as sub-slice 6, after `entity` ([0012](0012-entity-table.md)), the tenant bootstrap ([0013](0013-tenant-table-bootstrap.md)), stats ([0014](0014-stats.md)), `entity_prototype` ([0015](0015-entity-prototype.md)), and `containment` ([0016](0016-containment.md)).

This sub-slice's scope is narrower than RFC 0001's full picture, by explicit instruction: `information` here is just `entity_id` + `title` + a free-text `type` (for author-chosen categorization like "GM-note" or "main description"), unique per entity. Four concrete payload kinds: `description` (rich text + locale), `number`, `picture` (binary + file type), `document` (binary + filename).

**Not in scope**: RFC 0001's fuller `information` metadata (source, author, validity/reliability, provenance-as-a-field), the entire `knowledge`/knower system (who can see this - RFC 0001's own open question #1, still unresolved), payload ordering within a bundle, and an `is_public` flag. This proves the container and its four payload shapes; nothing about visibility or authorship attribution is answered here.

## Decision

### information

`information(id, tenant_id, entity_id, title, type, created_at, updated_at)`. `entity_id` FK to `entity.id`, `NOT NULL` - information is always tied to an entity, no freestanding rows. `type` is a plain `TEXT` column, not a native enum: it's free-form, author-chosen categorization ("GM-note," "main description," whatever a campaign finds useful), not a fixed schema-level discriminant like `stat_definition.value_type`. `UNIQUE(entity_id, type)` - an entity can't have two rows of the same type, exactly as specified. This composite unique index's leading column also serves "all information for this entity" lookups, but `entity_id` gets its own index too, matching every other FK column in this codebase regardless of a composite index technically already covering it.

### payload: universal table, no discriminator

`payload(id, tenant_id, information_id, created_at, updated_at)`, FK to `information.id`. Like `entity`, this has **no `kind` column** - which concrete table below has a matching row tells you the kind, the same class-table-inheritance idiom RFC 0001 already established for `entity`/`item`/`being`/`place` (not yet built, but the same pattern). Unlike `entity`, though, a payload conceptually should be *exactly* one kind at a time (a payload isn't simultaneously a description and a number the way an entity can be both an item and a being) - nothing in this schema enforces that, the same kind of accepted, unenforced cross-table invariant already documented for `entity_stat_group` (ADR 0014) and `containment` (ADR 0016). Revisit if this ever causes a real problem in practice.

### Four concrete payload tables

Each has `payload_id` as both primary key and FK to `payload.id` (same shape RFC 0001 describes for `item`/`being`/`place` extending `entity`), plus its own `tenant_id` + RLS - every table gets one, no exceptions, per RFC 0001's tenancy resolution, even though it's derivable transitively through `payload`/`information`.

- `payload_description(payload_id, tenant_id, locale, content)` - `content` is plain `TEXT`; "rich text" is a content convention (e.g. markdown or HTML expected inside it), not a distinct Postgres type. `locale` is plain `TEXT` (e.g. `"en-US"`), unvalidated - format-checking it is an application concern if it's ever needed, not a schema constraint for data that can't otherwise exist.
- `payload_number(payload_id, tenant_id, value)` - `value` is `NUMERIC` (arbitrary precision), not `FLOAT` or `INTEGER`: nothing about "a number" payload says what it represents (a price, a rating, a count), so the type that doesn't silently lose precision either way is the safer default.
- `payload_picture(payload_id, tenant_id, data, file_type)` - `data` is `BYTEA`, storing the bytes directly in Postgres rather than a reference to external object storage. Deliberately the simple choice for this slice: no new infrastructure (bucket, credentials, upload/signed-URL flow) to design. Known tradeoff, flagged rather than hidden: this bloats database size and, on Neon specifically (the deploy target - [ADR 0011](0011-deploy-target-cloud-run-neon.md)), makes storage cost and branch-copying more expensive as blobs grow. Revisit toward external object storage if that becomes a real problem, not preemptively.
- `payload_document(payload_id, tenant_id, data, filename, file_type)` - same `BYTEA` reasoning as `payload_picture`. Originally filename only, per what was actually asked for at the time; **`file_type` added in [ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)** once the binary-content serving endpoint actually needed a real `Content-Type` rather than guessing one from the filename extension - exactly the "revisit when a serving endpoint needs it" moment this ADR originally flagged, not a change of mind.

## Consequences

- Querying "what does this entity know/have written about it" is `information` filtered by `entity_id`, then a join across `payload` and whichever of the four concrete tables actually has a row - no single query returns a fully-typed bundle without a hand-written union/pivot, the same accepted EAV-adjacent cost noted in ADR 0014.
- Same known, unsolved limitation as every join/extension table so far: nothing enforces that a leaf table's `tenant_id` actually agrees with `payload.tenant_id`/`information.tenant_id`, or that exactly one of the four concrete tables has a row for a given `payload_id`.
- `payload_picture`/`payload_document` storing raw bytes in Postgres is the single most consequential simplification here - fine at this slice's scale, worth watching as content volume grows, especially on Neon.
- Same RLS caveat as every table so far: policies are real and tested, but currently unenforced in practice until the app's DB role stops being a superuser (ADR 0002/0012).
