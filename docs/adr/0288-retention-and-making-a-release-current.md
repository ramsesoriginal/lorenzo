# 0288 - Retention and making a release current

Status: accepted, decided with the maintainer on 2026-10-14. Slice R7 of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), tracked in #710. Builds on [ADR 0214](0214-the-release-document.md) (the document, written and read), [ADR 0286](0286-the-read-switch-for-public-repositories.md) (a library reads the current release, which was the newest until now) and [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md) (the digest, the released rows and the detector).

## Context

A public repository's libraries read its current release's document. Until this slice the current release was the newest, so a bad release could only be answered by publishing another, and every document was kept for ever. [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §5 asks for three things: the repository says which release is current, the documents of old releases are dropped, and an Owner can point the repository at an earlier release whose document is still kept.

## Decision

### `tenant.current_release_id`

A column on the repository's tenant row, a same-tenant key to `repository_release` (composite with the tenant's own id, as `weapon_stat_group_id` is, [ADR 0281](0281-sheet-settings-and-the-sheet-read.md)), cleared and not the tenant if the release is ever deleted. It is on `tenant` and not on the profile because the profile is what the Owner writes about the repository: a publish is not an edit of it, and `tenant` has no row-level policy for the gated read to go through. The migration sets it to the newest release of every repository that has one, which is what a library read until now.

`repository_releases.current_release` is the one function that answers "what does a library read": the release `current_release_id` names, and the newest for a repository that has none set. A publish sets it to its own release, so for a repository nobody has rolled back it is always the newest and nothing a library does changes. The author's side compares with it too: `assess`, behind the preview and the publish, compares the live content with the current release, so "Edited since" always means since the release libraries read.

### Retention

`release_documents_retained` (a setting, default **5**; "a setting, not a promise", [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §5) is the number of newest releases of a public repository that keep their document. A publish of a public repository, having written its own, drops the documents of every release but those and the current one, and then the files (`repository_release_blob`) that no kept document lists, which the document's `blobs` column says without opening one. A release keeps its ledger row, its counts, its digest and its breaking and warning rows for good: only its content goes, and with it the chance to make it current again. Pruning runs at a publish and at nothing else; a private repository's publish writes no document and prunes none, so the documents of a repository that went private stay under retention, read by nothing.

The current release is kept whatever its age. Since a publish makes the new release current, the old current is only ever kept past retention by a setting that was lowered, or by a later caller of `prune_release_documents`; the function takes it as an argument so that none can forget.

### Making a release current

`PUT /tenants/{id}/releases/{release_id}/current` (Owner), body `{acknowledge_breaking}` optional.

- **`404`** for a release the repository did not make, for its own Owner as for anyone, the same as `PATCH /releases/{id}`.
- **`409 release-not-retained`** when its document is gone: a release of a private repository never had one, and an old one of a public repository was pruned. The ledger says it exists; its content cannot be read.
- **The released rows** (the one set, [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md)) are recomputed from the document with `live_rows`, the function a publish uses, and replace the stored rows. The document's digest is checked against the release's own, so a document that does not hash to what the release said is an error and not a silent rollback to something else.
- **The detector runs between the release that was current and the one chosen**, as it runs between the last release and a new one: `compare(stored rows, rows of the document)`, `detect`, `split`. What it finds is what a library built on the first and updated to the second would lose. `409 release-has-breaking-changes` lists the rows, and `acknowledge_breaking` is the same one flag. Moving back to an older release that has an entry the newer one removed adds a row and breaks nobody; moving forward again to the release that removed it does, and says so.
- **The pointer moves** and the repository's `updated_by` with it. The ledger rows do not change: a release's breaking rows describe the publish that made it.
- **Libraries are told**, as for a publish: a notice to each library's Owners and Organizers, "{repository} made release {label} current", with the release's notes cut and a line saying a library that already took a later release will see the earlier state as changes. That is correct and said: their base snapshot is the newer one, so the older content shows as updates they may take or leave.
- **Making the current release current is a no-op**: `200`, nothing recomputed, nothing logged, nobody told.
- **Logged** in the repository's activity as `repository.release_made_current`.
- **What a library that updated to a later release sees.** Its update check lists releases after the one it took up to the current one for the notes of breaking and warning rows (`notes_since(upto=)`), so a rollback past the release it took lists none of the later releases' rows as skipped.

### What the lists say

`GET .../releases` of a repository, and of a library's view of one, gain `current` (the release libraries read), and the repository's own gains `kept` (whether its content is still there to be made current). They are additive. The release in a preview and in an update check is the current one, so says `current: true`.

## What the tests pin

- A publish makes its release current and a library reads it; a private repository keeps no document and its newest release is current.
- Making an earlier release current changes what a library browses, what "Edited since" compares with, and what a library on the newer release sees as changes; publishing after a rollback numbers on from the newest and is current at once; the rows a release matches follow the release made current, both ways.
- Libraries are told once, with the label; the current release made current is a no-op.
- Moving forward to a release that removed something a library on the other holds is `409` with the rows, and goes with `acknowledge_breaking`; going back is not.
- A release whose content is not kept is `409 release-not-retained`; only the Owner moves it (an Organizer is `403`); a release of another repository is `404`.
- Retention keeps the newest releases' documents and every ledger row; pruning keeps the current release and the files a kept document needs, and drops the rest, down to none.

## Not in scope

- **Flipping a repository between private and public**, the rule that makes a public repository's first release atomic with it, and the bridge-skew gate: R8.
- **A button.** The Studio release list, the confirmation and its wording are [RFC 0036](../rfcs/0036-repository-tooling.md)'s T7.
- **Pruning at a time other than a publish**, and a limit in bytes: R2's measurements may ask for either.

## Consequences

- A bad release of a public repository can be undone without losing anything: the libraries read the earlier content at once, the author's "Edited since" follows, and libraries that took the bad release are told and see the older content as changes.
- A public repository costs the size of its last five documents and the files they list, not of all its releases.
- One migration adds the column and sets it; no other table changes.
