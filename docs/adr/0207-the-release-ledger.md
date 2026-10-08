# 0207 - The release ledger

Status: accepted, decided with the maintainer on 2026-10-08. Slice R3 of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), tracked in #528. Needed by T3 and T4, Studio's publish dialog and release composer ([RFC 0036](../rfcs/0036-repository-tooling.md) §4). Extends [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) and [ADR 0121](0121-repository-updates-and-re-sync.md); the label rules, which RFC 0037 left to this slice, are decided here.

## Context

`PUT /tenants/{id}/published` sets a timestamp and sends a fixed message ("has published an update"). It records nothing about what was published, so a library cannot say which version it is on, an author cannot say why a publish happened, and there is no list to show. [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §1 makes a publish a **release**: a row with a number, a label, notes and a breaking flag. This slice is the ledger alone. The digest that says which rows were edited since, the breaking-change detector and the release document are R4 (ADR 0208) and later; nothing here reads a repository's content.

## Decision

### The table

`repository_release`, a tenant table of the repository:

| Column | Meaning |
| --- | --- |
| `id`, `tenant_id` | the release; the repository (`UNIQUE (id, tenant_id)`, so the tables of later slices can point at it with a same-tenant key, [ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)) |
| `number` | 1, 2, 3 within the repository, assigned by the server under a lock on the repository's row, so two publishes at once get two numbers; `UNIQUE (tenant_id, number)` |
| `label` | the author's words, 1 to 80 characters, trimmed; never parsed as a version |
| `notes` | optional, at most 4000 characters; blank notes are no notes |
| `breaking` | the author's statement, false by default |
| `created_by`, `created_at` | who and when; `created_by` is set null when the account goes, like every attribution ([ADR 0029](0029-attribution-created-by-updated-by.md)) |

RLS is `tenant_isolation` and `FORCE ROW LEVEL SECURITY` ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)), and, because the libraries a repository is granted to read its releases, `repository_read` too: the table is in the first list of `repository_access` ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), so the test that every tenant table is classified, and the one that a granted library sees every table only inside the gated read and can never write one, cover it. A release is never deleted on its own: unpublishing leaves the ledger, and the numbers continue when the repository publishes again. It goes with its repository ([ADR 0184](0184-deleting-a-tenant.md)).

Nothing points at a release with a foreign key. A copy records the release it last took as a plain id, as it records the repository it came from (`repository_copy.synced_release_id`, below), since the copy is another tenant's row and the repository may go.

### Labels

- **Unique within the repository, whatever the case.** "Spring" and "SPRING" are one label: a unique index on `(tenant_id, lower(label))`. Another repository may use the same label. A clash answers `409 release-label-taken` and makes nothing.
- **The default is the number**, as RFC 0037 says: a call without a body, as today's command line makes it, publishes release 1 labelled "1". If the author had already used "3" as a label for an earlier release, release 3 would clash with it and the publish is refused with the same `409`, which says to give this one a label. The alternative, skipping to the next free number or inventing a suffix, would make a label say what the author did not write.
- **Anything else is the author's.** No pattern, no SemVer, any Unicode text; whitespace around it is dropped.
- **The label and the notes may be corrected; nothing else may.** `PATCH /tenants/{id}/releases/{release_id}` takes `label` and `notes` (an Owner, as publishing is; the notes may be cleared with `null`, the label may not). The number, `breaking`, the counts and the digest of later slices are what was published and announced: an unknown field is a `422`, and a release's flag is not raised or lowered after libraries were told. Changing a label to another case of itself is allowed. The activity log records `repository.release_edited` with the release number and the names of the fields, not their text. A notification already sent keeps the words it carried.

### Reading the ledger

