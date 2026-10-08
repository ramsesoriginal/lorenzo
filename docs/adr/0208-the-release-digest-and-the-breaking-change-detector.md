# 0208 - The release digest and the breaking-change detector

Status: accepted, decided with the maintainer on 2026-10-08. Slice R4 of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), tracked in #529. Builds on [ADR 0207](0207-the-release-ledger.md) (the ledger) and [ADR 0121](0121-repository-updates-and-re-sync.md) (the update engine); needed by T3 and T4, Studio's publish dialog and release composer ([RFC 0036](../rfcs/0036-repository-tooling.md) §4), and by the Shelf's update inbox for the marks.

## Context

A release says what its author called it. It does not yet say what it did to the rows the update engine compares, whether a row a library is offered is what the author published or something edited since, or whether it contains a change the engine cannot carry to a library that already copied the repository. [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §2 and §3 decide the mechanism: hash those rows with the functions the diff uses, keep the hashes of the last publish, compare. This slice builds it, decides what the RFC left to it (the changed link name, how "matches" is computed, whether publish stays in the request), and puts the data Studio's dialog needs in one read, before a publish is made.

## Decision

### The released rows

A new tenant table, `repository_released_row`: for each row the update engine compares **and a library can receive**, the SHA-256 of the canonical JSON (sorted keys, no whitespace) of its snapshot, with the few facts the detector needs. Hashed with `entity_snapshot`, `stat_group_snapshot` and `stat_definition_snapshot`, named by origin id, and nothing else: no parallel description of a row exists, so a hash cannot disagree with what the engine would call a change.

| Column | Meaning |
| --- | --- |
| `tenant_id` | the repository |
| `kind` | `stat_group`, `stat_definition`, `entity` or `attachment` |
| `row_id` | the row's origin id, the id a library's copy link holds; an attachment's child |
| `parent_id` | an attachment's parent; null for every other kind (a check keeps the two in step) |
| `hash`, `name` | the hash; the row's name (an attachment's child's) |
| `facts` | `kinds` and `slug` of an entity; `value_type` and `enum_values` of a stat definition; `parent_name` of an attachment |

One row for each key (a unique index on `tenant_id, kind, row_id, coalesce(parent_id, nil)`), **one set for the repository, replaced at every publish in the publish transaction**, not one set for each release. RLS is `tenant_isolation` and `FORCE ROW LEVEL SECURITY`, and the table carries `repository_read` and is in the first list of `repository_access`: a library marks its updates against these hashes, inside the gated read ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). Nothing points at it.

Only the repository's **own** rows are hashed (`Content.own`): a stat group, stat definition or entry that is a copy of another repository's, or merged into from one, is not what this repository offers its libraries, and `compute_updates` skips it for the same reason. A bridge's parent added to a copy is the one thing of a copy that travels, and is an `attachment` row (from `attachments_of`, one hash for a pair of origin ids). So "matches" is blind to a bridge editing its own copy of another repository's row, as the engine is.

`repository_release` gains `digest` (a hash over the sorted `kind:row_id:parent_id:hash` lines of every released row, which survives the rows being replaced), `counts` and `breaking_rows`.

### Released and edited

A row is **released** when its hash now equals the stored one, **edited** otherwise; absent on both sides is equal. A removal that was published is released, one made since is edited, a row new since is edited.

