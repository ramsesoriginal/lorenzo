# RFC: Entity kinds and author freedom — making an entry whatever it is

Status: accepted, decided with the maintainer on 2026-10-07: kinds stay marker tables with no new table per author ([§2](#2-making-an-entry-with-kinds)), one thin registry of the tables a copy carries ([§1](#1-a-copyable-table-registry)), the field is called `kinds` ([§2](#2-making-an-entry-with-kinds)), a kind change after a first publish is a breaking change and the round-trip matrix gates publishing such entries ([§2](#2-making-an-entry-with-kinds)), parents for every entry ([§3](#3-parents-for-any-entry)), rename-only stat PATCH ([§6](#6-stat-group-and-stat-definition-patch-rename-only)), deleting something libraries hold warns with a count and never blocks ([§9](#9-deleting-what-libraries-hold)), and RFC 0018 closed as superseded by parents ([§10](#10-rfc-0018-is-closed)). The guards on deleting an entry that is also a being, the kinds an inventory item may take, any-of for the kind filter and the refusal of a reorder by someone who cannot see every note are decided too. The remaining mechanisms inside those decisions (routes, field names) are a proposal for review, the three spike-gated points are in [Spikes](#spikes), and what is still open is in [Open questions](#open-questions). Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. Rows "Authoring tool" and "Publish, subscribe, update screens" of [v1.0](../../v1.0.md); part of [RFC 0036](0036-repository-tooling.md).

## Context

Studio and [Bench](0039-bench-authoring-offline-and-extensibility.md) let an Author do what the API allows, and the API was built one kind at a time: a route to make an item, a route to make an inventory item, a route to make a character. Writing the tools showed where that leaves an author. A sentient sword, a race that other beings inherit from, a category node that is neither, a catalog sorted by name, a rename of a stat group, a picture on an entry: each is something a person writing a repository reasonably wants, and each stops at a missing route rather than a missing idea. This RFC lists those gaps, checked against the code, and closes them with the smallest change each, keeping what is already decided: no new table per author, and the copy engine as the one thing a repository's content must pass through.

Words, once: an **entry** is what the UI calls an `entity` (the table and the API's term); its **kind** is which marker rows it has. The user-facing words are those of [ADR 0194](../adr/0194-user-facing-terminology.md). The **parent** of an entry is the API's `prototype`: an `entity_prototype` row, which is what "inherits from" means.

### How kinds work today

- **`entity` is the identity and says nothing about kind.** There is no discriminator column ([ADR 0012](../adr/0012-entity-table.md)). `item`, `being`, `item_instance` and `character` are tables keyed by `entity_id`; an entry's kinds are the rows that exist for it. `item` has one column of its own (`in_public_catalog`, [ADR 0116](../adr/0116-players-read-catalog-items-and-a-public-catalog.md)); a `character` row's key points at `being`, so a character is always a being.
- **An entry may have more than one.** [RFC 0001](0001-core-domain-data-model.md) names the sentient sword, and nothing in the schema forbids an `item` row and a `being` row on one entry. No route makes one, and no repository test has one: the fixtures hold an item, an inventory item, and a being that is also a character.
- **The API makes kinds only through kind-specific routes.** `POST /items`, `POST /item-instances`, and `POST /characters` (which makes an entry, a `being` and a `character` together). `PUT /characters/{id}` promotes an existing being, but no route makes a being without a character, and a character's `DELETE` only demotes it ([ADR 0036](../adr/0036-user-player-character-crud-api.md)), so a being, once made, cannot be deleted. A bare entry (no kind) can be made as a group ([ADR 0064](../adr/0064-group-write-api.md)); deleting a group removes its members and leaves the entry.
- **Parents are written only for items.** `PUT /items/{id}/prototypes` and the three `bulk-*` routes load the entry through the `item` table, so a being or a bare entry has no way to inherit from anything ([ADR 0072](../adr/0072-item-catalog-prototype-set-editing.md)). The table and its cycle trigger are generic: `entity_prototype` relates any two entries of a tenant, and its `BEFORE INSERT` trigger rejects a loop whatever the kinds. An inventory item's one parent changes through its own route ([ADR 0192](../adr/0192-the-placeholder-item-the-api-and-the-seed.md)).
- **Finding entries.** `GET /entities` returns every entry ordered by name, with no filter. `GET /items` and `GET /beings` have `q`, and `GET /items` also `prototype_id` and `recursive`, but both are ordered by id. Every list entry in `GET /entities` is an `EntitySummary` with no kinds, though `GET /entities/resolve` already reports `kinds` for a slug.
- **Stats.** There is no `PATCH` for a stat group or a stat definition: [ADR 0103](../adr/0103-stat-tags-enum-values-and-mandatory-groups.md) left it out "until a client needs it", [ADR 0014](../adr/0014-stats.md)'s addendum and [ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md) say neither can be renamed, and an enum value can be added or removed but not renamed or reordered (`sort_order` exists, nothing writes it). A direct value for a non-bool stat cannot be cleared; that is [RFC 0039](0039-bench-authoring-offline-and-extensibility.md)'s W1. The lists return a few named columns and four named stat groups; the effective value of any other stat takes one `GET /entities/{id}` per entry.
- **Notes and pictures.** An entry's notes (the API's `information`) carry a unique `order`, and `PATCH` of an `order` that is taken is a `409`, so a reorder is a scramble of requests ([RFC 0015](0015-information-metadata-shape.md) decision 12 and [ADR 0101](../adr/0101-editable-information-and-description-payloads.md) both deferred it). Creating a note writes one description payload. The picture payload (`payload_picture`, bytes in Postgres) and `GET /tenants/{tenant_id}/payloads/{id}/content` exist, and `payload` rows are copied with an entry, but no route creates any payload other than a description, and `PATCH` of a payload edits only descriptions. Profile pictures set the precedent for an upload: a content-type allow-list and a size cap ([ADR 0056](../adr/0056-profile-pictures.md)).
- **Templates.** [RFC 0018](0018-entity-template.md) proposed `entity_template` tables and was never built. [RFC 0026](0026-world-model-axes-and-address.md) and [RFC 0028](0028-time-causality-and-calendars.md), which would add places, clocks and calendars, are still open.

### What a library does with kinds

- **The copy engine is table by table, keyed on the entry's id**, so it does not care how many kinds an entry has. The planner writes each marker row in its own branch from the set of kinds ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)); a being that is also a character already copies that way. An item that is also a being would copy the same way, though it has never been run.
- **A new table is edited into several places by hand:** `REPOSITORY_CONTENT_TABLES` and `REPOSITORY_EXCLUDED_TABLES` in `repository_access.py`, `_TABLES` and `_LINKS` and the per-table counts of `forget_copy` in `repository_copying.py`, and `load_content` and its `KINDS` in `repository_content.py`; a new kind also gets a branch in the planner and an entry in the `_KINDS` of `routers/entities.py`; two tests fail if a tenant table is in neither list or has no policy ([ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md), [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). Each new kind, and each RFC that adds a marker table, repeats that.
- **Updates ignore kinds.** A copy link's snapshot records an entry's `kinds`, but `repository_updates.py` declares `_IGNORED = {"kinds"}` and the diff skips it ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)). Harmless while no route changes a kind after creation; once one does, a kind added to an entry in a repository never reaches the libraries that copied it.

## Decision

### 1. A copyable-table registry

One small module lists every copyable table once, with what a copy needs to know about it: its model, whether it is content or excluded, its place in the insert order, and whether it is a link table. From that one list come:

- the two sets in `repository_access.py`, `_TABLES` and `_LINKS`, and the table list `forget_copy` counts over (its queries stay hand-written);
- the conformance tests: every tenant table is in the registry, every content table has the read policy, every foreign key between two of them is composite on `tenant_id`.

It is deliberately thin. It **cannot generate** the planner's per-table translation (which ids to re-target, what collides) or the diff's field semantics (`_SETS`, `_KEYED`, what is shown and never applied); those stay hand-written. What it adds is a test that a table in the registry either has a planner step or says which parent row carries it (a `payload_description` rides with its `payload`), so a table added without copy semantics fails loudly instead of being silently left out of a copy.

The registry is reused, not duplicated: Bench's bulk export ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md) W3) and the release serialiser ([RFC 0037](0037-releases-and-public-snapshots.md) R5) enumerate content through it. It is not a plug-in point and not data: a kind is added by a migration and a line in the registry, never by a tenant ([§11](#11-places-clocks-and-calendars)).

### 2. Making an entry with kinds

The field is **`kinds`**, never `roles`: Owner, Organizer and Author are roles ([RFC 0040](0040-authors-and-invites.md)), and the API already says `kinds` in `GET /entities/resolve`.

- **`POST /tenants/{tenant_id}/entities`** with `{name, slug?, kinds, parents?, in_public_catalog?}` creates the entry, its link name (the API's `slug`, [ADR 0139](../adr/0139-name-an-item-when-it-is-created.md)), its marker rows and its parent edges in one transaction. `kinds` is a list of `item` and `being`; empty makes a bare entry, which is what a group is today. `in_public_catalog` is valid only with `item`. The gate is the one `POST /items` has.
- **`character` stays out**, and so does `item_instance`. A being becomes a character through `PUT /characters/{id}` as today; an inventory item is made from a catalog item and keeps its own route and its one parent.
- **`PUT /entities/{id}/kinds/{item|being}`** adds a kind (idempotent: `201` the first time, `200` after, as `PUT /characters/{id}` does) and **`DELETE`** on the same path removes it. Both honour `If-Match`, touch the entry's `updated_at` and are written to the activity log.
- **Refused.** Removing `item` while any inventory item inherits from the entry directly (the guard `DELETE /items/{id}` already has); removing `being` while a `character` row exists (its key would cascade away; demote it first). The `409` says which.
- **A guarded `DELETE /entities/{id}`** deletes the entry, with the guards of each of its kinds composed. Today nothing deletes a being or a bare entry, so a being made by this route could never be removed. The kind-specific deletes keep working and, as now, delete the whole entry ([Open questions](#open-questions)).
- **A kind change after a first publish is a breaking change.** Adding `being` to a catalog item changes what the entry is in every library that copied it (it appears in beings lists and in a GM's reach, [ADR 0173](../adr/0173-a-gm-lists-the-beings-they-can-see.md)); removing `item` takes it out of catalogs. So [RFC 0037](0037-releases-and-public-snapshots.md)'s breaking-change detector reports a changed kind set on an entry an earlier release held, and the release composer shows it as a visible **Kind added** or **Kind removed** row rather than letting it travel quietly.
- **Updates stop ignoring `kinds`.** The diff shows a changed kind set as its own row. Accepting **Kind added** adds the marker row to the library's copy. **Kind removed** is applied only if the library's copy allows it (no inventory item inherits from it, no character on it), and otherwise skipped with the reason, as an enum value still in use is today ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).
- **The round-trip matrix gates publishing, not creating.** A draft repository may hold any combination the routes allow. A repository may be published (`PUT /published`, and a release once [RFC 0037](0037-releases-and-public-snapshots.md) lands) only if every kind combination in it is one a passing matrix covers: bare, `item`, `being`, `item`+`being`. The matrix runs each combination through a first copy, an update that adds the entry, an update that changes its name, parents, stats and notes, a kind added and removed after the copy, and a purge, in a plain repository and in a bridge ([RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md)). The proposed mechanism is a list of proven combinations in the API that publishing checks and the matrix test asserts complete; K2 settles it.

### 3. Parents for any entry

**`PUT /tenants/{tenant_id}/entities/{id}/parents`** with `{parent_ids}` replaces an entry's own direct parents, an empty list clears them, exactly as `PUT /items/{id}/prototypes` does: not itself, every id in the tenant, a loop refused by the trigger as `409`, `If-Match`, `updated_by` touched, one activity entry. It works for an item, a being, a character, and a bare entry, so a race or a class can be a being that other beings inherit from, and a group can sit under a category. `PUT /items/{id}/prototypes` calls the same code and stays. An inventory item keeps its own parent route ([ADR 0192](../adr/0192-the-placeholder-item-the-api-and-the-seed.md)); the generic route refuses it ([Open questions](#open-questions)).

No migration and no copy-engine change: the table, the trigger, and the engine's handling of `prototypes` (carried in every entry's snapshot, merged element by element in updates) are already generic, and effective stats resolve through any entry's parents ([ADR 0037](../adr/0037-effective-stat-resolution.md), [ADR 0039](../adr/0039-generic-effective-stat-view.md)). It also removes the API obstacle to what [RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md) left for later: beings (race, class) joining a rules repository the way items do.

### 4. Duplicate, and new from parent

Two author actions, built in the order that shows what they should do.

- **New from parent**: a new entry whose only content is `parents: [P]`. It needs nothing beyond [§2](#2-making-an-entry-with-kinds) and [§3](#3-parents-for-any-entry). It is what a template was going to be ([§10](#10-rfc-0018-is-closed)).
- **Duplicate**: a new entry with the same kinds and parents, and its own copy of the stat values, formulas, description and notes. First **client-side**, a sequence of existing routes from Studio and Bench (create, set parents, set stats, add notes), because what a person wants copied (GM-only notes? pictures?) is a question the first version of the dialog answers. Then a server `POST /entities/{id}/duplicate`, one transaction, with the choices the dialog turned out to need. `POST /groups/{id}/duplicate` ([ADR 0064](../adr/0064-group-write-api.md)) is the precedent.
- **Never copied** by a duplicate: the link name (unique), containment and ownership, who knows what, and a copy link. A duplicate of something a library copied is the library's own entry with no origin.

### 5. Finding entries

- **`GET /entities`** gains `q` (a case-insensitive substring of the name, as on items and beings), `kind` (repeatable; an entry matches any of those given), and `parent_id` with `recursive`, as `prototype_id` and `recursive` work on items. Its rows gain `kinds`, computed the way `GET /entities/resolve` does, so a client need not ask once per entry.
- **`GET /items` and `GET /beings` are ordered by name, then id**, as `GET /entities` already is. Ordering by id is stable and meaningless to a person, and a catalog of three hundred rows in id order is not browsable.

### 6. Stat group and stat definition PATCH, rename-only

The stat vocabulary becomes editable in the one way an author needs and nothing more. This amends [ADR 0143](../adr/0143-lorenzo-seed-taxonomy-and-stats.md) (the seed stops when a definition exists with another type or group, and says a stat cannot be retyped or moved) and the "cannot be renamed" note in [ADR 0014](../adr/0014-stats.md)'s addendum and [ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md).

- **`PATCH /stat-groups/{id}`**: `name`, `priority`, `mandatory`.
- **`PATCH /stat-definitions/{id}`**: `name`. **`PATCH …/enum-values/{value_id}`**: `value` (rename) and `sort_order` (reorder).
- **No retype, and no move of a definition between groups.** Both stay impossible: a value stored as one type has no honest conversion, and [ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)'s refusal to delete a definition in use stands.
- **A name already taken in the tenant is `409`.**
- **An enum rename rewrites what stores the old text, in the same transaction**: `entity_stat.value_text`, and the `true_value` and `false_value` of a comparison formula whose target is that enum. K6 lists every column that can hold an enum value before it is built.
- **What a library sees.** Renaming and changing `priority` or `mandatory` already reach libraries: the update engine applies a changed `name`, `priority` or `mandatory` on a copied group or definition and skips one whose new name is taken there. An enum rename reaches them as an added value and a removed one, and the removal is refused where the old value is still in use ([Open questions](#open-questions)); a reorder does not reach them, since `sort_order` is not in the snapshot.
- **That a stat write bumps the entry's version** is [RFC 0039](0039-bench-authoring-offline-and-extensibility.md)'s W1, not this slice.

### 7. A bulk effective-stat read

**`GET /tenants/{tenant_id}/entities/effective-stats`** takes the filters of [§5](#5-finding-entries) and one or more `stat_definition_id`, is paged, and returns for each entry and stat the effective value, whether the entry holds it itself, and the entry it is inherited from ([ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md)), with formulas evaluated. A compare grid is then "the list, plus these columns" in one request per page instead of one per entry. The gate is the one the corresponding single read has: for a non-member, only the public catalog ([ADR 0116](../adr/0116-players-read-catalog-items-and-a-public-catalog.md)). A `POST` form taking explicit ids is added only if the spike shows a filter cannot express a grid ([Spikes](#spikes)).

### 8. Note order, payloads, and pictures

- **`PUT /tenants/{tenant_id}/entities/{id}/information/order`** with the complete list of the entry's note ids in the new order. One transaction under the entry's note lock ([ADR 0101](../adr/0101-editable-information-and-description-payloads.md)). It carries no `If-Match`: the list must name every row, so a client that has not seen a new note gets a `409` and refetches, which answers the concurrency question [RFC 0015](0015-information-metadata-shape.md) left open.
- **`POST /tenants/{tenant_id}/information/{id}/payloads`** adds a picture payload (a multipart upload), and `DELETE /tenants/{tenant_id}/payloads/{id}` removes one. Payload `order` is appended by the existing trigger. Documents and numbers are not in this RFC.
- **`PUT /entities/{id}/picture`** and `DELETE` on it are the convenience for the entry's one main picture: they write the singleton `main_picture` note and its payload.
- **Size cap and storage.** A content-type allow-list (PNG, JPEG, WebP, GIF), a size cap in a new setting that starts at the profile-picture cap (2 MiB), bytes in Postgres as `payload_picture` already stores them ([ADR 0017](../adr/0017-information-and-payloads.md), [ADR 0056](../adr/0056-profile-pictures.md)), and no content sniffing beyond the declared type, the trust the existing pictures get. A per-tenant byte quota belongs to the pre-launch gates of [RFC 0038](0038-public-repositories-and-discovery.md) and is not set here.

### 9. Deleting what libraries hold

Deleting an entry, a stat definition or a stat group that libraries have copied **warns with the number of libraries still holding it and never blocks**. Deleting a stat definition that is in use stays refused ([ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)); this is about the delete that is allowed.

- **A read, not a gate:** `GET …/entities/{id}/libraries`, and the same under `stat-definitions/{id}` and `stat-groups/{id}`, answer `{count}` for a member of the repository. Studio and Bench show it in the delete dialog ("3 libraries have copied this. They will see it as removed upstream."), and `lorenzo repo` prints it. The delete itself is unchanged and the count is written to its activity entry.
- **Counts only, never names.** The links that say who copied what live in the copying library's own rows, which the repository's owner cannot read ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)), and an owner can already list the libraries a repository is granted to ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)); what a library copied stays its own business, as [RFC 0038](0038-public-repositories-and-discovery.md) keeps the privacy of who took a public repository. A narrow aggregate over copy links is the one place this is read across tenants ([Spikes](#spikes)). It counts the libraries whose link still points at a live row, so a library that deleted its copy is not counted.
- **What the libraries see** is what they already do: `repo updates` reports the row as removed upstream and leaves their copy as it is ([ADR 0167](../adr/0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md), [ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).

### 10. RFC 0018 is closed

[RFC 0018](0018-entity-template.md) is closed as superseded. Its question, which combination of notes and stats makes "a D&D character sheet" or "a magical weapon", is answered by an entry that other entries inherit from: it carries the stat groups, default values and description, "new from parent" ([§4](#4-duplicate-and-new-from-parent)) makes the instance, and a copy carries the parents. Nothing is added to the schema, to the registry, or to what a copy must enumerate. K10 changes its status line and links here. It is reopened only for a **slot case that parents cannot cover**: an ordered, curated *view* that names which note types and stat groups a sheet shows and in what order. That is a read-side projection, not something an author needs in order to write a repository, and a case for it is brought as its own RFC.

### 11. Places, clocks and calendars

[RFC 0026](0026-world-model-axes-and-address.md) and [RFC 0028](0028-time-causality-and-calendars.md) are open, and nothing here presumes their outcome. Where either proposes an entry subtype (a connection, a clock; events as entries), the cost of making it a kind is known and small: a marker table with `entity_id` as its key, one registry line ([§1](#1-a-copyable-table-registry)), one planner step, one more row in the matrix, and one more value `PUT /entities/{id}/kinds/{kind}` accepts, with the kind's own columns in that request's body as `in_public_catalog` is for `item`. The Bench side, a kind-agnostic entry shell and a command registry so a new kind adds an editor rather than rewrites one, is [RFC 0039](0039-bench-authoring-offline-and-extensibility.md)'s seam; registries are extracted when the first kind beyond item and being exists.

## Decided with the maintainer (2026-10-07)

- **Kinds are marker tables** (option a), not data an author defines. The field is `kinds`.
- **A thin copyable-table registry**, reused for export and the release serialiser, and by each new kind.
- **`character` stays out of `kinds`.** Removing `item` is refused while inventory items exist.
- **A kind change after the first publish is a breaking change** in the release ledger, with a visible "Kind added" row.
- **The round-trip matrix gates publishing such entries**, not creating them in a draft repository.
- **Generic parents** for beings and groups too; duplicate and "new from parent" client-side first.
- **Stat PATCH is rename-only**, amending ADR 0143.
- **Deleting something libraries hold warns with a count**, a narrow aggregate, never names, no block. Deleting a stat definition in use stays refused.
- **RFC 0018 is closed** unless a slot case appears that parents cannot cover.
- **Deleting an entry that is also a being** deletes the entry, with the guards of every kind composed and the other kinds named in the delete dialog; it is not refused until the extra kind is removed.
- **An inventory item may take the kind `being`** (a summoned creature tracked as inventory) and not `item`, and takes no generic parents.
- **Any-of for the `kind` filter**; an "all of" form only if a client asks.
- **A reorder of notes is refused** from a caller who cannot see every note of the entry.
- **The item route keeps the name `prototypes`** next to the generic `parents`, until a cleanup.
- **The delete count is a read, not a gate.** A script may skip it; no acknowledgement is required.

## Spikes

Each on a throwaway branch, its findings written back here, as the umbrella rule is.

1. **Item and being on one entry, through a copy.** Build the entry in a draft repository, copy it, update it, add and remove a kind after the copy, purge. Audit the queries that assume one kind (`GET /beings`, the item list's joins, a GM's reach). A result that needs engine changes beyond [§2](#2-making-an-entry-with-kinds)'s `kinds` diff keeps `item`+`being` creatable but off the list of publishable combinations until it is fixed; no result removes it from drafts.
2. **The library count under row-level security.** Try a `SECURITY DEFINER` function over the copy links, and a narrow policy read keyed on the repository, against the conformance tests that pin which tables carry which policy ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)). No migration so far uses a `SECURITY DEFINER` function, so this would be the first. If neither passes those tests cleanly, the count is kept as a maintained counter instead. The warning is decided either way; only the mechanism changes.
3. **The bulk effective-stat read at grid size.** Measured at the row and column counts of [RFC 0039](0039-bench-authoring-offline-and-extensibility.md)'s grid spike, formulas included. If one query per page is too slow, the read returns stored values and inherited sources only and a formula is evaluated by the client, or a `POST` form is added; either changes [§7](#7-a-bulk-effective-stat-read).

## Slices

| Id | What | Depends on | Touches |
| --- | --- | --- | --- |
| K1 | The copyable-table registry: the two sets, `_TABLES`, `_LINKS`, the purge, the conformance tests, the planner-step test | none | api |
| K2 | `POST /entities` with `kinds`, `PUT` and `DELETE` of a kind, the guarded `DELETE /entities/{id}`, updates carrying `kinds`, the round-trip matrix and the publish check | K1 for the matrix and the publish check; [RFC 0037](0037-releases-and-public-snapshots.md) R4 for the breaking-change row | api |
| K3 | `PUT /entities/{id}/parents` for any entry | none | api |
| K4 | New from parent and duplicate: client-side first, then `POST /entities/{id}/duplicate` | K2, K3 | hub, bench, api |
| K5 | `GET /entities` filters and `kinds`; name ordering for items and beings | none | api |
| K6 | `PATCH` for stat groups, stat definitions and enum values, rename-only; amends ADR 0143 | none | api, docs |
| K7 | The bulk effective-stat read | K5; spike 3 | api |
| K8 | Note reorder, picture payloads and the main picture, with a size cap | none | api |
| K9 | The library count and the delete warning in Studio, Bench and the CLI | K2; spike 2 | api, hub, bench, cli |
| K10 | Status update to RFC 0018: closed, superseded by this RFC | K4 | docs |

Each its own ADR when it lands. Order, not schedule: K2 and K3 come first so Bench can author beings and groups in draft repositories; K1 lands before anything is published with a new kind; K4 to K9 follow the editor; K8 is what Bench's picture slice ([RFC 0039](0039-bench-authoring-offline-and-extensibility.md) B8) waits for.

## Open questions

- **Carrying an enum rename to libraries.** An enum value's identity in the snapshot is its text, so a rename arrives as an addition and a refused removal, and a library's entries keep the old value. Giving enum values an identity in the snapshot fixes it and changes the snapshot format; whether that is worth it is for a later slice.
- **Who sees which entries.** `GET /entities` is open to every participant of a tenant and lists every entry name, with no visibility filter ([§5](#5-finding-entries) adds filters, not a gate). Whether a player should see entries a GM has not shared is outside this RFC and is raised here because it is now a filterable list.
- **Picture cap and count.** The starting cap is the profile-picture cap; whether an entry may hold any number of pictures, and what the cap should be for a repository's cover as against an entry, waits for real use.

## Not in scope

- **Arbitrary per-entry fields** (an entity-attribute-value store, or a JSON blob any entry may fill). Kinds have columns and rules; free fields would have neither.
- **Template tables** ([RFC 0018](0018-entity-template.md)), and any slot or sheet view ([§10](#10-rfc-0018-is-closed)).
- **Kinds an author defines as data.** A kind is a migration and a registry line.
- **Making an inventory item or a character through `kinds`.**
- **Places, clocks and calendars** ([RFC 0026](0026-world-model-axes-and-address.md), [RFC 0028](0028-time-causality-and-calendars.md)), beyond the cost named in [§11](#11-places-clocks-and-calendars).
- **Retyping a stat definition, moving it between groups, or deleting one in use.**
- **Document and number payload uploads, picture resizing, content sniffing, per-tenant byte quotas** ([RFC 0038](0038-public-repositories-and-discovery.md)), and pictures offline.
- **The release ledger and the breaking-change detector themselves** ([RFC 0037](0037-releases-and-public-snapshots.md)); this RFC adds one thing for the detector to report.
- **Which of these routes an Author may use.** Each new route sits behind the gate of the route it generalises; the capability matrix is [RFC 0040](0040-authors-and-invites.md)'s.

## Alternatives considered

- **`entity_template` tables** ([RFC 0018](0018-entity-template.md)). A template is a second way to say what a parent already says, adds tables the registry and the copy engine would have to carry, and answers a view question with storage. Closed in [§10](#10-rfc-0018-is-closed), open to a slot case.
- **Kinds an author defines as data** (a `kind` table with per-entry rows). The copy engine, the read policy, the views and the conformance tests all enumerate real tables, so an author-defined kind needs generic columns, which is a key-value store by another name. A kind also carries rules (a being can be a character, an item has inventory items) that code enforces. A marker table costs one migration and one registry line.
- **A generic entry with every field optional**, so any entry can be anything without kinds. It drops the constraints that make a copy safe (same-tenant keys, a character being a being), and every reader would have to ask which fields mean something.
- **A `kind` column on `entity`.** [ADR 0012](../adr/0012-entity-table.md) decided against a discriminator; a column would duplicate the marker rows and could disagree with them.
- **Naming the field `roles`.** Owner, Organizer and Author are roles; two meanings for one word is the confusion the glossary exists to avoid.
- **A registry that generates the planner and the diff.** The planner's re-targeting and the diff's field semantics differ for every table, so a generator would be a second copy engine. The registry lists, and the tests make an omission loud.
- **Blocking a delete that libraries hold.** It would let any library, by copying, take away the author's ability to remove a mistake. The author is told how many hold it and decides.
- **Letting kind changes travel quietly**, as `_IGNORED` does now. A library's entry would silently differ from its repository's, and a release would not say that an entry changed what it is.
- **A server-side duplicate before any client one.** What a person wants copied is not known until the dialog has been used; the first version is a sequence of routes that exist.

## Consequences

- An Author can make a being, a sentient sword, or a category node, give any of them parents, find them by name and kind, and put a picture on them, without a route per kind. A being can finally be deleted.
- A new kind costs a migration, a registry line, a planner step and a matrix row, and a test fails if one is missing; the hand-kept lists of tables become one.
- A kind added to a published entry is visible: a breaking change in a release, a "Kind added" row in a library's updates, and applied only where the library's copy allows it. This changes `repository_updates.py`'s `_IGNORED`, so existing update tests that assume kinds are skipped change with it.
- Publishing is gated by a list of proven kind combinations. A draft repository is not, so Bench can author freely and the engine is proven before anything leaves a draft.
- The API gains `POST /entities`, kind and parent routes, filters, a name ordering (a visible change to two lists), stat and enum `PATCH`, a bulk read, a note reorder, picture upload routes and a count read; one new setting (the picture cap), and possibly the first `SECURITY DEFINER` function. No new table for kinds themselves.
- Pictures are copied as rows, so a repository with many pictures is stored once per library that copies it; the quota is [RFC 0038](0038-public-repositories-and-discovery.md)'s to set.
- An enum rename is not clean for libraries until enum values have an identity; until then it is an addition and a removal they must resolve.
- [ADR 0143](../adr/0143-lorenzo-seed-taxonomy-and-stats.md) is amended by K6, [ADR 0103](../adr/0103-stat-tags-enum-values-and-mandatory-groups.md)'s deferred `PATCH` is built, and [RFC 0018](0018-entity-template.md) ends as closed.
