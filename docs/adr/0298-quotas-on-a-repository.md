# 0298 - Quotas on a repository

Status: accepted, with the numbers decided by the maintainer. Slice D6b of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) (section 6, item 3), tracked in #745. Builds on [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (repository tenants), [ADR 0237](0237-api-pictures-and-information-order.md) (pictures on an entry), [ADR 0056](0056-profile-pictures.md) (the cover) and the scale spike of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) (R2).

## Context

A repository other libraries read and copy is stored in one Postgres, pictures included, as bytes ([ADR 0017](0017-information-and-payloads.md)). Nothing bounded how large one could grow: a repository could hold any number of entries and any number of pictures, and a library that copied it took every byte again. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) makes a repository something strangers can copy, so it asks for a bound before `public` is accepted: a most number of entries, a most total of picture bytes, and a most size for one picture, in every repository tenant, set above what the seeded repositories hold.

## Decision

### The limits

Three settings, each read from the environment, each `0` for "no limit", and each held only for a tenant of kind `repository`: a play library is never limited.

| Setting | Variable | Default |
| --- | --- | --- |
| `repository_max_entries` | `REPOSITORY_MAX_ENTRIES` | 30,000 |
| `repository_max_picture_bytes` | `REPOSITORY_MAX_PICTURE_BYTES` | 20,000,000 (20 MB in all) |
| `repository_picture_max_bytes` | `REPOSITORY_PICTURE_MAX_BYTES` | 10,000,000 (10 MB for one picture) |

