# RFC: Releases and public snapshots — what publishing a repository means

Status: accepted, decided with the maintainer on 2026-10-07: publishing becomes a *release* with a free-text label, notes and a breaking flag ([§1](#1-the-release-ledger)); release snapshots exist **only for public repositories**, and private repositories stay live-read with a LIVE banner and a digest ([§4](#4-the-release-document-for-public-repositories), [§5](#5-the-read-switch-retention-and-rollback)); and the wording rule ("Matches release 1.3", "Edited since 1.3", never "stable" or "frozen"). The digest and released rows ([§2](#2-the-digest-and-the-released-rows)), the breaking-change detector ([§3](#3-the-breaking-change-detector)) and the exact shape of the release document, the read switch and the flips ([§4](#4-the-release-document-for-public-repositories) to [§6](#6-flips-between-private-and-public)) are proposals for review, and §4 to §6 are gated on the spike in [Spikes](#spikes): if the release document cannot reproduce a repository's content exactly, they are redrawn before public discovery starts. Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. Serves the rows "Publish, subscribe, update screens" and "Authoring tool" of [v1.0](../../v1.0.md), and is the ground [RFC 0038](0038-public-repositories-and-discovery.md) (public repositories and discovery) stands on. It is one of the five topic RFCs under [RFC 0036](0036-repository-tooling.md).

Words: in the product a *library* is a tenant of kind `play` and a *repository* is a tenant of kind `repository`; the user-facing words (release, edited since, libraries using it, built on, Update) are those of ADR 0194. This RFC says *tenant*, *grant* and *subscription* where the schema and the API do.

## Context

### What publishing is today

Publishing a repository is a timestamp and a message. `PUT /tenants/{id}/published` (Owner only) sets `tenant.published_at` to now, records `repository.published` in the activity log, and writes one notification to the members of every granted tenant, in the request, with fixed text: "{name} is published" the first time, "{name} has published an update" with the body "Check its updates to see what changed." after that. `DELETE` returns the repository to draft. Nothing else is recorded: no label, no notes, no list of what changed, no history beyond the activity log, which only the repository's own members can read ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md), [ADR 0084](../adr/0084-activity-log-coverage-and-member-removal-notice.md)).

### What a subscriber reads is the live rows

Everything a library does with a repository before and after copying it reads the repository's rows as they are **now**, inside `reading_repository` ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)):

- `copy-plan` and `copy` go through `plan_copy`, which calls `load_content` once per step of the manifest ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md), [0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)). The manifest itself reads the repository's own `repository_copy` rows (what it is built on) live.
- `updates`, and applying them, go through `compute_updates`, which calls `load_content` for the repository and for the library and compares them with the base snapshot every copy link holds ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).
- Browsing (`GET .../repositories/{id}/entities` and `.../stat-groups`) queries the live tables directly.

[ADR 0183](../adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md) tried this on the four seed repositories and kept it: what `updates` shows is the repository's state now, not its state at the last publish, and "publishing is how an author says *look now*". So a repository's work in progress is visible to every library it is granted to from the moment the author saves it. The only signal a library has that anything happened is `published_at` against its own `synced_at`.

### What a re-publish can and cannot say

It can say "look now". It cannot say what changed, why, or whether the change will break a library that has built on it, and it cannot say that what a library will see is what the author meant to publish, since the live rows include whatever was half-edited a minute ago.

### What the engine compares, and what it never sees

The update engine compares the snapshot functions in `repository_content.py` and nothing else. An entity snapshot holds its name, kinds, whether it is in the public catalog, its slug, its prototypes (by origin id), its stat groups, its stat values and its formulas; a stat group snapshot its name, priority and mandatory flag; a stat definition snapshot its name, value type, group and enum value names. The `kinds` key is stored and then skipped by the diff (`_IGNORED = {"kinds"}`), a changed value type is shown and never applied (`_NOT_APPLICABLE`), and the parents a bridge added to its copies (attachments, [ADR 0172](../adr/0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md)) are compared as their own list.