- **`GET .../repositories/{id}/updates`** gains `release` (the repository's latest release, as `GET .../releases` has it, null before its first) and, on every row of `changed`, `added`, `removed` and `deleted_locally` and every attachment of `attachments_added`, `attachments_removed` and `attachments_deleted_locally`, `state` (`released` or `edited`) and `breaking` (below). `attachments_removed` and `attachments_deleted_locally` are now of a type that carries them (`AttachmentChangeOut`), as `attachments_added` is.
- **`state` is null** when the repository's latest release has no digest: the repository has no release yet, or its latest was made before digests ([ADR 0207](0207-the-release-ledger.md) backfills nothing). Everything then behaves as before, the next publish is a baseline, and `matches` stays null.
- A text edit is not seen: descriptions, notes and pictures are not in a snapshot, and "matches" says nothing about them.

### The detector

At publish the live rows are compared with the stored ones. These are **breaking**, as RFC 0037 §3 lists them:

| `reason` | Row | When |
| --- | --- | --- |
| `entity_removed` | the entry | gone since the release |
| `stat_definition_removed` | the stat | gone |
| `stat_group_removed` | the stat group | gone |
| `stat_definition_retyped` | the stat | its value type differs |
| `enum_value_removed` | the stat | an enum value the release had is gone (the detail names them) |
| `kinds_changed` | the entry | its set of kinds differs |
| `slug_changed` | the entry | it had a link name and now has another, or none |
| `attachment_added` | the pair | a parent added to a copy since the release |

**A changed link name is listed** (the question RFC 0037 left open). The engine compares and applies a slug, but `[[slug]]` references in text that was copied once are not rewritten, so a rename can break a library's links without any row saying so; the only moment anyone can say so is the publish. A slug given to an entry that had none is not listed (nothing referred to it). The alternative, leaving it to the author's own `breaking` flag, was rejected because the detector is a floor and this is a known way to fall through it.

- **The first release has no hits**, and neither does any release with nothing to compare with (the latest has no digest): everything counts as added.
- **`PUT .../published` answers `409 release-has-breaking-changes`** while there are hits and the body does not carry `acknowledge_breaking: true`. The problem body has `breaking_rows`: for each, `kind`, `row_id`, `parent_id`, `name`, `reason` and `detail`, a sentence in the vocabulary of [ADR 0194](0194-user-facing-terminology.md) ("“Orc” was removed. Libraries that copied it can only keep their copy, detached."). Nothing is made: no release, and the released rows do not move.
- **An acknowledged release has `breaking` set** and keeps the hits as `breaking_rows` for good, so a library several releases behind sees the union of what it skipped. An author may set `breaking` on a release with no hits; `acknowledge_breaking` with no hits changes nothing.
- **A single flag, listing the rows**, as proposed: the API takes one boolean either way.

### Libraries: marks and confirmation

`breaking` on a row of `updates` is a list of `{reason, detail, release: {id, number, label}}`: why each release **after the one the library last took** (`repository_copy.synced_release_id`) called the row breaking, oldest first, so the library sees the union of what it skipped. A copy with no release on record is owed every breaking release. The key is the row's origin id (and the parent's, for an attachment), which is what a library's copy link holds, so a removed entry's hit lands on the `removed` row, a retyped or enum hit on the stat's `changed` row, and an attachment hit on the pair.

**`POST .../updates` answers `409 update-needs-confirmation`** for an action on a row with such a note unless the action carries `confirm: true` (a field of an update action and of an attachment action, as of the request). The problem body has `unconfirmed`: the row, `reason`, `detail` and the release's label. Nothing is applied, a dry run asks too, and a call that confirms every such row applies as before. **`detach` is not asked about**, and neither is an attachment's: it changes nothing the library holds, and a removed entry's only action is to detach it; RFC 0037 words the rule for "an action", and this reads it as the ones that change content. The library that took the release is on it, so is not asked about it again.

### The preview, for the author

`GET /tenants/{id}/release-preview`, for any member of the repository (`409` for a play tenant), writes nothing and loads the repository once, as a publish does. It is what Studio's guarded dialog and composer show before the publish is made, and a publish records exactly this:

```json
{
  "release": { "id": "...", "number": 2, "label": "1.3", "...": "as GET /releases" },
  "baseline": true,
  "matches": false,
  "live_digest": "9f2c...",
  "differing_rows": 4,
  "counts": {
    "entities": {"added": 1, "changed": 1, "removed": 1},
    "stat_groups": {"added": 0, "changed": 1, "removed": 0},
    "stat_definitions": {"added": 0, "changed": 0, "removed": 0},
    "attachments": {"added": 0, "removed": 0},
    "descriptions_edited": 3
  },
  "added":   [{"kind": "entity", "row_id": "...", "parent_id": null, "name": "Blade", "parent_name": null}],
  "changed": [{"kind": "...", "row_id": "...", "parent_id": null, "name": "...", "parent_name": null}],
  "removed": [{"kind": "...", "row_id": "...", "parent_id": null, "name": "...", "parent_name": null}],
  "breaking": [{"kind": "entity", "row_id": "...", "parent_id": null, "name": "Orc", "reason": "entity_removed", "detail": "..."}],
  "descriptions_edited": 3,
  "libraries_told": 12
}
```

