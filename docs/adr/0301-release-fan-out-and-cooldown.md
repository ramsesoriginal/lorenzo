# 0301 - The release fan-out and the release cooldown

Status: accepted. Slice D6e of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §6 item 2, tracked in #748. Builds on [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (the notice to the libraries a repository is granted to), [ADR 0207](0207-the-release-ledger.md) and [ADR 0288](0288-retention-and-making-a-release-current.md) (releases, and making an earlier one current), [ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md) (the flip to private, whose revoke notice it carries) and [ADR 0092](0092-campaign-invite-links.md) (a policy that opens on a setting only one code path makes). It is stacked on slice D6a, [ADR 0303](0303-operator-delist.md): its migration hangs off D6a's, and it keeps D6a's rule that a delisted repository tells its libraries nothing.

## Context

Telling the libraries that hold a repository about a release was a loop inside the request that made the release: for each library, switch the tenant, read its Owners and Organizers, add their notices. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)'s fan-out spike measured it (section "Findings of the fan-out spike"): `54 + 4N` statements, 0.9 s at 100 libraries, 21 s at 5,000, and 62 s at 20,000 on the machine of the database, with the repository's row locked for the whole of it; with a network between the API and the database it is several times that, and a client that gives up at 30 s sees an error for a release that was committed. Public repositories make the number of libraries something strangers raise. The spike also tried moving the work after the response: a task after the response lost its tail when the process was killed (1,000 of 10,000 people told, nothing recording who was left), and a table of pending announcements with a cursor, a chunk of notices and the cursor committed together, resumed to exactly one notice per person from kills at random points. What starts a drain is a separate choice, and no scheduler runs in production.

The same section asked for a cooldown between a public repository's releases, so that one announcement is out before the next may start.

## Decision

### The announcement is a row

`release_fanout`, one row for each announcement, written **in the transaction of what it announces**, so that it exists if and only if that does:

| Column | |
| --- | --- |
| `tenant_id` | the repository |
| `release_id` | the release it announces, or null for the notice of the flip to private (a key that moves with the repository, `ON DELETE CASCADE`) |
| `type`, `title`, `body` | the notice as it was worded then: a later edit of the release's label or notes changes nothing already on its way |
| `created_by` | whom the notices say made them: the person who made the release |
| `recipients` | the libraries to tell, as they were then, sorted by id |
| `cursor` | how many of the recipients have been told |
| `created_at`, `updated_at`, `done_at` | `done_at` is set with the last chunk |

Two checks: the cursor is between 0 and the number of recipients, and a finished row has reached the last one. A partial index over `(created_at, id) WHERE done_at IS NULL` is the sweep's one question, so with nothing pending it costs one read of nothing.

Three places write one, through `release_fanout.announce`: `publish_release` (so `PUT .../published` and `PUT .../public`), "make release current" (the rollback) and `make_private` (the revoke notice). The last one reads its recipients **before** it deletes the grants, in that transaction, and the snapshot is what tells them afterwards: the grants are gone by the time anyone drains it. An announcement with no recipient writes no row. `notify_tenant_admins` stays, for the notices that go to one library or a handful: a grant, a revoke, a delisting.

Tenant data of the repository, because it holds who copied it: `tenant_id`, `tenant_isolation` and `FORCE ROW LEVEL SECURITY` ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)), and one line in `copyable_tables.py` as a table that is not content and that a copy never carries ([ADR 0218](0218-the-copyable-table-registry.md)). No route reads it.

### The sweep policy

