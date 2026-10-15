# 0303 - Operator delist

Status: accepted. Slice D6a of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §6 item 1, tracked in #744. Builds on [ADR 0057](0057-platform-operations.md) (the `platform-operator` role, `/admin` and account suspension), [ADR 0287](0287-who-may-read-a-public-repository.md) (the gate, and the three places that say who may read a repository) and [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (the listing, which this adds a condition to).

## Context

[RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §6 asks for a lever: "an abusive repository can be dealt with without editing the database". An operator takes a repository off Discover, with a reason; it closes to new copies and reads as unpublished to everyone but its members and the operators; libraries that already copied it keep their copies; suspending an account delists the repositories it owns. It is not a takedown process, which the RFC leaves as a future matter. Two questions were open, and the RFC proposed answers that are taken here.

## Decision

### What a delisting is

A repository is **delisted** while its tenant row says so: `delisted_at`, `delisted_by` (the operator's account, `ON DELETE SET NULL`) and `delist_reason` (1 to 500 characters). All three or none, and only a repository has them (a check). The columns are on `tenant`, beside `published_at`, and not on `repository_profile` as RFC 0038 §2 first put them, for one reason that came out of building it: **a policy that has to know whether a repository is open to outside readers must read a row that no policy hides.** The gate (`repository_read_tenant_id()`) is asked by a library that holds a grant and by a request in no library; the profile row of a delisted repository would be invisible to exactly those readers (the profile's `repository_read` policy hides what is closed), and a hidden row reads as "not delisted". Leaving the profile visible to the gate would give every holder a way to read a delisted repository's profile and reason in the gated read, and the operators' own list would need an opening of its own in the wall of [ADR 0002](0002-multi-tenancy-shared-schema-rls.md). On `tenant`, which has no policies, the gate, the three policies and the listing each read one fact in one place, next to "published".

### Who reads a delisted repository

It reads as unpublished, to everyone but its own members, and the operators' list. In code, `delisted_at IS NOT NULL` is one more condition wherever `published_at IS NOT NULL` decides:

- **The gate**, `repository_read_tenant_id()`, answers null. Every content table's `repository_read` policy calls it, so a library that holds a grant (invited or by a copy), a library that holds none and a request in none read nothing, and a route that asks `reading_repository` is told "not allowed" and answers the `404` it answers for a draft.
- **The three places that say it in the database** ([ADR 0287](0287-who-may-read-a-public-repository.md)) gain the condition: the profile's own `repository_read`, `discover_read` (the listing), and the insert policy of `repository_subscription`, so a library cannot write its own `public` grant to a delisted repository. The repository's side still writes an invitation, whatever state it is in; the library it invites reads nothing until the repository is listed again.
- **The listing**, `discover.listed()` and the facets, leave it out: it is not in a search, a filter or a count, and its storefront is the `404` of an unlisted one.
- **The preview, the browse, the profile, the cover, the releases and the dependencies** are all gated reads, so they close with it, in a visitor's form and a library's.
- **Copies.** The copy planner treats a delisted repository as not published (`Step.published`, from the tenant row), so a plan, a dry run and a copy of it are `404` for any library, and so is the update check and applying updates (`compute_updates` is a gated read). A library's own list of repositories shows it with `published_at` empty and no current release, and the hub's Shelf reads that as not published.
- **What libraries are not told.** A release of a delisted repository, and making an earlier release current, tell no library: it is something they cannot read.

Its **members** (Owner, Organizer, Author) read it through their own tenant, which delisting does not touch: profile, entries, releases, the log, the people, the showcase. They edit it and release it as ever, because they have to be able to fix it. They are told that it is delisted: `GET /tenants/{id}/profile` and its `PATCH` answer with `MemberProfileOut`, the profile and `delisted: {reason, at}` (`null` while it is listed), and `GET .../flip-check` (the Owner's) carries the same field. A visitor's and a library's profile is the plain `RepositoryProfileOut` and has no such field at all (they cannot read a delisted repository), and it never says who: the operators are "the platform's operators", never a person. **Operators** do not read a repository's content as operators: [ADR 0057](0057-platform-operations.md) rules out a "God-mode" read, and delisting does not add one. They find it, with its reason, in `GET /admin/repositories/delisted`.

### Making it public while delisted

`PUT .../public` is `409 repository-delisted`, in words that name the reason ("The platform's operators took this repository off Discover, so it cannot be made public until they list it again"), before anything is kept. A repository that is public and delisted can still be made private (`DELETE .../public`), the safe direction, which stays delisted. Studio's card uses the flip check to say so before the button is pressed.

### The operators' routes

All in `routers/admin.py`, behind `platform-operator`:

- **`PUT /admin/repositories/{repository_id}/delist`** with `{reason}`: delists. Idempotent: delisting a delisted repository updates the reason and the operator, keeps the time it was first delisted, and is logged again; the Owners are told once, the first time (a later reason is on the page and in the log, not another notice). `404 repository-not-found` for an id that is not a repository, library ids included.
- **`DELETE /admin/repositories/{repository_id}/delist`** lists it again. No-op, still `200`, with `relisted: false` where it was not delisted (nothing is logged or sent).
- **`GET /admin/repositories/delisted`**, a page, latest first: `id`, `name`, `slug`, `reason`, `delisted_at`, `delisted_by` and `delisted_by_nickname`. Operators read who; members never do.

Each change is logged in the repository's own activity log as `repository.delisted` and `repository.relisted`, with the operator as the actor and no words of the reason (the log is read by Organizers too, and holds ids and field names only, [ADR 0063](0063-tenant-activity-log.md)). Its Owners (not its Organizers or Authors) get a notification: "*Name* was taken off Discover and closed to new copies", with "Reason: …" and "Libraries that copied it keep their copies, and cannot update from it until it is listed again."; and, on relisting, "*Name* is listed again". Neither names the operator.

### Suspending an account

`PUT /admin/users/{id}/suspend` also delists **every repository the account is an Owner of**, with the reason "Its Owner's account was suspended", in the same transaction as the suspension. A repository it only organises or authors is not its own and is left as it is; one with another Owner is delisted all the same (the account that is suspended is one of its Owners, and the other Owners are told). A repository that an operator had delisted already keeps the operator's reason and time and tells nobody twice. Suspending again does the same. **Lifting the suspension does not list them again**: an operator does, with the same call as for any repository.

Reading the repositories an account owns is a read of its memberships, which RLS ([ADR 0022](0022-user-tenant-membership.md)) shows to the tenant they are in or the user they are of, and the operator is neither. The read is made as the user it is about, for that one query (`app.user_id` is set to the account's id, then put back to the operator's), the one place an operator's request reads another user's memberships, and only their Owner role on repositories.

### The two questions the RFC left open

- **What a delist does to libraries that already hold the repository.** The copies stay, and update checks and reads by libraries stop, since an update check serves the content again. The other reading, updates continue and only discovery stops, would leave an abusive repository serving its content to the libraries that hold it, which is what a delist is for.
- **Which repositories a suspension delists** when the suspended account is one Owner of several: all of those where it is an Owner, and none where it is not.

## What the tests pin

- Every reader against public, private and delisted: a visitor and a library's holder (invited), in Discover, the storefront, the profile, the cover, the releases, the preview, the browse, the stat groups, the dependencies, the copy plan and a dry-run copy; a repository's Owner reads all of its own.
- In the database, as the restricted role: the gate answers null for a delisted repository whether the library holds a grant, holds none or is in none, and answers again once it is listed; an invited library of a private repository is closed too; the profile is not in the gated read; `discover_read` leaves it out; a library cannot write its own grant to it; the repository's own side still invites; the columns are all or none, 500 characters at most, a reason required, and only a repository.
- A delisted repository blocks new copies by a library with no invitation and by the invited one, and writes no grant; libraries keep their copies and their copy records, update checks and applying updates are `404`, their list shows it as not published, and a release of it tells no library; listed again, the update check serves the release.
- Members read the reason and the time and never a name; the Owner edits the profile and releases; an Author changes entries; a visitor's and a library's profile and the storefront never carry it.
- The routes: operator-only (`403` otherwise, and an audit of every `/admin` route for the role), idempotent delist with the reason updated and the first time kept, a reason of 1 to 500 characters, `404` for an id that is no repository, relist and its no-op, the page and its fields.
- The Owners are told once however many times it is delisted, an Organizer and a library are not; relisting tells them; the log has each change with the operator and none of the words.
- Delisted, a repository cannot be made public (`409`, nothing kept, the flip check says why), can be made private, and leaves Discover's facets.
- Suspension delists the repositories the account owns and not those it only organises, authors or plays in, tells a co-Owner once, is idempotent, leaves an operator's earlier reason, is not undone by lifting it, and an operator relists with the same call.
- In the hub, against the real API: every member reads the notice with the reason, an Owner's card cannot make it public and says why, the repository is edited and released as ever, and at 375 pixels the notice fits.

## Not in scope

- **A takedown process**: who may ask, how a complaint is judged, an appeal, what the Owner is told beyond the reason. RFC 0038 §8 leaves it, and this is the lever it would use.
- **An operator screen.** Operators use the API, and `lorenzo api` for scripts.
- **Reading a repository's content as an operator.** [ADR 0057](0057-platform-operations.md) is unchanged.
- **Relisting on its own**, a time limit, and a reason that libraries can read.

## Consequences

- An abusive repository can be taken off Discover, closed to copies and to updates, and its Owners told, with one call, and an operator can undo it with one more.
- The rule that decides who may read a repository is, once more, written in four places in the database and tested against each other; this slice changed all of them by one condition, on a row nothing hides.
- One migration: three columns, a check, two partial indexes, the gate and three policies.
- A delisted repository is `404` to a library on every route that reads it, the update check included, and the libraries that copied it have no update path from it until it is listed again; they keep what they copied.
