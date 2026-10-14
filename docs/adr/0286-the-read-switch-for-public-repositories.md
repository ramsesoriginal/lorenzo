# 0286 - The read switch for public repositories

Status: accepted, decided with the maintainer on 2026-10-14. Slice R6 of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), tracked in #701. Builds on [ADR 0214](0214-the-release-document.md) (the release document, which nothing read yet) and [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) (the `visibility` column, which nothing could set to `public` yet). Extends [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md).

## Context

A library reads another tenant's repository in four places: the copy planner and the update engine call `load_content` for it ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [0121](0121-repository-updates-and-re-sync.md)), the manifest asks which repositories it has copied (`_dependencies`, [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)), and the two browse routes query its tables. All four read the rows as they are now. [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §4 and §5 say that for a **public** repository they read its current release's document instead, so that what its author edits is seen by nobody until the next release, and that a private repository stays live-read, with the LIVE banner and the digest as its whole mechanism.

The document and the column both exist and are not used. This slice makes the switch between them, in one place.

## Decision

### One function

`repository_upstream.load_upstream(session, repository_id)` returns an `Upstream(content, release, public)`: for a private repository its `load_content` and its newest release, for a public one the `Content` of the current release's document ([ADR 0214](0214-the-release-document.md)) and that release. It runs inside `reading_repository`, which is where a library may see the rows, the profile and the documents. `plan_copy` and `compute_updates` call it where they called `load_content` for the repository; the library's own content is still `load_content`, since its rows are its own. The engines take a `Content` and cannot tell which they were given, which [ADR 0214](0214-the-release-document.md)'s tests pin.

The copy records, as the release it took, the release it read (`Upstream.release`), and the update check compares with it. That is the one the library was shown.

Which repositories are public is the profile's `visibility`, read in the same gated read (`is_public`); a repository without a profile row is private.

### The current release

`repository_releases.current_release` is what a library reads. Until a release can be made current again ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §5, slice R7) it is the newest release, and it is asked for by this name so that R7 changes it in one place and the callers do not move. The author's own side (the preview and the publish compare with the *latest* release) keeps `latest_release`.

### A public repository with nothing to read

A public repository whose current release has no document, or that has no release, is answered `409 public-repository-has-no-release`. It is not read live instead: that would show every library edits no release has announced, which is the one thing the switch is for. RFC 0037 §6 says no repository is public without a release, and the flip that makes it so (R8) is atomic with the first release; this error is for a repository that a manual change or a bug has left in a state nothing should leave it in, and for the time before R8, when `public` can only be set in the database.

### Publishing writes the document

A publish of a public repository stores its document in the transaction that makes the release, from the same load as the digest ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §4), so the two cannot disagree: `assess` keeps the `Content` it loaded, and `store_release_document` takes it. A private repository's publish writes none. A repository that is made public after releases it made as a private one has no document for them and is not readable until it releases again; R8's flip makes the first release as part of the same transaction.

### The manifest

`_dependencies` reads `upstream_copies`: for a private repository its copy records now, for a public one what its current release's document says it had copied (`links.copies`, read from the document without the rest of it or its files). A public bridge is therefore built on what it was built on when it was released, the same as everything else a library reads of it. The manifest, the plan and the copy of a public repository are all made against that one state.

### Browsing

`GET .../repositories/{id}/entities` and `.../stat-groups` of a public repository are answered from the `Content`: `entity_rows` and `stat_group_rows` give the entries and groups, and the entries are paged in memory, as `GET /repositories` already is. A private repository keeps its queries; reading the whole content to show a page would cost it more than it costs now, and its readers are the people its owner invited.

What a reader may notice between the two:

- The order is by name and then id, as before, but compared as text by code point where the database compares by its collation, so two names that differ in case or accents may swap places.
- `q` is a case-insensitive part of the name. The live route passes it to `ILIKE`, so a `%` or `_` in it is a wildcard there and a plain character here.
- A document is read with its files, which a browse does not need. At the sizes of today that is a few kilobytes of JSON and a few files; the cost at scale is R2's question and a browse that reads no files can be made from the same document.

### What does not change

Who may read a repository: a library needs a grant to a published repository, public or not (the gated read is untouched, and a library with no grant gets the 404 it got). The profile, its cover and the releases list are read live, as they are edited and as the ledger says; the *content* is what a release freezes. `public` is still refused by the API ([ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md)), so nothing in a deployment is public yet, and the tests make a repository public in the database.

## What the tests pin

- A publish of a public repository writes a document for that release, and one of a private repository writes none.
- Browsing, the plan for a copy, the copy and the updates of a public repository show its release and not what its author edited since, and show the edit after the next release; the same repository made private again shows its rows.
- The browse of a document answers exactly as the browse of the rows, for a name filter, paging and the stat groups.
- The manifest of a public bridge is what its release was built on, whatever its copy records say now, and the stack copies from its documents.
- A public repository with no release, or whose release has no document, is `409 public-repository-has-no-release` in every read, and reads once it releases.
- A library with no grant reads nothing of a public repository.
- The equivalence tests of [ADR 0214](0214-the-release-document.md) (`plan_copy`, `compute_updates` and the digest from a document equal those from the rows) run through the real switch, where they patched the engines before.

## Not in scope

- **Who may read a public repository**: a library with no grant, the routes that need none, and a copy that subscribes the library: slice D2 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md).
- **`current_release_id`, retention and making a release current again**: R7.
- **The flip rules**, the first release made with the visibility and the dependencies that must be public: R8.
- **The scale of a document**, and a browse that reads none of its files: R2.

## Consequences

- A library that copies a public repository, or checks it for updates, sees the state its author released, and what the author does between releases reaches nobody.
- A private repository is read exactly as before.
- Everything that reads another tenant's repository goes through `load_upstream` or `upstream_copies`; a new read of a repository's content for a library uses them, or a public repository's edits leak.
- No migration, no new route and no change to a response: the one new answer is the `409` for a state nothing reaches yet.