What it never compares: `information` and `payload` (descriptions, notes, pictures, documents), containment, ownership, group members and knowledge. Those are copied once and not offered for update ([RFC 0024](0024-repositories.md) amendment A7, [ADR 0121](../adr/0121-repository-updates-and-re-sync.md)). A rewritten description is therefore invisible to the engine, and so to anything built on it.

### Why a timestamp cannot tell released from edited

[RFC 0024](0024-repositories.md) amendment A7 already replaced timestamps with snapshots for the diff, for reasons that apply to any "what changed since publish" built on `updated_at`, checked against the models:

- `entity_prototype`, `entity_stat_group` and `entity_slug` have no timestamp at all, and neither do the attachments.
- A stat value write (`entity_stats.py`) moves `entity_stat.updated_at` and does not touch the entity.
- A deletion leaves nothing to read: a removed prototype edge, a deleted stat value, a deleted entity.

A `max(updated_at)` at publish would therefore call a changed or removed row "released", the unsafe direction. The one place a timestamp is good enough is description text: editing a description bumps `payload.updated_at` (`description_payloads.write_description`), so "N descriptions edited since the release" can be counted, as a hint only.

### What this builds on

- **The snapshot functions are pure.** `entity_snapshot`, `stat_group_snapshot` and `stat_definition_snapshot` take a `Content` and name every id by its origin, so the same function describes a repository's row now, a copy link's base, and a library's copy. Hashing their output cannot disagree with what the engine compares, by construction.
- **`load_content` returns plain data.** One `Content` object holds everything a repository can hold, with the copy links of the tenant; the engines never touch the tables again once they have it.
- **Subscribers' links hold origin ids.** Each copy link records `source_id` and a base snapshot in origin ids. Anything that replaces the live read must keep those ids valid.

## Decision

### 1. The release ledger

A publish becomes a **release**. A new table `repository_release`, a tenant table of the repository:

| Column | Meaning |
| --- | --- |
| `id`, `tenant_id` | the release; the repository |
| `number` | 1, 2, 3 within the repository, assigned by the server |
| `label` | free text the author writes ("1.3", "Spring errata"), unique within the repository, **never parsed as a version**. Defaults to the number when omitted, so a caller that sends no body (today's CLI) still publishes |
| `notes` | free text, optional: what this release is, for people |
| `breaking` | the breaking flag: the author's statement, forced on by an acknowledged detector hit ([§3](#3-the-breaking-change-detector)) |
| counts | rows added, changed and removed per kind, attachments added and removed, and the description-edit hint of [§2](#2-the-digest-and-the-released-rows) |
| `digest` | one hash over the release's row hashes ([§2](#2-the-digest-and-the-released-rows)); kept for every release |
| `created_by`, `created_at` | who and when |

What changes around it:

- **`PUT /tenants/{id}/published`** takes `{label?, notes?, breaking?, acknowledge_breaking?}`, makes the release and sets `published_at`. Owner only, as today.
- **`GET /tenants/{id}/releases`** lists them, newest first, readable by the repository's members and, through the gated read, by every tenant granted the repository.
- **The notification carries the release.** Title "{name} published release {label}", body the notes (cut at a length the slice chooses) and a line when the release is breaking, replacing "Check its updates to see what changed." The first publish keeps its own wording. The fan-out stays in the request here; making it asynchronous is a pre-launch gate of [RFC 0038](0038-public-repositories-and-discovery.md).
- **`synced_release_id` on `repository_copy`** records the repository's release that was current when the library last copied or applied updates, so the Libraries-using-it view can say "on release 1.2" and the library's own view "Last updated from release 1.2". It is set where `synced_at` is set. A copy made before the ledger has none. It never says "up to date"; that is only said when the library's update list is empty.
- **The activity log** records the label with `repository.published`.

**The wording rule.** What the interface says about a release is what was checked, in these words and no stronger:

- "**Matches release 1.3**": the repository's compared rows hash to the release's digest.
- "**Edited since 1.3**": they do not, with the number of rows that differ.
- Never "stable", "frozen", "final" or "released" as a promise about the content.
- Beside either, in words: **text edits are not tracked.** Descriptions, notes and pictures are copied once and updates do not carry them ([Context](#what-the-engine-compares-and-what-it-never-sees)). The description-edit hint ("12 descriptions edited since 1.3") is shown to the author in the composer and the LIVE banner as a hint, with the caveat that a hard delete leaves no trace.

A release on a **private** repository is a ledger entry and a marker: libraries still read the live rows ([§5](#5-the-read-switch-retention-and-rollback)), and the interface says so with the **LIVE** banner wherever such a repository is edited ("Libraries using it see your edits now", with their number). A release on a **public** repository is also what is read.

### 2. The digest and the released rows

At every publish, in the publish transaction, the server loads the repository's content once (the cost class of one `updates` call) and, with the **same snapshot functions the diff uses**, hashes:

- every entity, stat group and stat definition: SHA-256 of the canonical JSON (sorted keys, no whitespace) of `entity_snapshot`, `stat_group_snapshot` or `stat_definition_snapshot`, named by origin id;
- every attachment (the repository's own additions to its copies), as one hash per pair of origin ids.

The hashes are stored in `repository_released_row(tenant_id, kind, row_id, hash)`, with `row_id` the row's origin id (the id a library's link holds), **overwritten at each publish**: one set of rows, not one per release. Beside the hash each row keeps a few facts the detector needs and a person needs to read a change list: the row's name and, per kind, an entity's kinds, a definition's value type and enum values. An attachment's key is its pair of origin ids; the exact column shape is the slice's. `repository_release.digest` is a hash over the sorted row hashes, so a release's identity survives the rows being overwritten.

**Released and edited.** A row is *released* when its hash now equals its stored hash, and *edited since* otherwise. The rule is uniform: absent on both sides counts as equal, so a row that was removed and whose removal was published is released, and one removed after the release is edited. A row with no stored hash (new since) is edited.

- **`GET .../repositories/{id}/updates`** gains, additively, the current release (`id`, `label`, `created_at`) and a `state` on every changed, added and removed row and attachment: `released` or `edited`. For a repository published before the ledger existed there is no stored hash; its rows carry no state (null) and everything behaves as today until the next publish.
- **"Apply all clean" applies only released rows.** The client convenience is defined once: a clean, released row that is not breaking. Rows edited since the release are applied one at a time, by choice. **Attachments and breaking rows are never part of "all"**: attachments are already named one by one in `POST .../updates`, and the API refuses (`409 update-needs-confirmation`, in the manner of `update-needs-choices`) an action on a row any release since the library's `synced_release_id` lists as breaking unless the action says it confirms.
- **For a public repository every row a library sees is released by construction**, since it reads the release document ([§4](#4-the-release-document-for-public-repositories)); the marking matters on private repositories and to the author of either.
- **What it does not say.** "Released" means "equal to what the engine saw at publish". A row edited since cannot show its released value, and a text edit is invisible ([Context](#what-the-engine-compares-and-what-it-never-sees)).

The author's side, which [RFC 0036](0036-repository-tooling.md) builds in Studio: the guarded publish dialog and the release composer list what will go out (counts by kind, the names of removed rows, the detector's hits, the description-edit hint) from a comparison of the live content with the stored rows, so a publish shows its own changelog before it is made.

The table is a tenant table: `tenant_id`, same-tenant keys ([ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md)) where it points at another tenant table, and RLS with `FORCE ROW LEVEL SECURITY` ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)). Libraries read it through the gated read for the marking, so it, `repository_release` and the tables of [§4](#4-the-release-document-for-public-repositories) carry the `repository_read` policy and go in the first list of `repository_access` (ADR 0118); the test that fails when a tenant table is in neither list covers them.

### 3. The breaking-change detector

At publish, the live rows are compared with the stored rows (the previous release's), and these are **breaking**, because the update engine cannot carry them to a library that already copied the repository, or carries them in a way that leaves the library's content different from a fresh copy's:

- **A removed entity.** A library sees a *removed upstream* row and can only keep its copy detached.
- **A removed or retyped stat definition**, or a removed stat group. A retype is shown and never applied (`_NOT_APPLICABLE`), so existing libraries keep the old type and new copies get the new one; a removal leaves the library's formulas and values pointing at a definition upstream no longer has.
- **A removed enum value.** Stat values in a library may still hold it.
- **An attachment added onto an existing item.** By design it changes what the item resolves to in every library that holds it ([RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md) §3: one Longsword that gains a price and dice), so it is a decision for the library, not a routine change.
- **A kind change.** `kinds` is stored and ignored by updates, so existing copies silently keep the old kinds while new copies get the new ones.

**Acknowledgement is mandatory.** `PUT /published` answers `409 release-has-breaking-changes`, listing the rows and the reason for each, unless the request carries `acknowledge_breaking: true`; an acknowledged release has `breaking` set and the list is kept on the release (`breaking_rows`: kind, row id, name, reason), so a library several releases behind sees the union of what it skipped. The first release has nothing to compare with and has no hits. Authors may set `breaking` on a release the detector found nothing in; the detector is a floor, not a ceiling.

**What the detector cannot see.** Text, containment, ownership and anything else the engine does not compare ([Context](#what-the-engine-compares-and-what-it-never-sees)); a changed slug is compared by the engine and is not listed here (see [Open questions](#open-questions)). The composer says so in the same words as the wording rule.

### 4. The release document for public repositories

For a **public** repository ([RFC 0038](0038-public-repositories-and-discovery.md)) a release also stores the repository's content as it was, and every other tenant reads that instead of the live rows.

- **What it is.** A serialised copy of the in-memory `Content` that `load_content` returns, written in the same transaction and from the **same load** as the digest of [§2](#2-the-digest-and-the-released-rows), so digest and document cannot disagree. Every field of `Content` is in it (entities, kinds, slugs, prototypes, stat groups and definitions, enum values, stat values, formulas, containment, ownership, group members, information, payloads, knowledge, and the tenant's copy links with their snapshots, the set of repositories it has copied, and its attachment records), and **every row id is the repository's own id, unchanged**. The engines take a `Content`; they cannot tell a document from a live read.
- **Stored** as `repository_release_document(release_id, tenant_id, format, content)`, gzipped JSON, one row per release, with a format version so a document written before a change to `Content` can still be read. A test fails when `Content` gains a field the serialiser does not write, as the table-list test does for RLS.
- **Immutable.** A trigger refuses an update to a document row. It goes only when retention removes it ([§5](#5-the-read-switch-retention-and-rollback)) or its repository is deleted.
- **Pictures once.** Picture and document bytes (they live in Postgres, [ADR 0017](../adr/0017-information-and-payloads.md)) are not inlined: the document refers to them by SHA-256 and `repository_release_blob(tenant_id, sha256, file_type, data)` holds each once, however many releases use it. Retention drops a blob when no retained document refers to it.
- **Read through one function.** `load_content` stays what it is. A single `load_upstream(session, repository_id)` returns a `Content` for another tenant's read: the live one for a private repository, the current release's document for a public one. It replaces the `load_content` calls at the two upstream sites (`plan_copy`, `compute_updates`), it is what the manifest's read of "what this repository is built on" uses (today `_dependencies` queries `repository_copy` directly; a document carries the same set in `links.copies`), and the two browse endpoints are rewritten over its result (name, kinds and prototypes from `Content`, `q` as a case-insensitive filter, paging in memory as `GET /repositories` already does).
- **Access is unchanged.** The new tables carry the same `repository_read` policy: readable only inside `reading_repository`, by a tenant with a grant to a published repository. Who may *become* such a tenant for a public repository, and what may be seen before that, is [RFC 0038](0038-public-repositories-and-discovery.md); this RFC changes what is read, not who may read.

**Why a document and not a cloned tenant.** The obvious design is to copy the repository into a hidden tenant at each release and point grants at it. It fails on identity. `entity.id` is a global primary key (`UuidPk`, with `UNIQUE (id, tenant_id)` only to support the same-tenant keys of ADR 0117), so a clone in another tenant cannot keep the ids; and every library's copy link holds the repository's own ids as `source_id` and in its base snapshot. A clone would orphan each library's three-way diff at every release unless a clone-to-live id map were applied at every read site. It would also need a new tenant kind (`kind` is immutable by trigger), the whole copy machinery run at publish, and a new gated-read rule across the 33 content tables. A document keeps the ids, adds four tables, and changes the read at the places listed above.

**Why not only hashes.** A hash tells the engine a row changed, not what it was. A library reading a public repository needs the rows themselves as they were at the release, not as the author has since edited them.

### 5. The read switch, retention and rollback

- **The rule.** A tenant that reads a repository for copy, copy-plan, browse or updates reads the repository's **current release document** if the repository is public, and the live rows if it is private. A public repository has no current release until its first one, and a repository cannot be public without one ([§6](#6-flips-between-private-and-public)).
- **Private repositories stay live-read.** Decided with the maintainer: the LIVE banner and the digest are the whole mechanism for them. The people who read them are those the owner invited, who can be asked.
- **The current release** is `current_release_id` on the repository (a same-tenant key to `repository_release`). Publishing makes the new release current.
- **Retention.** The documents of the **last five releases** are kept (the number is a setting, not a promise); every release keeps its ledger row, its counts, its `digest` and its `breaking_rows` for good. Blobs are kept while a retained document refers to them. The row hashes of [§2](#2-the-digest-and-the-released-rows) are one set, the latest.
- **"Make release current" is the rollback.** `PUT /tenants/{id}/releases/{release_id}/current` (Owner) points `current_release_id` at a retained release. In the same transaction the released rows are recomputed from that release's document, with the same functions, so "Edited since" always compares the live content with the release that is current. The detector of [§3](#3-the-breaking-change-detector) runs between the release that was current and the one chosen, and acknowledgement is required for the same reasons. Libraries that already updated to the newer release see the older state as changes on their next check, which is correct: their base snapshot is the newer one. Libraries are notified as for a publish, with the label.
- **What an author sees.** For a public repository the banner says edits are not visible to anyone until the next release, and shows how many rows differ from the current one and the description-edit hint; for a private one it is the LIVE banner.

### 6. Flips between private and public

The visibility column and the flip endpoints are [RFC 0038](0038-public-repositories-and-discovery.md)'s; what must hold when they are used is this RFC's.

- **Private to public is atomic with the first release.** One transaction sets the visibility, makes a release and its document, and makes it current. There is no public repository without a release.
- **It requires every repository it is built on to be public.** A copy of a public repository invites the copying library, and a manifest needs a grant and a published step for each repository in it (grants are not transitive, [ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)); a private upstream would leave the copying library unable to copy its dependencies. The Studio dialog offers to publish the upstreams the person owns, and otherwise names who to ask.
- **Libraries that already read it live** keep their links. Their next update check reads the release, so edits made since the first release quietly leave their inbox; they are told once.
- **Public to private** revokes the grants whose source is a public copy (the `source` column of RFC 0038) after a warning with their number, and **their copies stay**, as for any revoke today. Grants the owner made by invitation stay and read live again. The documents are kept under retention and nothing reads them while the repository is private.
- **A release is gated on what the repository is built on.** A public repository built on others can publish a release only while its own copy of each of them is at that repository's current release (its `synced_release_id` equals their `current_release_id`); otherwise `409 built-on-behind` names which. This is the bridge-skew gate: a library copying a bridge that was authored against an older or newer upstream would get rows ADR 0120 drops and reports. For a private repository the composer shows the same finding as a warning.

## Spikes

Run on throwaway branches; what they find is written back into this RFC, in a "What was tried" section, as RFC 0033 did.

**R1, release round-trip (hard gate for public discovery).** Serialise the `Content` of the four seed repositories (core, equipment, D&D rules, the bridge with its attachments), of a bridge built on two repositories that share a dependency, and of one with pictures and documents, into the document of [§4](#4-the-release-document-for-public-repositories) and read it back. It passes when:

- the read-back `Content` equals the original field for field (UUIDs, `Decimal`s, bytes, sets, tuples, the `defaultdict`s);
- `plan_copy` and `compute_updates` fed the document produce exactly what they produce from the live rows, for a first copy, for an update with changes in every compared field, for attachments, and for a bridge;
- the digest computed from the document equals the one computed from the live load;
- the picture bytes are stored once across two releases.

It also records the document's size, plain and gzipped. A failure the serialiser can fix is fixed. One it cannot (something in `Content` that the engines read and a document cannot carry) changes the design: [§4](#4-the-release-document-for-public-repositories) to [§6](#6-flips-between-private-and-public) are redrawn, the candidates being a cloned release tenant with an id map (rejected above for its cost, reopened only by this result) or public repositories read live with the digest alone, and public discovery waits for the redrawn design.

**R2, scale.** Build repositories of 1,000, 5,000 and 20,000 entities with realistic stats, prototypes and attachments, and measure `copy-plan`, `updates` (first and repeated), the digest at publish, building and reading a document, the live digest of [§1](#1-the-release-ledger) ("Matches release 1.3" needs one), and memory. The results decide, and nothing else in this RFC depends on them: whether the digest and document stay in the publish request or the release is built in a "building" state; whether "Matches" is computed on demand or cached; whether a release read is cached per release id (the document is immutable, so it can be); whether browse needs a SQL path; and whether a per-library "updates available" summary is cheap enough to offer. A result that makes `updates` on a document unacceptable at 20,000 entities is a reason to cache, not to change the design.

## Slices

| Slice | What | Depends on | Touches |
| --- | --- | --- | --- |
| **R1** | Spike: release round-trip ([Spikes](#spikes)); findings written back here | none | api (throwaway branch), docs |
| **R2** | Spike: scale ([Spikes](#spikes)); findings written back here | none | api (throwaway branch), docs |
| **R3** | Ledger-lite: `repository_release`, `PUT /published {label, notes, breaking}`, `GET /releases`, the notification text, `synced_release_id`, `lorenzo repo publish --label/--notes` | none | api, cli |
| **R4** | Digest and `repository_released_row`, released and edited on `/updates`, "apply all clean" rule, the breaking-change detector with `acknowledge_breaking` and `update-needs-confirmation`, the description-edit hint | R3; R2's findings | api, cli |
| **R5** | The serialiser and the immutable release document, the blob table, the `Content` test | R1 passed; R3, R4 | api |
| **R6** | The read switch for public repositories: `load_upstream` in `plan_copy`, `compute_updates`, the manifest and browse | R5; RFC 0038 D1 (the visibility column) | api |
| **R7** | Retention, `current_release_id` and "make release current" with its detector run | R6 | api |
| **R8** | Flip rules (atomic first release, built-on repositories public, public-to-private revocation) and the bridge-skew gate | R5 to R7; RFC 0038 D1 | api |

The screens that use these are in [RFC 0036](0036-repository-tooling.md): the guarded publish dialog and release composer in Studio, the marking in the Shelf's update inbox, and the visibility switch (T3, T4, S4, T7 there). RFC 0038's flips (D5) need R5 to R8. Migrations and the regeneration of `openapi.json` and `schema.d.ts` are serial across slices.

## Open questions

- **A changed slug.** The engine compares slugs and applies a change, but `[[slug]]` references in text that was copied once are not rewritten, so a renamed slug can break a library's links without any row saying so. Whether it is listed by the detector (proposed: yes) is slice R4's to decide.
- **Label rules.** Unique within a repository is proposed; whether the comparison ignores case, and whether a label may be changed after the release (the notes and label are the author's words, the digest is not), is slice R3's.
- **The number of retained documents.** Five is proposed; R2's results on size may move it.
- **Computing "Matches".** Hashing the live content costs one load; whether Studio asks on each visit, on demand, or reads a cached value invalidated by writes is R2's result.
- **One checkbox or one per row** for the breaking acknowledgement. One, listing the rows, is proposed; the API takes one flag either way.
- **How long a "building" release may take** if R2 shows publish cannot stay in the request, and what libraries see meanwhile (proposed: the previous release stays current until the new one is complete).
- **A release made current again after a library updated to a newer one.** The library sees the older state as changes; whether the interface should call that a rollback is for the Shelf's inbox (RFC 0036 S4) to word.

## Not in scope

- **Snapshots of private repositories.** Decided: they stay live-read.
- **A library pinning itself to a release.** A library reads the current release of a public repository; staying on 1.2 while the author is on 1.4 is not offered.
- **SemVer, version ranges and constraint solving.** Labels are free text.
- **Comparing or carrying text.** A diff of descriptions, notes and pictures, and updates that bring them, are a later question; this RFC only says in words that they are not tracked.
- **Auto-applying an update**, ever.
- **Who may see or copy a public repository**, the visibility and source columns, discovery, the publish cooldown, quotas and takedowns: [RFC 0038](0038-public-repositories-and-discovery.md).
- **The release composer and publish dialog as screens**: [RFC 0036](0036-repository-tooling.md). This RFC defines what they say and what the API answers.
- **Partial copy**, and carrying a library's edits back to a repository.

## Alternatives considered

- **A draft flag on entities.** Hides only new rows. Rebalancing thirty published weapons is thirty *edits*, and an edit needs two versions of one row, which is a snapshot; stat definitions, groups, prototype edges and attachments are not entities at all. It would also be a second visibility model across the 33 read policies.
- **A staging repository, filled by copy.** The author works in a second repository that copies the live one. A bridge carries only what it authored, and its edits to its copies of a dependency do not travel except an added parent ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md), [0172](../adr/0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md)), and text is copied once and never updated, so promoting staging to live cannot carry an edit.
- **A cloned release tenant.** Argued in [§4](#4-the-release-document-for-public-repositories): `entity.id` is a global key, so ids cannot be preserved and every library's links would orphan.
- **Event-sourced versions**, recording every write to the repository and replaying to any point. Every write route would have to emit events, deletes and cascades across the content tables would have to be modelled, and the read path would still need a materialised state per version for a library to use. It keeps a history nobody asked for: only releases matter.
- **`max(updated_at)` as the released marker.** Unsound, as in [Context](#why-a-timestamp-cannot-tell-released-from-edited), and wrong in the unsafe direction.
- **Storing whole snapshots per row instead of hashes.** Larger by orders of magnitude and unnecessary: the engine needs equality, and a library's own base snapshots already hold the content it copied. The few facts the detector needs are kept beside the hash.
- **Snapshots for every repository.** Cost and storage for repositories whose readers are people the owner invited and can talk to; the LIVE banner states the contract honestly. Decided with the maintainer.

## Decided with the maintainer (2026-10-07)

- **Release snapshots only for public repositories.** Private repositories stay live-read, with a LIVE banner.
- **Release labels are free text, plus a breaking flag.** No SemVer.
- **A release says "Matches release X" or "Edited since release X"**, never "stable" or "frozen", and says in words that text edits are not tracked.
- **Public discovery is in v1.0**, so the release document is on the path to it; the round-trip spike gates it.
- **API stability is not a constraint** while the project is in early development, so `PUT /published` takes a body and `/updates` and the notifications change shape where this RFC needs them to.
- **Spikes run on throwaway branches**, with their findings written back into the RFC.

## Consequences

- A publish says something: a label, notes, what changed, whether it breaks, and who is on which release. A library can tell a change the author announced from one made since.
- A breaking change cannot be published by accident; the author sees it listed and says so.
- A public repository gives its libraries a stable read: edits do not reach anyone until the next release, and a bad release can be rolled back to a retained one.
- A private repository is exactly as before in what libraries read, and is now honest about it. Its libraries have a marker, not a guarantee.
- **Publish becomes heavier.** It loads the whole repository once (the cost of one `updates` call), writes hashes, and for a public repository a document; R2 measures it.
- **Every new field on `Content` needs the serialiser and a document format version**, and the test says so. Retained documents are upgraded on read, not rebuilt, since the live rows they came from have changed.
- **There are two read paths** (live and document) behind one function. The regression surface is the engines' tests run against both.
- **"Apply all clean" changes meaning** for clients that apply in bulk: it applies only released rows, and never attachments or breaking rows. The CLI's `repo updates --apply` and the hub are meant to follow the same rule, which each slice that touches them states.
- **Tables:** `repository_release`, `repository_released_row`, `repository_release_document` and `repository_release_blob` are tenant tables with RLS, same-tenant keys, and a place in `repository_access`; `repository_copy` gains `synced_release_id`; the repository gains `current_release_id`. The API changes are additive except the publish body and the notification text.
- An author who finds a typo in a public repository must publish a release to fix it for others. That is the price of a stable read.
