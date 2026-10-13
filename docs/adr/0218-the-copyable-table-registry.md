# 0218 - The copyable-table registry

Status: accepted, decided with the maintainer on 2026-10-08. Slice K1 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md), tracked in #554. Builds on [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (the two sets of tables), [ADR 0119](0119-copying-a-repository-into-a-tenant.md) (what a copy writes) and [ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md); needed before a new kind is published, and by the release serialiser and Bench's bulk export, which enumerate content through it.

## Context

A table that holds tenant data is named in several places by hand: `REPOSITORY_CONTENT_TABLES` and `REPOSITORY_EXCLUDED_TABLES` in `repository_access.py`, `_TABLES` and `_LINKS` in `repository_copying.py`, the list of link models `forget_copy` drops, and the counts a purge reports. Two tests fail if a tenant table is in neither set of `repository_access` or has the wrong policy; nothing fails if a table is in the sets and a copy never writes it, or if the planner writes rows for a table `write_rows` does not know, which `write_rows` then skips without a word. Each new table, and each RFC that adds a marker table, repeats the edit, and a miss is silent ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §1).

## Decision

### One module

`lorenzo_api/copyable_tables.py` lists every tenant table once, as `REGISTRY`, in the order a copy inserts its rows. Each line is a `CopyableTable`:

| Field | Meaning |
| --- | --- |
| `name`, `model` | the table and its model; a test holds `model.__tablename__` to `name` |
| `content` | a repository can hold it, so a library reads it through the gated read and it carries the `repository_read` policy; false for what belongs to a play tenant, a campaign or administration, and for the copying tenant's own bookkeeping |
| `copy` | what a copy does with its rows: `rows` (the planner writes them under the table's name, `write_rows` inserts them in registry order), `link` (a copy link, written after every `rows` table), `attachment_link` (written by `write_attachments`) or `none` (never copied: what a repository publishes, and every excluded table) |
| `carried_by` | for a `rows` table with no planner step of its own, the registered table whose step writes its rows: a `payload_description` rides with its `payload`, an `item` marker with its `entity` |
| `link_of` | a `link` table's kind of row (`entity`, `stat_group`, `stat_definition`), from which the planner key (`link_entity`) and the column holding the copy's id (`entity_id`) follow |
| `counted_on_purge` | a purge reports the tenant's own rows of this table that go with the copy |

What comes from it: `REPOSITORY_CONTENT_TABLES` and `REPOSITORY_EXCLUDED_TABLES` (the names stay in `repository_access`, derived), `_TABLES` and `_LINKS` of `repository_copying` (`COPIED_TABLES`, `COPY_LINKS`), the link models `forget_copy` deletes (`LINK_MODELS`), and the keys a purge may report (`PURGE_COUNTED`, the flagged tables and `attachment`, a prototype edge counted apart). **Nothing a copy, an update or a purge does changes**: the lists have the same members in the same order, and the full test suite is the proof.

### Thin on purpose

The registry **lists; it does not generate.** Which ids a copy re-targets, what collides, which fields the update diff shows or applies, and the queries a purge counts with stay hand-written, since they differ for every table and a generator would be a second copy engine. A purge asserts that the keys it counted are exactly `PURGE_COUNTED`, so a table flagged without a count, or a count for a table not flagged, fails every purge test.

### The tests

`tests/test_copyable_tables.py`:

- **Every tenant table is in the registry**, and every line is a tenant table, read from the database (a `tenant_id` column and row-level security).
- **Every content table has the `repository_read` policy and no other has**; the older test of the same name in `test_repository_read_rls.py` stays, over the derived sets.
- **A copy has a step for every copied table.** A copy of a repository with a row in every table (`seed_every_content_table`) is planned, and what the planner wrote is held to the registry both ways: a copied table it wrote nothing for has no step (or the seed lacks a row for it, which the new table's author adds), and rows for a table the registry does not copy would have been left out without an error. `carried_by` is held to name a copied table.
- **A copy inserts after what it points to.** A foreign key between two copied tables must point backwards in registry order.
- The registry lists each table once, with its own model, and a field means something only on the tables it belongs to.

The test that every foreign key between two tenant tables includes `tenant_id` ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)) already reads every constraint from the database, so it stays where it is.

### What a new table costs

A migration and a model, as before, and **one line in the registry** in place of an edit to the two sets, the two copy lists and the purge: a table missing from it fails a test, and a table that says it is copied without a planner step to write it fails another. `AGENTS.md` says so in place of "one of `repository_access`'s two lists".

## Not in scope

- The marker kinds (`item`, `being`...) as registry data, and the branches of the planner that write them: K2 adds a kind's registry line and its matrix row.
- The release serialiser and Bench's bulk export, which will enumerate content through the registry ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) R5, [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) W3).
- `load_content`, `load_links` and the diff's field tables (`_SETS`, `_KEYED`): hand-written, per the RFC.
- Tables that are not tenant tables (`app_user`, `tenant`, `repository_subscription`, `information_type`, the profile pictures of users).

## Consequences

- A tenant table is classified, ordered and given its copy role in one place, and a miss fails a test with the name of the table.
- A migration in another branch that adds a tenant table and edits `repository_access`'s lists will conflict: its lines move to the registry.
- No API change, no migration, no change to what a copy, an update or a purge does.