The drain has to read pending rows of every repository, with no tenant selected. Three more policies, **only for SELECT, UPDATE and DELETE**, open while `app.fanout_sweep` is `on`, which the drain sets for its own transaction and nothing else does ([ADR 0092](0092-campaign-invite-links.md)'s pattern, no `SECURITY DEFINER`). A row is only ever inserted under its own repository's context, in the transaction of its release, and the sweep's setting opens no insert. Both settings are read with `missing_ok`, since the sweep has no tenant. The notices themselves are written as `notify_tenant_admins` writes them, under each library's own context (`membership` is readable under it, and `notification` is insertable by anyone), so nothing else in the wall moves.

### The drain

`release_fanout.drain_chunk`, one chunk a transaction:

1. take the oldest pending row (or the one asked for) `FOR UPDATE SKIP LOCKED`;
2. for each of the next `release_fanout_chunk_size` libraries, set its context, read its Owners and Organizers and add one notice each, flushed before the next library (the same people, the same type, title and body as before; one `batch_id` a library, as before; no new deduplication: the guarantee is the cursor's, and **no unique constraint on `notification`** exists or is needed);
3. move the cursor by compare and set (`WHERE cursor = :old`), setting `done_at` with the last chunk; a row that does not move rolls the chunk back;
4. commit.

A drain that stops anywhere, killed with a chunk half written, leaves the cursor where it was and the chunk uncommitted, so the next drain starts that chunk again and nobody is told twice or missed. One announcement is drained one chunk at a time (a second drain finds its row locked and leaves); two announcements of one repository drain side by side. A library that was deleted has no administrators to read and is passed over. A library that lost its grant between the release and the drain is still told: the snapshot is what is read. What stops a drain (an exception) is logged and left, and the drain returns normally, so a hint in a background task never fails a request.

### What starts a drain

In this order, each a hint for the next:

1. **After the response, in the same process** (`BackgroundTasks`, `drain_after_response`), for the announcements the request wrote. A hint, because a Cloud Run instance has no CPU guaranteed once the response is out and may be stopped.
2. **A sweep** that drains the pending rows of every repository, oldest first, in bounded work: at most `release_fanout_sweep_chunks` chunks a call, the rest left for the next. It runs **at process start-up** (from the lifespan, as a task, so start-up does not wait for it; it also removes finished rows older than seven days) and **on an authenticated request**, after its response, at most once every `release_fanout_sweep_interval_seconds` a process (`get_current_user`; the interval is claimed when the sweep is scheduled, so a burst starts one). It is not on an unauthenticated route, a health check or the metrics. A fan-out that was cut off is finished by the next instance that starts or the next minute of traffic on a live one, with nothing new on Google Cloud.

**Not built, and named as the later fix:** an hourly authenticated scheduler call in the way of [ADR 0095](0095-loot-bot-notification-dms.md), for announcements that would otherwise wait while nobody uses the API. It is the optional layer, not the base: it needs the Cloud Scheduler API, a service account, a route that verifies a Google-signed token (`apps/api` has none), and it keeps the Neon compute awake. Cloud Tasks and Pub/Sub would add a trigger and need the same table behind them, since both deliver at least once. [ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md)'s queue and Redis are not needed.

### The cooldown

`release_cooldown_seconds` (`RELEASE_COOLDOWN_SECONDS`, default **300**, `0` is off). A release of a **public** repository is refused if the repository's newest release was made less than that long ago. The check is one indexed read of the newest release (`(tenant_id, number)`), after `lock_repository`, so two releases at once are taken one after the other (one is made and one refused), and before the digest is computed, so a refusal costs one statement. It applies to a release made by `PUT .../published`; it does **not** apply to a private repository, whose libraries were each invited; to the release made by the flip to public (it is the first as far as a library is concerned, and the flip is atomic with it, though it is the newest release for the next one); to editing a release's label or notes; or to making an earlier release current, since refusing a rollback while a bad release is out would be the wrong refusal (the rollback is announced through the same table).

The refusal is `429 release-cooldown`, with a `Retry-After` header in seconds, and in the body `allowed_at` (the time the next release is possible, as an ISO time) and `interval_seconds`. Its `detail` reads: "This repository can make its next release at 14:05 UTC. Releases of a public repository are at least 5 minutes apart." The server cannot know the reader's time zone, so it says UTC; the hub says it again in the reader's own.

Why 300: it is eight times the longest drain measured for 1,000 libraries (37 s at a 17 ms round trip) and longer than a drain of 5,000 libraries at that round trip (185 s), so one announcement is out before the next may start, and short enough that a bad release can be followed by a corrected one soon. It bounds the notices one repository can cause to 288 releases a day.

### Settings and their defaults

| Setting | Default | |
| --- | --- | --- |
| `RELEASE_COOLDOWN_SECONDS` | 300 | seconds between a public repository's releases; 0 off |
| `RELEASE_FANOUT_CHUNK_SIZE` | 250 | libraries told in one transaction (the spike's) |
| `RELEASE_FANOUT_SWEEP_CHUNKS` | 20 | chunks one sweep writes: 5,000 libraries |
| `RELEASE_FANOUT_SWEEP_INTERVAL_SECONDS` | 60 | the least time between two sweeps started by requests of a process; 0 is every request |

The API's test settings (`tests/_workers.py`) set the cooldown to 0 and the sweep interval to an hour, since the tests release the same repository again and again and a sweep triggered by a request must not drain an announcement a test is holding; the tests of this ADR set their own values. The hub's real-API launcher sets the cooldown to 0 for the same reason, and one spec runs once on a launcher at the default.

### The hub and the CLI

Studio's release dialog says the refusal in the reader's own time, with the interval, and stays open: "This repository can make its next release at 14:05. Releases of a public repository are at least 5 minutes apart." The CLI prints the API's own detail and `(HTTP 429)`, as it does for every refusal.

## What the tests pin

- The announcement is written with the release, holds the words as they were (editing the notes after changes nothing), and is gone with the transaction that rolls back; nobody to tell writes no row; a delisted repository writes none.
- The drain tells each person exactly once, the Owners and Organizers of each library and not its Authors: through chunks, stopped after a whole chunk, stopped inside one (that chunk uncommitted and the cursor unmoved), and finished by the next drain; three drains started together write each chunk once; a row held by one drain is skipped by another; two announcements of one repository are each drained once.
- Making an earlier release current and the flip to private are announced through the table, and the revoke notice reaches the libraries whose grants the flip deleted and not the libraries that were only invited.
- The sweep finishes a stranded announcement in bounded work; it is scheduled once a minute at most per process, on an authenticated request only (a health check and the readiness check start none) and after the response; the start-up sweep finishes what was left and removes a finished row older than a week.
- The table's wall: another tenant's context reads none of it, no tenant and no sweep setting reads none, the setting opens a read and no insert.
- A release at 5,000 libraries costs 56 statements and one insert of the snapshot, with no notice written and no tenant switched in the request (it was 20,054 statements).
- The cooldown refuses inside the interval with `allowed_at` the newest release plus the interval, `interval_seconds`, a `Retry-After` and the words above, and writes no release and no announcement; allows after it, and runs from the new release; never applies to a private repository, the flip, an edit of a release or making an earlier one current; two at once give one release and one refusal; 0 turns it off.
- The hub says the refusal in words with the time in the reader's zone, and never "tenant", "grant", "subscription", "stable" or "frozen"; one real-API spec runs against a launcher at the default.

## Consequences

- A release costs the snapshot and not the loop: the request no longer fails, holds the repository's row, or burns CPU in proportion to the libraries, and the notices follow in seconds in the same process or within a minute of traffic.
- **Notices can be late.** After the response, an announcement is told by a process that has CPU only by luck; the guarantee is that it is **finished**, by the next instance or the next authenticated request, not that it is prompt. With no traffic and no scheduler it waits for the next start-up or request.
- **A drain that always fails is retried every minute** by every process that sweeps (a poison row). Nothing in it can fail for a data reason today (a deleted library has no administrators), and the failure is logged each time (`release_fanout_drain_failed`).
- The rows are kept a week after they finish and removed at start-up. The notices themselves have no retention rule, and 288 releases a day at 5,000 libraries is 2.9 million rows; that is a limit of the notice table, not of this interval.
- A repository's row of `tenant` is no longer held for the length of the announcement.

## Not built

- The set-based statement the spike measured (one `INSERT ... SELECT` from the grants and `membership`, 0.56 s for 5,000 libraries): it needs a policy on `membership` that opens across tenants and a migration, and is its own decision.
- The scheduler call, Cloud Tasks and Pub/Sub, above.
- Skipping a library that lost its grant between the release and the drain: the snapshot is what is read.

## Not verified

What a Cloud Run revision does with CPU after a response and at scale-down is Google's documented rule and was not run; the round trip between Cloud Run and Neon is unmeasured, so the 300-second default rests on the spike's 17 ms; the drain on Neon's pooled connection (every statement of it runs in one transaction with a transaction-local setting, and no session-level lock is used).