`release` is the latest release (null before the first); `baseline` whether it has a digest to compare with; `matches` whether the live content hashes to its `digest` ("Matches release 1.3" or "Edited since 1.3"), null without a baseline, and `differing_rows` how many rows differ from it. `live_digest` is the hash itself. `counts` is what a publish would record. `added`, `changed` and `removed` name at most **200** rows each, ordered stat groups, stats, entries, attachments, then by name; the counts are complete, and an attachment's `name` is its item and `parent_name` its parent. `breaking` is what a publish would refuse. `descriptions_edited` is the hint: description texts written or edited after the release's `created_at` (`payload.updated_at`, which `write_description` moves), null with no release; it counts a text edited twice once and never sees a deletion. `libraries_told` is how many libraries hold an invitation. The wording rule of RFC 0037 §1 stands: the composer says "text edits are not tracked" beside the hint.

**"Matches" is computed on demand, in the request.** It is the same load a publish makes; nothing is cached, because the only cache that is exact is one invalidated by every write to the dozens of tables a repository holds.

### Release fields

`GET .../releases` and the answer of `PUT .../published` gain `digest`, `counts` (as above, the first release counting everything as added; null for a release made before digests) and `breaking_rows` (empty when none). A library reads the same through the gated read.

### Publish stays in the request

[RFC 0037](../rfcs/0037-releases-and-public-snapshots.md)'s scale spike (R2) has not run, and nothing here depends on its result: the digest, the released rows and the comparison are made in the publish transaction, under a lock on the repository's row so two publishes at once compare one after the other. Measured on a repository of entries each with an item row, four stat values, a stat group and a parent, eight stats, in a local Postgres, one request at a time (the first row includes a cold start):

| Entries | Publish | Publish again (5% renamed) | Preview | A library's `updates` | Copy (for scale) |
| --- | --- | --- | --- | --- | --- |
| 1,000 | 0.31 s | 0.25 s | 0.15 s | 0.19 s | 0.72 s |
| 3,000 | 0.25 s | 0.38 s | 0.27 s | 0.47 s | 2.2 s |
| 6,000 | 0.46 s | 0.63 s | 0.46 s | 0.80 s | 5.2 s |
| 20,000 | 1.70 s | 1.99 s | 1.25 s | 2.72 s | 34 s |

A publish costs about what one `updates` check does, and grows linearly. It stays in the request; a "building" state ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) Open questions) is for a document of a public repository, which this slice does not make.

### The command line

`lorenzo repo publish --acknowledge-breaking`; a refusal names each row and says how to go on. **`repo updates --apply` and `repo offer --apply-updates` follow the rule of RFC 0037**: they take only **released** rows (a row with no state, from a repository without digests, is taken as before) that no release since the last update called breaking; a row edited since the release or called breaking is left and said, and **an attachment is never taken**, however applicable, since it changes what an item is in the library. This replaces the clean selection of [ADR 0174](0174-the-cli-shows-attachments.md), which took an attachment whose ends were here; it is named in an `--actions` file, with `"confirm": true` where a release called it breaking. `repo updates` marks a row "edited since release 1.3" or "breaking, release 1.2".

## Not in scope

- The release document, the read switch, `current_release_id` and "make release current" with its detector run: RFC 0037 §4 to §6. Until `current_release_id` exists, the current release is the newest by number.
- The hub's update inbox and publish dialog, which read these fields.
- A cache of "matches", and a per-library "updates available" count: R2's.
- Comparing text.

## Consequences

- Studio can say, before a publish is made, what it releases, what it would refuse and how many libraries it tells; a library can say, for each row, whether the author published it, and which rows to be careful with.
- API changes: `ReleaseOut` and `ReleaseAuthoredOut` gain `digest`, `counts` and `breaking_rows`; `UpdatesOut` gains `release`; its rows and attachments gain `state` and `breaking`; the apply actions gain an optional `confirm`; `PUT /published` can answer a new `409`, and `POST .../updates` another. All are additive for a client that does not send what is new, and a client that applies breaking rows must now confirm them. The generated clients take them; no accepted break is needed.
- The command line's "apply all clean" changes meaning, as RFC 0037 says it would: it takes less. A script that relied on it taking attachments names them in a file now.
- A repository that has been publishing for a while compares with nothing at its next publish, and from then on has a baseline; its libraries see no marks until then.
- A bridge that builds up its attachments between releases is asked to acknowledge each release that adds one, since an attachment added to an item libraries already hold changes it. That is noisy for a bridge's second release; it is the price of not guessing which items libraries hold.
