# 0214 - The release document

Status: accepted, decided with the maintainer on 2026-10-08. Slice R5 of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), tracked in #550. Built on what the spike R1 found (the RFC's "What was tried"): a `Content` serialised to a document and read back is the same field for field, and the update engine, the copy planner and the digest cannot tell it from the rows. Extends [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) and [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md); the open questions RFC 0037 left to this slice are decided here.

## Context

[RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §4 gives a release of a **public** repository a document: the repository's `Content` as it was, which every other tenant reads instead of the live rows. This slice builds the document and nothing that uses it: the format and the code that writes and reads it, the two tables, and the test that the document and the rows are interchangeable. The visibility column that says which repositories get a document is slice D1 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md), so nothing here is called by a publish; the functions are called directly, by the tests, and by the slices that follow (R6 reads, R7 retains, R8 flips).

`Content` is the one object the engines read ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [0121](0121-repository-updates-and-re-sync.md)), and its parts are plain data: dicts, lists, sets, tuples, `Decimal`, `bytes`, a few small dataclasses and the copy links of the tenant. R1 serialised all of it with nothing left out.

## Decision

### The format

A document is one JSON object, compressed with gzip, stored in `repository_release_document.content`. Every field of `Content` is a key of it, named as the field is:

- **Ids are strings**; a map keyed by an id is a JSON object, a map keyed by two (a stat value, a formula: entity and definition) is a list of `[entity, definition, value]`; a tuple is a list; a set is a sorted list; `Decimal` is its string, so its scale survives; `StatValueType` is its value.
- **A nested dataclass is an object keyed by its field names** (`StatValue`, `Formula`, `PayloadData`, `InformationData`), and `Links` is an object of its fields.
- **Order is the load's.** Lists and maps are written in the order `load_content` produced them and read back in it, so the `Content` read back is the one that was written, down to the order of every list. Nothing is sorted for the sake of equal bytes: the gzip header carries no time, so the same `Content` is the same bytes, but SQL does not promise the order of two loads of one table, and nothing relies on two releases of unchanged rows being the same bytes. The digest ([ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md)) is what says a release is unchanged.
- **A non-finite float is written as a string** (`"nan"`, `"inf"`, `"-inf"`), a finite one as a JSON number. The API accepts `NaN` and `Infinity` as the value of a float stat and the database stores them (found by R1), and standard JSON has no such number: refusing them would fail a release on a value the API let in, writing them as bare tokens would make a document most parsers cannot read. Whether the API should refuse them is a question of its own. `Decimal` values go as strings and so carry `NaN` already. The writer never emits a bare `NaN` token (it is run with `allow_nan` off, so a value it forgot is an error).
- **Files are not inlined.** A picture's or a document's bytes are in `repository_release_blob`, and the payload in the document holds their SHA-256 beside the file type and the name, which stay with the payload: two payloads with the same bytes may call them different types.

**The version.** The table has a `format` column, 1 now, and the reader looks the version up: a document is read by the code of its version, and a version nobody knows is an error that says so, never a guess. A change to `Content` or to the shape above makes a version 2 and keeps the reader of 1, since the rows a retained document came from have changed and it cannot be rebuilt. A golden file of version 1 in the tests is read on every run, so a change that would break reading it is caught.

**A field the format does not write is an error, not a silent loss.** The format is a table of codecs per dataclass, one entry for each field, and writing a `Content` whose class has a field with no entry raises `ContentFieldNotSerialisedError` naming it. So a release cannot be made from a `Content` that has outgrown the format, and a test that adds a field to a `Content` subclass sees it raise, as the table-list test of `repository_access` does for RLS.

### The blob table

`repository_release_blob(tenant_id, sha256, data)`, the key `(tenant_id, sha256)`: the bytes of a file once for each repository, however many releases and payloads use them. It does not carry the `file_type` RFC 0037's sketch gave it: the type belongs to the payload, which the document keeps, and a blob is the bytes alone. Writing a document inserts the blobs it refers to that are not there yet. Two repositories holding the same picture keep a copy each, as everything of a tenant's is its own.