- **`GET /tenants/{id}/releases`**, for any member of the repository: a page of releases, newest first (`page`, `size` as every list). `409` for a play tenant. Each item: `id`, `number`, `label`, `notes` (null when none), `breaking`, `created_at`, `created_by` (the user's id, null once their account is gone). It is an id and not a name: the names of a repository's people are the roster's, and a name beside every release would be a second place to keep them in step.
- **`GET /tenants/{id}/repositories/{repository_id}/releases`**, for any member of a library the repository is granted to and published: the same list through the gated read ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), `404 repository-not-found` for a repository that is not invited, not published or not theirs, as every read of it answers. It leaves `created_by` out: who published a public repository is a question of its own, [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)'s publisher identity, and a library has no need of it.
- **`SubscriberOut`** (a repository's `GET .../subscribers`) gains `synced_release` and **`SubscriptionOut`** (a library's `GET .../repositories`) gains `synced_release` and `current_release`, each `{id, number, label}` or null: the release a copy last took, and the repository's newest. "On release 1.2" and "Last updated from release 1.2" are one read. A library gets them only where it can read the repository (granted and published); one whose invitation is gone has `synced_release: null`. Until a later slice adds `current_release_id` to the repository ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §5), the **current release is the newest by number**.

### What a publish does

`PUT /tenants/{id}/published` takes an optional body `{label?, notes?, breaking?}`. In one transaction it makes the release, sets `published_at` as before, records the activity, tells the libraries and commits. The answer is the repository as `GET /tenants/{id}` has it plus `release` (the new one, with `created_by`), so a client has what it made without a second call.

- **The notification carries the release.** The title is "{name} published release {label}"; the body is the notes cut at 280 characters between words with an ellipsis, then, when the release is breaking, "This release is marked breaking: it may change things your library already uses."; with neither, the line it had before ("Check its updates to see what changed."), which is still true. The notification type stays `repository_updated`.
- **The first publish keeps its own wording**: "{name} is published", and its body as it was; the notes and the breaking line, when given, follow it.
- **The activity log** records `repository.published` with `release=<number>,breaking=<true|false>,label=<label>`. The log's rule is ids, counts and field names, never what someone wrote, because its readers must not learn GM-only text; the label is not that. It is the title of what the libraries are told, and the same people who read the log write it.
- **Unpublishing** (`DELETE /published`) is unchanged.

### `synced_release_id` on a copy

`repository_copy.synced_release_id`, a plain id, null before a copy has one. It is set wherever `synced_at` is set: when a copy is made (the repository's newest release at the moment of the read), and when updates are applied, **including a call that applies nothing or only some of the changes**, since the library has looked at that release and chosen. A dry run rolls back, so it moves nothing. A copy made before there was a ledger has none, and so does a copy of a repository that published before it and has not published since: the migration backfills nothing, because the ledger records what was published and an invented release 1 would say something nobody did. It never says "up to date"; that is only said when the library's update list is empty.

### The command line

`lorenzo repo publish --tenant <repository> [--label ...] [--notes ...] [--breaking]`. With none of the three it sends no body, as before; the answer names the release ("Published release 1.3 of sunken-vale", "sunken-vale is published as release 1.0") and `--json` prints the repository with its `release`. `lorenzo repo subscribers` and `lorenzo repo list` gain a release column, and the second says "(1.4 is out)" beside a copy that is behind. The models are generated from the API's schema as ever ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)).

## Not in scope

- The digest, the released rows, the `state` of a row on `updates`, the detector and `acknowledge_breaking`: R4 (ADR 0208).
- A release document, a read switch, `current_release_id` and rolling back to a release: RFC 0037 §4 to §6.
- Deleting a release. A mistaken one is corrected in its words, and the next release says so.
- Where a library reads the release in its own screens: the Shelf's inbox ([RFC 0036](../rfcs/0036-repository-tooling.md) S4).

## Consequences

- Studio's release list and composer, and the publish dialog's "libraries will be told release X", have what they need from the API; a library can say which release it is on.
- API changes, each additive for a client that reads what it needs: `PUT /published` takes an optional body and answers a superset of what it answered; `GET .../subscribers` and `GET .../repositories` gain required response fields; the non-first notification's title and body change ("has published an update" is gone), which the RFC names as intended. No accepted break is added to `openapi-breaking-accepted.txt`.
- A repository's publish history is kept from here on. A repository that has published before has no release 1; its first publish from now on is its release 1, and its libraries' copies show no release until they next copy or apply.