**Measured first.** The seeded repositories are small: the four layers of `lorenzo seed` hold 64 entries between them (2 in core, 30 in D&D's rules, 32 in the equipment), and the importer adds the 221 items of the SRD ([ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md)); the largest, the bridge, holds about 290 entries once it has copied the equipment and the rules, and none of them has a picture. The scale spike of RFC 0037 built a repository of 20,000 entries with a 30 kB picture on one entry in a hundred, 200 pictures and 6 MB, and a bridge of 21,983 entries with 20,000 copied; it passed at 20,000 and named a ceiling of 20,000 entries as the candidate quota until a release can be built asynchronously. So:

- **30,000 entries** is 103 times the largest seeded repository and 1.5 times the largest size the spike measured. A publish of 20,000 entries takes 5.4 s and 437 MB over the process; what a publish of 30,000 needs was not measured, and whether it fits the service's memory, or needs the "building" state of RFC 0037, is that RFC's to settle before a repository of that size is published.
- **20 MB of pictures in all** is 3.3 times the spike's 6 MB at its largest, and room for about 660 pictures of 30 kB.
- **10 MB for one picture** is 333 times the spike's picture, and it equals [`picture_max_bytes`](0237-api-pictures-and-information-order.md), the cap on one picture for every tenant (10,000,000, answering `422 invalid-picture`). By default the limit of a repository is therefore no stricter than the global cap: a picture over it is refused as invalid before the repository's limit is looked at. It is a setting of its own so that it can be lowered for repositories without lowering it for libraries, and then a picture between the two is refused in a repository only, with the `413` below.

They are settings and not promises: a deployment that has measured more sets its own.

### What counts

- **Entries** are the rows of `entity` of the tenant, every kind of entry (items, beings, characters, groups, an inventory item, and the entries a copy brought), counted by the tenant's own index.
- **Picture bytes** are the bytes of every `payload_picture` of the tenant: the pictures on the information of its entries, the main picture included, and those a copy brought.
- **A cover is not one of them.** A repository's cover and profile picture are one picture row each in `profile_picture`, replaced and not added to, and bounded by `profile_picture_max_bytes` ([ADR 0056](0056-profile-pictures.md)). Counting it would make a quota a person meets by changing their cover.
- **Release blobs are not a second count.** A release keeps each picture once, by SHA-256, in `repository_release_blob`; a blob is a picture the repository held at the time, so the blobs are bounded by the pictures and the number of releases retained ([ADR 0288](0288-retention-and-making-a-release-current.md)).

### Where it is enforced

By hand, not by the engines. The limits hold what a person writes into a repository: the routes, the importer, Bench through the routes, and any direct ORM insert. They do not hold the copy and update engines.

- **A flush hook** on the ORM session (`repository_quotas.install`, installed when the application starts) looks at what a flush is about to insert, before it writes anything: new `Entity` rows, and new or replaced `PayloadPicture` rows. Every route that makes an entry (the entries route, the item and group routes, a character, an inventory item, a split, a pack given out), the importer and Bench through those routes, and every picture upload (the main picture, a picture on information) pass through it. A new way of making an entry or a picture is held to the limits without being told to be.
- **Copies and updates into a repository are exempt and never refused** by any of the three limits. `repository_copying.write_rows`, which a copy, a copy again and the additions of an update share, inserts whole tables of rows with Core statements the hook never sees, and does not check them. What a repository that builds on another holds is its upstream's, and the upstream was held to these limits when its entries and pictures were written; refusing the engine would leave a half-built stack, a bridge short of the repository it is built on. A copy into a play library was never limited either.
- **What a bridge holds still counts.** The counts are of rows, so the entries and pictures a copy brought are in the totals when someone later adds to the repository by hand: a bridge that is over a limit by its copies is refused its next manual entry or picture, and only that.
- **A replayed create is not new.** A create sent twice under the client's own id ([ADR 0222](0222-ids-made-by-the-client.md)) is answered with the entry it already made before anything is inserted, so a repository at its limit still answers a replay.

### Only growth by hand is refused

A write is refused for what it adds, never for what the repository already holds. Renaming, editing text, setting a stat, deleting an entry or a picture, and replacing a picture with a smaller one or one of the same size are not blocked, however far over a limit a repository is, whether the limit was lowered later or a copy took it over. Replacing a picture with a larger one is refused only when it takes the total past its limit. Deleting frees room at once. An entry added and one deleted in the same flush count for the difference.

### The refusal

Three problems, additive, each with `detail` in words for a person and the numbers beside it (`quota`, `limit`, and what is held and added or the size):

| Problem | Status | When | Example `detail` |
| --- | --- | --- | --- |
| `repository-entry-limit` | 422 | an entry added by hand over the limit | "This repository holds 30,000 entries, which is the most a repository can have." Where it holds more than the limit, or several are added at once: "This would make 30,006 entries in this repository, and a repository can have 30,000 at most. It holds 30,005." |
| `repository-picture-total-limit` | 422 | a picture that takes the total past its limit | "The pictures in this repository take up 19.9 MB, and this one would take them past 20 MB, the most a repository can hold." |
| `repository-picture-too-large` | 413 | one picture over the single limit | "This picture is 3.4 MB, and a picture in a repository can be 2 MB at most." (with a limit lowered below the global cap) |

A single picture is a `413` because the picture itself is the problem and will not fit however much room there is; the other two are `422`, the request's content against what the repository can still take. Nothing is written for a refused request (the entry, its link name, the information and the payload of a picture are all in the one rolled-back transaction) and nothing is logged beyond the refusal.

### What it costs

The check is a count by the tenant's own indexes, made only when a write adds an entry or a picture to a repository, and not at all for a play library after its kind is known. Measured on Postgres 17 on the docker container, as `lorenzo_app` with row-level security on, in a repository of 20,000 entries and 1,538 pictures of 30 kB (46 MB):

- the count of entries, `ix_entity_tenant_id` as an index-only scan, 20,000 rows, 18 buffers: 6.1 to 6.4 ms;
- the sum of picture bytes, `ix_payload_picture_tenant_id` and `octet_length`, which reads the size from the stored value's header and never a picture in full: 0.55 ms;

and one statement to learn the tenant's kind, which a request that has read its tenant already holds. A route that adds an entry therefore pays about 6 ms at 20,000 entries and less below it; the count grows with the rows it counts and was not measured at 30,000.

### What it does not do

- **No lock.** Two writers at the same moment can each see room that only one of them can have, so a repository can end up over by at most the writes that were in flight. A lock per repository would serialise every write to it and could wait in a cycle with the capacity check's row locks ([ADR 0128](0128-capacity-and-moving-anyway.md)); the limits protect the database from growth, not an exact count.
- **A byte ceiling on a repository's release documents** (RFC 0037 names 100 MB as a candidate) is not built here: a document is bounded by the entries it holds.
- **The engines are not bounded here,** so a chain of bridges can hold more than one repository's limit: each is bounded by what it was built from and what was added by hand.

## Consequences

- **What people write into a repository cannot grow without bound,** and each limit says which it is and its number.
- **A new way of making an entry or a picture by hand is held to the limits without being told to be,** through the flush hook. The copy and update engines are the one exemption, by design; a test fails on a Core insert of an entry or a picture anywhere else, which the hook would not see.
- **A copy or an update into a repository never fails for size,** so the hub's copy wizard has no quota refusal to meet, and it has no special case for one. The hub writes no entries or pictures into a repository by hand (its one picture, the cover, is not counted). Bench passes the API's words on as it does any refusal.
- **A repository over a limit keeps working** and can only shrink or change; a bridge made large by its copies is refused only its next entry added by hand.
- **Quota refusals are new problem types with no new fields to read,** so no client had to change: the OpenAPI schema is the same.

## Tests

`apps/api/tests/test_api_repository_quotas.py`, through the real HTTP API: at the limit succeeds and one over is a `422` with the message above and nothing written; every way of making an entry (the entries route with each kind, the item route, the group route, and a row an ORM session adds by itself) is held; a replayed client id is not new; deleting frees room; a repository over a lowered limit can be changed and shrunk and refused to grow; a play library is never limited, by entries or pictures; `0` takes a limit off; one picture over the single limit is a `413` on the main picture and on a payload, with no information or payload kept; the total refuses at the limit, counts a replacement by what it adds and a removal by what it gives back; the cover is not counted; a copy into a repository succeeds past the entry limit, the single limit and the total, and the next entry or picture added by hand is then refused; the additions of an update are not refused; a copy into a play library is not limited; the defaults; the sizes in words; and the source guard. In the hub, `describeError`'s words for the problems, and a real-API spec against an API limited to 50 entries: the 51st entry by hand is refused in words and a copy past the limit through the wizard is not; in Bench, the transport's refusal of both.