### The document table

`repository_release_document(release_id, tenant_id, format, content, blobs, created_at)`:

- **The key is `release_id`**: one document for each release, with a same-tenant key to `repository_release (id, tenant_id)` ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)) that goes when the release does.
- **`blobs`** is the sorted list of the SHA-256 of every file the document refers to. Retention (R7) keeps a blob while a retained document lists it, and this is how it asks without opening documents.
- **Immutable.** A trigger refuses an `UPDATE` of a row of either table, for every role; a `DELETE` is allowed, since a release's document goes when retention removes it and everything goes with its repository ([ADR 0184](0184-deleting-a-tenant.md)). A second document for a release is refused.

Both tables are tenant tables of the repository: `tenant_isolation` and `FORCE ROW LEVEL SECURITY` ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)), and, because the libraries a repository is granted to will read its documents, `repository_read` as well, so both are in the first list of `repository_access` ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). The tests that every tenant table is classified, and that a granted library sees them only inside the gated read and never writes them, cover them.

### The code

- **`release_document.py`**, pure: `encode(content)` returns the document as plain JSON data and the files it refers to by SHA-256; `decode(document, files)` builds the `Content`; `dumps` and `loads` are the gzipped JSON; `FORMAT` is the current version and `READERS` the readers by version.
- **`release_document_store.py`**, with the session: `store_release_document(session, tenant_id, release_id, content)` writes the document and its files, and `read_release_content(session, tenant_id, release_id)` reads them back as a `Content`. The caller passes the `Content` it already loaded for the digest, so that the digest and the document of one release come from one load and cannot disagree. Like `load_content`, they filter on the repository's id explicitly: a member reads their own, a library reads inside `reading_repository`. They are not called from a publish.
- **Errors** are plain exceptions of this module (`ReleaseDocumentError` and its kinds), not HTTP problems: R6 decides what a reader of a missing document is told.

### What the tests pin

- The round trip of a `Content` with every field filled, strictly: the class of every container and scalar, the scale of a `Decimal`, the order of every list; and that of a repository written to the database and loaded.
- `plan_copy` and `compute_updates`, given the document where they read the repository, produce exactly what they produce from the rows, for a first copy of a bridge and its two repositories, and for an update after a change in every field the engine compares; the digest of the document is the digest of the rows.
- The same bytes in two releases are one row in the blob table.
- The golden file of version 1; an unknown version; a field the format does not write; a missing file; a second document for a release; the trigger; the tenant isolation and the gated read.

## Not in scope

- **The read switch.** `load_upstream` and the two engines, the manifest and the browse endpoints reading a document: R6. This slice swaps `load_content` in the tests only.
- **Writing a document at a publish**, and which repositories get one: the visibility column is [RFC 0038](0038-public-repositories-and-discovery.md)'s D1, and the first release of a public repository is R8's flip.
- **Retention, `current_release_id` and "make release current"**: R7. The tables allow deleting a document and a blob; nothing here does it.
- **Scale.** The size and time of a document at 1,000 to 20,000 entries is R2's; R1 measured four small repositories.
- **A cap on a document's size**, until R2 says what one should be.
- **Refusing non-finite floats in the API.**

## Consequences

- A release of a public repository can hold exactly what the repository was, in one row and a few blobs, and what reads it needs nothing but a `Content`.
- Every new field of `Content` needs a codec, a version if it changes what a document holds, and a golden file for it; forgetting is an error at the first release, and a test.
- Files are kept once, not once for each release. A repository with many large pictures grows the blob table by its distinct pictures, not by its releases.
- A document written under a format stays readable for as long as its reader is kept. The cost of that is the readers of every version; there is one.
- One migration adds the two tables, their policies and the triggers; nothing that exists changes.
