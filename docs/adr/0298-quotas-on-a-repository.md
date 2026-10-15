# 0298 - Quotas on a repository

Status: accepted. Slice D6b of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) (section 6, item 3), tracked in #745. Builds on [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (repository tenants), [ADR 0237](0237-api-pictures-and-information-order.md) (pictures on an entry), [ADR 0056](0056-profile-pictures.md) (the cover) and the scale spike of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) (R2).

## Context

A repository other libraries read and copy is stored in one Postgres, pictures included, as bytes ([ADR 0017](0017-information-and-payloads.md)). Nothing bounded how large one could grow: a repository could hold any number of entries and any number of pictures of 2 MB each, and a library that copied it took every byte again. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) makes a repository something strangers can copy, so it asks for a bound before `public` is accepted: a most number of entries, a most total of picture bytes, and a most size for one picture, in every repository tenant, set above what the seeded repositories hold.

## Decision

### The limits

Three settings, each read from the environment, each `0` for "no limit", and each held only for a tenant of kind `repository`: a play library is never limited.

| Setting | Variable | Default |
| --- | --- | --- |
| `repository_max_entries` | `REPOSITORY_MAX_ENTRIES` | 20,000 |
| `repository_max_picture_bytes` | `REPOSITORY_MAX_PICTURE_BYTES` | 50,000,000 (50 MB) |
| `repository_picture_max_bytes` | `REPOSITORY_PICTURE_MAX_BYTES` | 1,000,000 (1 MB) |

