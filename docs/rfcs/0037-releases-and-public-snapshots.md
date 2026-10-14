# RFC: Releases and public snapshots — what publishing a repository means

Status: accepted, decided with the maintainer on 2026-10-07: publishing becomes a *release* with a free-text label, notes and a breaking flag ([§1](#1-the-release-ledger)); release snapshots exist **only for public repositories**, and private repositories stay live-read with a LIVE banner and a digest ([§4](#4-the-release-document-for-public-repositories), [§5](#5-the-read-switch-retention-and-rollback)); and the wording rule ("Matches release 1.3", "Edited since 1.3", never "stable" or "frozen"). The digest and released rows ([§2](#2-the-digest-and-the-released-rows)), the breaking-change detector ([§3](#3-the-breaking-change-detector)) and the exact shape of the release document, the read switch and the flips ([§4](#4-the-release-document-for-public-repositories) to [§6](#6-flips-between-private-and-public)) are proposals for review. §4 to §6 were gated on the spike R1 in [Spikes](#spikes), which passed ([What was tried](#what-was-tried)): the release document reproduces a repository's content exactly, so they stand as drawn. The scale spike R2 ran too ([R2, scale](#r2-scale)): they hold at 20,000 entries, and it settled the open questions on retention, "Matches" and a "building" release. Built in the slices in [Slices](#slices), each recorded as its own ADR when it lands. Serves the rows "Publish, subscribe, update screens" and "Authoring tool" of [v1.0](../../v1.0.md), and is the ground [RFC 0038](0038-public-repositories-and-discovery.md) (public repositories and discovery) stands on. It is one of the five topic RFCs under [RFC 0036](0036-repository-tooling.md).

Words: in the product a *library* is a tenant of kind `play` and a *repository* is a tenant of kind `repository`; the user-facing words (release, edited since, libraries using it, built on, Update) are those of [ADR 0194](../adr/0194-user-facing-terminology.md). This RFC says *tenant*, *grant* and *subscription* where the schema and the API do.

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
- **An attachment added onto an existing item.** By design it changes what the item resolves to in every library that holds it ([RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md) §3: one Longsword that gains a price and dice), so it is a decision for the library, not a routine change. *Built as a warning, not as a breaking change: every release of a bridge adds some, so acknowledging them would drown the acknowledgement that matters ([ADR 0208](../adr/0208-the-release-digest-and-the-breaking-change-detector.md)).*
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

## What was tried

**R1 was run on 2026-10-08 and passed.** The serialiser, about two hundred lines, and the tests live on the throwaway branch `spike/release-roundtrip`, which is not merged.

**What it ran on.** The four seed repositories made the way a person makes them (`tenant create`, `seed --layer`, `repo offer`, `apply --part`, `repo publish`, as in [ADR 0183](../adr/0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)): core, the equipment, D&D rules, and the bridge built on the last two, so the diamond (both are built on core) and the bridge's attachments are the real ones. Then the library that took the bridge, whose `Content` carries copy links, snapshots and attachments of its own. Then a repository made for the purpose, with a row in every content table, one picture used twice and two documents, and a copy record of each kind, deleted and merged links included. The edits for the update checks were made in the database, as authors would through the routes, on the seed repositories and on the Armoury world of [ADR 0208](../adr/0208-the-release-digest-and-the-breaking-change-detector.md)'s tests, which has an enum, a formula, a slug and a prototype edge between two items.

**The document.** Every field of `Content` becomes JSON: ids as strings, tuples and sets as lists (sets sorted), `Decimal` as its string, `StatValueType` as its value, a stat or a formula as an object, picture and document bytes as their SHA-256 with the file type and name kept beside it, the copy links as maps. Read back, it builds the same classes. The gzip header carries no time, so equal documents are equal bytes.

**Field for field.** A walk that checks the class of every container and scalar, the scale of every `Decimal`, `bool` against `int`, a `defaultdict` against a `dict` and what its factory makes, a tuple against a list, a set against a list, and the order of every list and dict, found no difference on any of the six contents. The one thing that is not the same class is the id: the database driver returns its own `UUID` subclass and the document reads back the standard one. They compare, hash and print equal and nothing reads the class. Two loads of unchanged rows came out equal down to the order of every list, but SQL does not promise that, so nothing relies on it.

**The engines.** `plan_copy` and `compute_updates` read a repository at one place each, through `load_content`; the spike put a function there that answers from the read-back for the repositories named and from the rows for every other tenant. Their results, compared with the same walk (new ids made deterministic), were identical for:

- a first copy of the bridge, a manifest of four steps with its attachments planned, and a first copy of each of the other three alone;
- a first copy of the repository with pictures and documents, whose planned rows hold the bytes;
- an update of the library that took the bridge after changes in three of the four repositories: the equipment (a rename, a slug, a prototype edge removed, a stat value, an entry added, an entry removed, a kind added), core (a stat group's priority and mandatory flag, a formula's offset) and the bridge (an attachment added). Core showed 3 changed rows, the equipment 4 changed, 1 added and 1 removed, the bridge 1 attachment added, the rules nothing;
- an update after the edits of ADR 0208's tests on the Armoury world, the eleven that are not a removal together and the removal alone. The fields that came out changed were name, slug, prototypes, stat groups, stat values, formulas, enum values, value type and group priority; a kind change is in the digest and not in `updates`, since the diff skips `kinds`.

The manifest reads `repository_copy` directly and not through `load_content`; a document holds the same set in `links.copies`, which `load_links` reads from those rows.

**The digest.** `live_rows` and `digest_of` over the read-back gave the digest of the live load for all six contents, and so did every entity, stat group and stat definition snapshot.

**Pictures once.** The repository with files holds five payloads with bytes, one picture twice. Two documents of it refer to four blobs by SHA-256: 160,008 bytes kept once, where inlined in both they would be 400,016. A map keyed by SHA-256 stood in for the blob table, which the spike did not build.

**Size and time.** Plain is the compact JSON, gzipped the stored document, and the files are not in either.

| Content | Entries | Plain | Gzipped |
| --- | --- | --- | --- |
| Core | 2 | 3,628 | 1,283 |
| Equipment | 39 | 23,900 | 4,959 |
| D&D rules | 32 | 29,630 | 6,890 |
| Bridge | 73 | 88,648 | 16,074 |
| Library that took the bridge | 73 | 92,536 | 16,496 |
| Repository with files | 5 | 7,165 | 2,068 |

That is 0.6 to 1.2 kB per entry plain and 0.1 to 0.2 kB gzipped. In the bridge's document the copy links are 48% (42,436 bytes, 24,248 of them the snapshots), the prototype edges 8%, the text and file payloads 8%, the stat definitions 6%, the stat values 5%. On the bridge, encoding takes 0.2 ms, compressing 1.6 ms and reading back 1.5 ms. These are four small repositories; scale is [R2](#spikes)'s question and nothing here extrapolates it.

**What it found beyond the criteria.**

- **The API accepts `NaN` and `Infinity` as a float stat value**, and the database stores them (`PUT .../stats/{definition}` with those literals answers `200`). Standard JSON cannot carry them, so a serialiser that refuses them fails a publish on a value the API let in, and one that writes them anyway makes a document other readers cannot parse. The serialiser can fix it: write a non-finite float as a tag and read it back as the float. Whether the API should refuse them is a separate question, not this RFC's.
- **Nothing the engines read was missing from `Content`.** No field needed to be added to it or taken out of it.

**Not tried.** The blob table and its keys in Postgres, the immutability trigger, a document written under an older format, `load_upstream` as the one read function, and what a copy does today with a repository that holds a non-finite float (its copy link snapshot is JSONB, which cannot hold one either).

**Verdict.** The release document reproduces the content exactly, and the engines cannot tell it from the live rows. [§4](#4-the-release-document-for-public-repositories) to [§6](#6-flips-between-private-and-public) stand as drawn, and [R5](#slices) can be built.

### R2, scale

**R2 was run on 2026-10-14 and passed, with findings.** The design stands at 20,000 entries. Several things in the code it measured cost more than they need to, one of them growing with the square of the content, and browsing a public repository needs a path of its own. The harness, its results and the extra experiments live on the throwaway branch `spike/release-scale`, which is not merged, under `apps/api/spike_r2/`; `run.sh` takes a size from an empty database to the last profile.

**What it ran on.** Three sizes of one shape, each in an empty database.

- *Core*: a repository of N entries (1,000, 5,000 and 20,000), about six in seven of them items and the rest beings, with 6 stat groups and 42 stat definitions (ints, floats, bools, enums of five values, texts, two derived), about five stored stat values on each entry, a linear formula on one entry in ten, a stat group on three in ten, a link name on two in three, a description of 300 to 1,200 characters on four in five, and a picture (one image of 30 kB, the same each time) on one in a hundred. Prototype edges come in four tiers, so chains are up to four deep; 15% of the entries have a second parent and 3% a third.
- *Bridge*: built on Core by an actual copy through `POST .../copy`, then N/10 entries of its own with one or two parents among the copies, a stat group and three stat definitions of its own, and N/20 attachments (a parent added to a copied entry). At N = 20,000 it holds 21,983 entries, 20,000 of them copied, and 27,410 prototype edges.
- *Libraries*: one that copied Core, one that copied the Bridge (and so Core), one that copied nothing.

| Content as first published after the edits below | 1,000 | 5,000 | 20,000 |
| --- | --- | --- | --- |
| Core: entries | 1,004 | 5,013 | 20,041 |
| Core: prototype edges | 1,176 | 5,818 | 23,233 |
| Core: stat values | 4,778 | 23,794 | 95,302 |
| Core: descriptions | 799 | 4,049 | 16,241 |
| Bridge: entries (copied and own) | 1,100 | 5,493 | 21,983 |
| Bridge: copy links | 1,000 | 5,000 | 20,000 |

Between releases the author's edits were made in the database: 1% of the entries renamed, 1% of the integer stat values changed, 0.5% of entries added, 0.3% removed, 0.2% of the prototype edges taken off and 1% of the descriptions edited on Core, and on the Bridge 5% of its own entries renamed, 1% removed and one more parent on one copied entry in forty (500 attachments at 20,000, besides the 1,000 the library had taken). Each repository was published as a private one, then made public in the database (the API refuses it) and published again, so that every figure below has the read of the rows and the read of a document on the same content.

**How it was measured.** A Postgres 17 of its own database on the container `lorenzo-postgres-1`, with the settings the container has (128 MB of shared buffers), and the app's role `lorenzo_app` with `jit = off` as [ADR 0285](../adr/0285-api-reads-that-cost-what-they-read.md) set it. The code ran from a clone on the native Linux filesystem of WSL, not from `/mnt/c`, whose timings are not to be trusted. The routes were called through httpx against the app in the same process, as the tests do, with the caller's identity supplied (so without the per-request user upsert) and spans made and not exported; the pieces were called as functions. A figure is the median of five runs after one warm-up run (seven below 5,000 entries), with statements counted and the time the database took read from the driver. Peak memory and a cold time are the first run in a process of its own, run once with the resident size read from the kernel and once under `tracemalloc`; the baseline of such a process, with the app loaded, is 133 MB. The machine had 16 cores and 31 GB, so what is reported is cost, not what one small container would do with several requests at once. The descriptions are random hexadecimal text, which gzip compresses less than prose, so the gzipped sizes below are somewhat more than a repository of real text would give.

**What a publish costs.** Through `PUT .../published`, as the Owner, with the releases that came after the first made on content that had changed by the edits above or by one renamed entry:

| Publish, median of the runs (three of Core, two of the Bridge) | 1,000 | 5,000 | 20,000 |
| --- | --- | --- | --- |
| Core, first release (nothing to compare with) | 0.22 s | 0.64 s | 2.4 s |
| Core, private (digest and released rows) | 0.18 s | 0.64 s | 2.7 s |
| Core, public (and the document) | 0.23 s | 1.04 s | 5.4 s |
| Bridge, public | 0.21 s | 1.04 s | 5.3 s |
| Peak memory of the load, digest and document of Core, over the process | 19 MB | 83 MB | 325 MB |
| The same of the Bridge | 25 MB | 111 MB | 437 MB |

A publish is 61 to 71 statements whatever the size. Where the 5.4 s of the public publish of Core at 20,000 goes, by the pieces called alone:

| Piece, Core | 1,000 | 5,000 | 20,000 |
| --- | --- | --- | --- |
| `load_content` | 51 ms | 305 ms | 1.44 s |
| `live_rows` (hash every row) | 8 ms | 52 ms | 245 ms |
| `stored_rows` (the last release's rows) | 9 ms | 36 ms | 456 ms |
| compare, detect, digest | 0 ms | 2 ms | 16 ms |
| the whole of `assess` | 88 ms | 488 ms | 2.2 s |
| `replace_stored_rows` | 33 ms | 149 ms | 746 ms |
| `encode` (`Content` to the document) | 12 ms | 42 ms | 388 ms |
| `dumps`, JSON 4 / 22 / 86 ms and gzip at level 9 | 66 ms | 271 ms | 1.08 s |
| `store_release_document` (encode, dumps and the insert) | 76 ms | 368 ms | 1.6 s |

The rest, about 0.9 s at 20,000, is the lock, the release row, the activity log, the notification of the libraries and the commit. The live digest, which is `assess` on its own, is also what `GET .../release-preview` costs: 0.10, 0.44 and 2.0 s on content with the edits in, 0.09, 0.49 and 2.4 s on unchanged content, 41 statements, 190 MB at 20,000.

**The document.** Plain is the compact JSON, gzipped is the stored row, the files are not in either.

| Document | 1,000 | 5,000 | 20,000 |
| --- | --- | --- | --- |
| Core, plain | 1.9 MB | 9.6 MB | 38.5 MB |
| Core, gzipped | 0.63 MB | 3.2 MB | 13.1 MB |
| Bridge, plain | 2.7 MB | 13.7 MB | 54.9 MB |
| Bridge, gzipped | 0.84 MB | 4.3 MB | 17.4 MB |
| Core, `gzip` at level 9 / 6 / 1: time | 47 / 33 / 11 ms | 256 / 169 / 53 ms | 993 / 667 / 201 ms |
| Core, `gzip` at level 9 / 6 / 1: size | | 3.24 / 3.26 / 3.45 MB | 13.1 / 13.2 / 13.9 MB |
| Core, gunzip and parse | 9 ms | 52 ms | 226 ms |
| Core, decode to a `Content` | 20 ms | 243 ms | 728 ms |
| Core, `read_release_content` (fetch, gunzip, parse, decode) | 38 ms | 284 ms | 1.28 s |
| Bridge, `read_release_content` | 51 ms | 376 ms | 2.8 s |
| Memory kept by a decoded `Content` of Core | 5.1 MB | 25 MB | 101 MB |
| Memory kept by the `Content` loaded from the rows | 5.7 MB | 28 MB | 112 MB |

That is 0.6 to 0.65 kB gzipped for each entry of Core. By the key of the document the payloads (the description texts) are 60% of the gzipped bytes and the stat values 14%, the entries, their kinds, link names and public-catalog flags 13%, the prototype edges 7%. In the Bridge the copy links are 17% (3.0 MB gzipped at 20,000, 12.4 MB plain). Pictures are in the blob table: the one picture of the seed is one row of 30 kB, kept once for every release, as [ADR 0214](../adr/0214-the-release-document.md) says. After the publishes (seven of Core, three of them with a document, and four of the Bridge, two of them) the table `repository_release_document` was 9.9, 19 and 78 MB and `repository_released_row` 4.8, 9.1 and 33 MB, the last of them because the set is deleted and inserted again at each publish and the dead rows wait for the vacuum.

**What a library and a visitor read.** Through the routes, the same content read as rows (a private repository) and as a document (a public one, the document of its current release):

| Route, median | Rows 1,000 | Document 1,000 | Rows 5,000 | Document 5,000 | Rows 20,000 | Document 20,000 |
| --- | --- | --- | --- | --- | --- | --- |
| `copy-plan` of Core | 0.22 s | 0.20 s | 0.98 s | 1.0 s | 4.3 s | 6.9 s |
| `copy-plan` of the Bridge (two steps) | 0.43 s | 0.34 s | 1.5 s | 1.6 s | 7.0 s | 8.7 s |
| `updates`, Core, library that copied Core | 0.27 s | 0.20 s | 1.1 s | 0.96 s | 4.2 s | 5.3 s |
| `updates`, Bridge, library that copied it | 0.20 s | 0.17 s | 1.2 s | 1.2 s | 11.6 s | 16.2 s |
| `GET .../entities`, one page of 50 | 26 ms | 60 ms | 26 ms | 317 ms | 43 ms | 1.4 s |
| `GET .../entities?q=`, `.../stat-groups` | 26 / 16 ms | 56 / 57 ms | 28 / 15 ms | 322 / 285 ms | 59 / 15 ms | 1.3 / 1.2 s |
| `GET .../dependencies` of the Bridge | 25 ms | 65 ms | 25 ms | 223 ms | 22 ms | 0.69 s |
| `GET /tenants/{id}/repositories` (the library's list, no content) | 22 ms | 19 ms | 21 ms | 30 ms | 30 ms | 31 ms |

The first call of `updates` and the repeated ones cost the same (5.5 and 5.3 s at 20,000, Core): there is nothing in it to warm. In a process of its own the first call takes 4.0 s, with 340 MB over the baseline. A copy-plan reads one document for each step and two more parses of each for what the manifest wants: Core's reads one document in full and one for `links.copies`, the Bridge's reads two of each. Ten consecutive pages of the browse of Core take 12.2 s from the document and 0.3 s from the rows at 20,000, 2.7 s and 0.2 s at 5,000, and each page asks the process for 187 MB at 20,000 and 47 MB at 5,000, against 1 MB from the rows. Peak memory of one request over the baseline of 133 MB, at 20,000: `copy-plan` of the Bridge 480 MB, `updates` of Core 340 MB (358 from rows) and of the Bridge 386 MB, building the document of the Bridge 437 MB. Statements per request, from a document and from the rows: `updates` 48 and 79, `copy-plan` of the Bridge 54 and 114. At 20,000 the database spends 1.1 s of the 5.3 s of an `updates` call and 0.1 s of the 8.7 s of the `copy-plan` of the Bridge; the rest is Python. Copying, which R2 did not set out to measure but made to build the Bridge and the libraries, took 0.9, 4.1 and 12 s for Core into a library and 1.1, 5.5 and 19 s for the Bridge and Core into another.

**What it found beyond the criteria.**

- **The garbage collector.** Python's cyclic collector is a growing share of building a big `Content`. With the collector off for the length of the read, `load_content` takes 50 ms against 52 at 1,000 entries, 112 against 247 ms at 5,000 and 340 ms against 1.2 s at 20,000; the decode of a document 322 ms against 536 at 20,000. Every read in the tables above starts with one of the two, so about 0.9 s of each load of the rows at 20,000 is the collector (0.2 s of each decode of a document), and it is why the cost of a load grows faster than the entries (53 ms at 1,000, 1.4 s at 20,000, 27 times for 20). Not tried in the app: raising the collector's thresholds for the process, or suspending it for the length of a load.
- **An O(n × attachments) in the update engine.** `_find_attachment_updates` calls `_local_entity` twice for each end of each attachment, and that calls `local.links.local_of("entity")`, which inverts the whole map of copy links each time. A Bridge of 20,000 entries with 1,500 attachments to look at spends 5 of the 11.5 s of an `updates` call there (profile): `updates` of the Bridge is 11.6 to 16 s where that of Core, with the same entries, is 4.2 to 5.3 s, and it grew 10 to 14 times for 4 times the entries from 5,000 to 20,000. Computing the inversion once, a small change tried only in the harness, brought it from 9.5 to 4.4 s on a fresh 20,000. The fix is in `apps/api/src/lorenzo_api/repository_updates.py` and was not made on this branch.
- **The manifest reads whole documents for one set.** `read_release_copies` gunzips and parses the document to take `links.copies`: 60 ms at 5,000 and 295 ms (Core) and 644 ms (Bridge) at 20,000, once more for each repository of a `copy-plan`, besides the full read, and for the whole of `GET .../dependencies`, which is 22 ms from the rows and 0.69 s from the documents. The set is the one thing of the document a manifest reads, and it can be kept where it can be read without the document (a column next to `blobs`).
- **Compression is the largest piece of the document that is only a choice.** `gzip` at its default level 9 is 1.0 s of the 20,000-entry publish; level 1 is 0.2 s for a document 6% larger (13.9 against 13.1 MB), level 6 is 0.67 s for 0.5% more.
- **The released rows are rewritten whole.** `replace_stored_rows` deletes and inserts every row at each publish, 0.75 s at 20,000 and 20,000 dead rows left for each release. The comparison that `assess` makes already has the rows that differ.
- **`updates` hashes the repository again to mark its rows.** `_mark` calls `live_rows` on the content it has just read, 1.0 s of 7.5 in a profile of Core at 20,000; the document is immutable, so the hashes of a release could be kept with it.
- **`copy-plan` is mostly LorenzoScript.** 17,637 calls of `parse` for the references in the descriptions are about 8 of the 17.6 s of a profile of the Bridge's copy-plan at 20,000, whatever the source of the content.
- **The memory of one request is the limit before the time is.** The deploy workflow sets no memory for the service, so Cloud Run's default applies unless it was changed by hand (not checked): at 20,000 entries a publish of the Bridge needs 437 MB and a `copy-plan` of it 480 MB over a process of 133 MB, and a second request at the same time doubles that.

**Not tried.** Several documents or libraries at once, a smaller container, a Neon database over a network (every figure is a Postgres on the same machine, so the database's share is smaller than it would be), prose in the descriptions, many pictures, retention (the five documents were kept and none removed), a `Content` over 22,000 entries, and any change to the code measured.

**What it decides.** The six questions of [Spikes](#spikes):

1. **Does the digest and the document stay in the publish request?** Yes, up to about 20,000 entries, where a public publish of Core takes 5.4 s and of the Bridge 5.3 s (private 2.7 s), against 1.0 s at 5,000 and 0.2 s at 1,000. It grows a little faster than the entries, because of the collector. [ADR 0208](../adr/0208-the-release-digest-and-the-breaking-change-detector.md) measured 1.7 s for a publish of 20,000 lighter entries, with no document and no descriptions, against 2.7 s here for a private one. Recommended threshold: a release whose content (counting the copied entries of a bridge) is over **20,000 entries**, or whose document is over about 20 MB gzipped, is built in the "building" state, the previous release staying current until it is complete; below it the request is enough. What limits it first is memory (437 MB over the process at 20,000), so the service's memory is set for it, whatever the default is, and a ceiling of 20,000 entries is a candidate quota for a public repository until the building state exists. Switching the document to gzip level 1 and loading with the collector held off take about 1.7 s from the 5.4 (0.8 and 0.9 s, measured piece by piece, not together).
2. **Is "Matches release X" computed on demand or cached?** On demand. It is `assess`: 0.1 s at 1,000 entries, 0.45 s at 5,000, 2.0 to 2.4 s at 20,000, 190 MB, asked when the author opens the release panel and after an edit of theirs, not on a timer. A cache needs a key that moves on every write the digest reads, and `tenant.export_revision` ([ADR 0262](../adr/0262-bulk-entity-export.md)), which is read in 3 ms, moves for sixteen tables and not for stat groups, stat definitions, enum values or the formula tables, which the digest hashes: a cache keyed on it would say "Matches" over an edited stat, the unsafe direction. Triggers on those tables and a test that the trigger tables are the digest's inputs would make it exact; until a screen asks often enough to need it, [ADR 0208](../adr/0208-the-release-digest-and-the-breaking-change-detector.md)'s choice stands.
3. **Is a release read cached per release id?** Not yet, and the first thing to do is to make one read cheaper. What it would save is the read of the document: 1.3 s of the 5.3 s of an `updates` call at 20,000 (Core), 2.8 s of 16 s (Bridge), the whole 1.4 s of a browse page, and about 0.04 s at 1,000. What it costs is the `Content` held: 101 MB for Core at 20,000 and 5 MB for 1,000, in a process that has 512 MiB by default. A cache of decoded documents keyed by release id and bounded in bytes is exact (a document never changes) and is the right shape once many libraries check the same release of a repository of 5,000 entries or more; it saves that read for all but the first of them. Until then: one gunzip for the manifest's set (above), and the browse of question 4.
4. **Does browse of a public repository need a SQL path?** Yes, from about 5,000 entries. A page of 50 is 0.3 s and 47 MB at 5,000 and 1.4 s and 187 MB at 20,000, ten pages 12 s, and `stat-groups`, six groups, 1.2 s, against 15 to 60 ms from the rows at any size; at 1,000 it is 60 ms and does not matter. The document is the right source for what a library copies and the wrong one for paging. A per-release index written at publish is the candidate: one row for each entry of the release (name, kinds, parents, the stat groups and definitions beside it), which is the cost of the released rows (0.75 s at 20,000) and is paged and searched by the database; keeping the entries' names, kinds and prototype ids in a second, small part of the document row (about 4 MB plain at 20,000) would be the cheaper form, at the cost of paging in the process. `repository_released_row` cannot serve, since it holds only a repository's own rows, no parents, and one set.
5. **Is a per-library "updates available" summary cheap enough?** The fact of one is, the count is not. `GET /tenants/{id}/repositories` already carries each copy's `synced_release` and the repository's `current_release`, in 16 to 21 statements and 20 to 40 ms at every size, no content read: "release 1.4 is out, you are on 1.2" costs nothing for a public repository, and for a private one there is no release to compare with. How many rows changed is `updates`: 0.2, 1.0 and 5.3 s a repository, and a library holding several adds them. It is offered where a person opens it, and may be cached for a (library, repository, release taken, current release) of a public repository, whose documents are immutable.
6. **Does the number of retained documents move?** No. Five documents of Core are 3.2 MB at 1,000 entries, 16 MB at 5,000 and 66 MB at 20,000, of the Bridge 4.2, 22 and 87 MB, and the blob table one row of 30 kB however many releases use the picture. Below 5,000 entries that is a few megabytes a repository. At 20,000, 66 to 87 MB is also what the ceiling of question 1 allows, so five stays as proposed and the setting stays a setting; a byte ceiling on the documents of a repository (100 MB is a candidate) belongs with the quotas of [RFC 0038](0038-public-repositories-and-discovery.md), and retention keeps at least the current release and the one before whatever the ceiling.

**Verdict.** The release document and the read switch work at 20,000 entries: a public publish takes 5.4 s, a document is 13 to 17 MB, and reading one from a document costs 1.1 s more than from the rows in an `updates` call and 2.6 s more in a `copy-plan`, so [§4](#4-the-release-document-for-public-repositories) to [§6](#6-flips-between-private-and-public) stand as drawn and nothing is a reason to redraw them. Browsing a public repository is the one read that cannot stay on the document at that size. Before a repository of that size is public: the attachment lookup in the update engine is made linear, the manifest's set is kept outside the document, the document is compressed at a lower level, the collector's share of a load is dealt with, the service has the memory for a publish, and the browse has an index.

## Slices

| Slice | What | Depends on | Touches |
| --- | --- | --- | --- |
| **R1** | Spike: release round-trip ([Spikes](#spikes)); passed, findings in [What was tried](#what-was-tried) | none | api (throwaway branch), docs |
| **R2** | Spike: scale ([Spikes](#spikes)); passed with findings in [R2, scale](#r2-scale) | none | api (throwaway branch), docs |
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
- **The number of retained documents.** Settled by [R2](#r2-scale): five stays, at about 0.65 kB gzipped for each entry of a release (66 to 87 MB for five releases of 20,000 entries); a byte ceiling on a repository's documents is a quota for [RFC 0038](0038-public-repositories-and-discovery.md).
- **Computing "Matches".** Settled by [R2](#r2-scale): on demand (0.45 s at 5,000 entries, 2.0 to 2.4 s at 20,000). A cache needs a revision that moves for every table the digest reads, which `tenant.export_revision` does not yet.
- **One checkbox or one per row** for the breaking acknowledgement. One, listing the rows, is proposed; the API takes one flag either way.
- **How long a "building" release may take, and where it starts.** [R2](#r2-scale) shows publish staying in the request up to 20,000 entries (5.4 s, 437 MB of memory for a bridge); a release over that is built in the "building" state, and what libraries see meanwhile is open (proposed: the previous release stays current until the new one is complete). How long it may take is for the slice that builds it.
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