**Measured first.** The seeded repositories are small: the four layers of `lorenzo seed` hold 64 entries between them (2 in core, 30 in D&D's rules, 32 in the equipment), and the importer adds the 221 items of the SRD ([ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md)); the largest, the bridge, holds about 290 entries once it has copied the equipment and the rules, and none of them has a picture. The scale spike of RFC 0037 built a repository of 20,000 entries with a 30 kB picture on one entry in a hundred, 200 pictures and 6 MB, and a bridge of 21,983 entries with 20,000 copied; it passed at 20,000 and named a ceiling of 20,000 entries as the candidate quota until a release can be built asynchronously. So:

- **20,000 entries** is 69 times the largest seeded repository and the size the spike measured; a publish of it takes 5.4 s and 437 MB, which is what bounds it, not the rows. A bridge that copies a repository of 20,000 entries is therefore refused, which is a reason to build on a smaller one.
- **50 MB of pictures** is 8 times the spike's 6 MB at its largest, and room for about 1,600 pictures of 30 kB; a copy takes every byte again, so the total is also what one library's copy can cost the database.
- **1 MB for one picture** is 33 times the spike's picture and half of [`picture_max_bytes`](0237-api-pictures-and-information-order.md) (2 MB), which stays what it was for every tenant and answers `422 invalid-picture`; a picture between the two is refused in a repository only.

They are settings and not promises: a deployment that has measured more sets its own.

### What counts

- **Entries** are the rows of `entity` of the tenant, every kind of entry (items, beings, characters, groups, an inventory item, the entries a copy brings), counted by the tenant's own index.
- **Picture bytes** are the bytes of every `payload_picture` of the tenant: the pictures on the information of its entries, the main picture included.
- **A cover is not one of them.** A repository's cover and profile picture are one picture row each in `profile_picture`, replaced and not added to, and bounded by the 2 MB of `profile_picture_max_bytes` ([ADR 0056](0056-profile-pictures.md)). Counting it would make a quota a person meets by changing their cover.
- **Release blobs are not a second count.** A release keeps each picture once, by SHA-256, in `repository_release_blob`; a blob is a picture the repository held at the time, so the blobs are bounded by the pictures and the number of releases retained ([ADR 0288](0288-retention-and-making-a-release-current.md)).

### Where it is enforced

At each way a row is made, in one place for each, not a call at every route:

- **A flush hook** on the ORM session (`repository_quotas.install`, installed when the application starts) looks at what a flush is about to insert, before it writes anything: new `Entity` rows, and new or replaced `PayloadPicture` rows. Every route that makes an entry (the entries route, the item and group routes, a character, an inventory item, a split, a pack given out), the importer and Bench through those routes, and every picture upload (the main picture, a picture on information) pass through it. A new way of making an entry or a picture is held to the limits without being told to be.
- **`repository_quotas.check_rows`** is the same check for the copy and update engines, which insert whole tables of rows with Core statements the hook never sees; it is called by `write_rows`, which both share, so a copy into a repository, a copy again, and the additions of an update are all held to the limits.
- **A copy is whole or not at all.** The check runs before the first row is inserted, and the request's transaction is rolled back on a refusal, so `copy` and `copy-plan`'s check first (the dry run, which does everything and rolls back) both answer with the refusal and write nothing.
- **A replayed create is not new.** A create sent twice under the client's own id ([ADR 0222](0222-ids-made-by-the-client.md)) is answered with the entry it already made before anything is inserted, so a repository at its limit still answers a replay.

### Only growth is refused

A write is refused for what it adds, never for what the repository already holds. Renaming, editing text, setting a stat, deleting an entry or a picture, and replacing a picture with a smaller one or one of the same size are not blocked, however far over a limit that was lowered later a repository is. Replacing a picture with a larger one is refused only when it takes the total past its limit. Deleting frees room at once. An entry added and one deleted in the same flush count for the difference.

### The refusal

Three problems, additive, each with `detail` in words for a person and the numbers beside it (`quota`, `limit`, and what is held and added or the size):

| Problem | Status | When | Example `detail` |
| --- | --- | --- | --- |
| `repository-entry-limit` | 422 | an entry (or a copy's entries) over the limit | "This repository holds 20,000 entries, which is the most a repository can have." For a copy or several entries: "This would make 20,006 entries in this repository, and a repository can have 20,000 at most. It holds 20,000." |
| `repository-picture-total-limit` | 422 | a picture that takes the total past its limit | "The pictures in this repository take up 49.9 MB, and this one would take them past 50 MB, the most a repository can hold." |
| `repository-picture-too-large` | 413 | one picture over the single limit | "This picture is 1.4 MB, and a picture in a repository can be 1 MB at most." |

A single picture is a `413` because the picture itself is the problem and will not fit however much room there is; the other two are `422`, the request's content against what the repository can still take. Nothing is written for a refused request (the entry, its link name, the information and the payload of a picture are all in the one rolled-back transaction) and nothing is logged beyond the refusal.

### What it costs

The check is a count by the tenant's own indexes, made only when a write adds an entry or a picture to a repository, and not at all for a play library after its kind is known. Measured on Postgres 17 on the docker container, as `lorenzo_app` with row-level security on, in a repository of 20,000 entries and 1,538 pictures of 30 kB (46 MB):

- the count of entries, `ix_entity_tenant_id` as an index-only scan, 20,000 rows, 18 buffers: 6.1 to 6.4 ms;
- the sum of picture bytes, `ix_payload_picture_tenant_id` and `octet_length`, which reads the size from the stored value's header and never a picture in full: 0.55 ms;

and one statement to learn the tenant's kind, which a request that has read its tenant already holds. A route that adds an entry therefore pays about 6 ms at 20,000 entries and less below it.

### What it does not do

- **No lock.** Two writers at the same moment can each see room that only one of them can have, so a repository can end up over by at most the writes that were in flight. A lock per repository would serialise every write to it and could wait in a cycle with the capacity check's row locks ([ADR 0128](0128-capacity-and-moving-anyway.md)); the limits protect the database from growth, not an exact count.
- **A byte ceiling on a repository's release documents** (RFC 0037 names 100 MB as a candidate) is not built here: a document is bounded by the entries it holds.
- **The copy plan does not say a copy would be refused**; the refusal comes with the copy, and "check first" runs it.

## Consequences

- **A repository cannot grow without bound,** and each limit says which it is and its number.
- **A new way of making an entry or a picture is held to the limits without being told to be,** through the flush hook; one that inserts with Core statements calls `check_rows`, and a test fails on a Core insert of an entry or a picture outside the copy engine's `write_rows`.
- **The hub shows the refusal in the API's words** where it writes into a repository (a copy or an update into a library that is a repository), and Bench passes the API's words on as it does any refusal.
- **A repository over a lowered limit keeps working** and can only shrink or change.
- **Quota refusals are new problem types with no new fields to read,** so no client had to change: the OpenAPI schema is the same.

## Tests

`apps/api/tests/test_api_repository_quotas.py`, through the real HTTP API: at the limit succeeds and one over is a `422` with the message above and nothing written; every way of making an entry (the entries route with each kind, the item route, the group route, and a row an ORM session adds by itself) is held; a replayed client id is not new; deleting frees room; a repository over a lowered limit can be changed and shrunk and refused to grow; a play library is never limited, by entries or pictures; `0` takes a limit off; one picture over the single limit is a `413` on the main picture and on a payload, with no information or payload kept; the total refuses at the limit, counts a replacement by what it adds and a removal by what it gives back; the cover is not counted; a copy into a repository refused whole by the entry limit and by each picture limit, the same copy into a play library not limited, and the roomier repository taking it; an update's additions held to the limit; the sizes in words. In the hub, the copy wizard's reading of the three problems and `describeError`'s words for them; in Bench, the transport's refusal of both.
