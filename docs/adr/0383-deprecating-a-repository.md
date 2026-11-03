# 0383 - Deprecating a repository

Status: accepted. Slice D8 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §7, tracked in #965. Builds on [ADR 0287](0287-who-may-read-a-public-repository.md) (the gate, and the three places that say who may read a repository), [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md) (the flips), [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (the listing), [ADR 0301](0301-release-fan-out-and-cooldown.md) (the fan-out that tells the libraries) and [ADR 0303](0303-operator-delist.md), whose shape it follows: columns on `tenant`, the gate and the policies changed by one condition, a notice for the members, a card in Studio. The choices marked *default* below were not put to the maintainer; each is the answer the RFC leans to or the smallest one, and each is listed as a question at the end.

## Context

[RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §7 asks for a state a repository can be put in, public or not: it keeps its updates for the libraries that already copied it, blocks new copies, and leaves Discover, with an optional message the libraries see. It is how an Owner retires a repository without cutting off the libraries that use it, which unpublishing does ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), and it can be undone. [ADR 0287](0287-who-may-read-a-public-repository.md) wrote "not deprecated" into the rule that decides who may read a repository and left the column for this slice.

## Decision

### What a deprecation is

A repository is **deprecated** while its tenant row says so: `deprecated_at` and `deprecated_message` (1 to 500 characters, optional). The message only with the time, and only a repository has either (a check). The columns are on `tenant`, beside `published_at` and `delisted_at`, for the reason [ADR 0303](0303-operator-delist.md) gave: the gate and the policies that decide whether a repository is open to outside readers read the tenant row, which no policy hides.

**The words.** The API and the documents say deprecated; the account hub says **retired** ("Retire this repository", "This repository is retired", "Bring it back"), because "deprecated" is a word about code. [ADR 0194](0194-user-facing-terminology.md) says a new word goes into identity §14.3 before it goes into a screen, so §14.3 gains a row for it in this change. It does not conflict with anything in [ADR 0194](0194-user-facing-terminology.md): "retire" was not in use. *Default.*

**Who.** An Owner, as the visibility flips are; no Organizer or Author. *Default.*

### What a deprecated repository does

- **It leaves Discover.** `discover.listed()`, the facets and `discover_read` gain `deprecated_at IS NULL`, so it is not in a search, a filter or a count and its storefront is the `404` of an unlisted repository, to a library that holds it as well.
- **It blocks every new copy.** `GET .../copy-plan` and `POST .../copy` are `409 repository-deprecated` for a library that can read it: one that holds only an invitation and has not copied, and one that has copied it, with or without `again` (a copy again is a new copy, and nothing is forgotten when it is refused). `detail` names the repository and the Owner's message. A repository built on a deprecated one, copied by a library that has not copied the deprecated one yet, is refused the same way, naming it; a library that already copied the deprecated one copies the other as ever. A library that cannot read it gets the `404` it got.
- **The libraries that hold it keep reading it and updating from it.** Update checks, applying updates, the browse, the preview, the dependencies and releases are all unchanged for a library with a grant: an invitation, or the grant a copy of a public repository wrote (`source = public`). The Owner goes on editing and releasing, and a release is announced to those libraries as before.
- **Visitors lose the public read of it.** The public branch of the gate is closed while it is deprecated, so a user with no library, and a library with no grant, read it as unpublished: no profile, cover, preview, browse, releases or dependencies. A library with a grant is unaffected, because the grant is a branch of its own.
- **The operator's delist wins.** A repository that is both is delisted: it reads as unpublished to every library, the holders included, and a notice of either tells nobody ([ADR 0303](0303-operator-delist.md)).

**The rule in four places.** As in [ADR 0287](0287-who-may-read-a-public-repository.md) and [ADR 0303](0303-operator-delist.md), the rule is written in four places in the database, and this changes each by one condition, in one migration, with the pre-existing definitions as the starting point of `downgrade`:

| Where | Change |
| --- | --- |
| `repository_read_tenant_id()` | the public branch needs `deprecated_at IS NULL`; the grant branch does not |
| the profile's own `repository_read` | the same, for `visibility = 'public'` |
| `discover_read` | `deprecated_at IS NULL` |
| the insert policy of `repository_subscription` | a library cannot write its own `public` grant to a deprecated repository; the repository's side still writes an invitation |

**What did not change in Python.** The mirrors of the gate in code are `reading_repository` (it asks the function, so it follows), `is_holder` (a grant, which stays the holder's mark) and `is_public`. `is_public` says whether the profile reads `public`, and decides whether a library reads the current release's document or the live rows; a deprecated public repository stays public in that sense, and its holders keep reading its release, not its edits. Making it false for a deprecated repository would hand every holder the Owner's unreleased edits, so it is not changed. A picture of a repository is as open as it was ([ADR 0300](0300-authentication-on-a-private-repositorys-picture.md)): it is a picture of a name that was public.

### Flips

- **Making a deprecated repository public** is `409 repository-deprecated` before anything is kept (it would be public and found nowhere); bring it back first. The operator's word comes first where both hold (`repository-delisted`). The Owner's flip check says so (`deprecated`) so that Studio says it before the button is pressed.
- **Making it private** is allowed, as it is for a delisted one. It revokes the `source = public` grants as any such flip does, after the same warning with the number of libraries, so libraries that copied it by themselves lose their update path then; the Owner chose that, and the repository stays deprecated.
- **Releases** keep working, and are announced to the libraries that hold it.

### The routes

Both the Owner's, under `/tenants/{tenant_id}`:

- **`PUT /deprecation`** with an optional `{message}`: retires it. Idempotent: a second call replaces the message and keeps the time it was first retired. A message is 1 to 500 characters when given, trimmed, line breaks kept (`422` otherwise); no body and `null` are no message. It answers `{message, at}`.
- **`DELETE /deprecation`** brings it back, `{undeprecated: true}`; for a repository that is not deprecated a `200` with `{undeprecated: false}`, and nothing is logged or sent.

Each change is logged in the repository's own log as `repository.deprecated` and `repository.undeprecated`, the Owner as the actor and no words of the message (the log is read by Organizers too, [ADR 0063](0063-tenant-activity-log.md)); a `PUT` that changes nothing is not logged. The command line has no command of its own: `lorenzo api PUT /tenants/<id>/deprecation --data '{"message": "..."}'` does it, and [Going public](../operations/public-launch.md) says so.

### What readers see

- **Members** (Owner, Organizer, Author) read `deprecated: {message, at}` (`null` while it is not) on `GET /tenants/{id}/profile` and its `PATCH`, in the `MemberProfileOut` of [ADR 0303](0303-operator-delist.md), and on the Owner's flip check. Never who retired it.
- **A library that holds it** reads `deprecated: {message}` (`null` while it is not) on its list of repositories, the `SubscriptionOut` its Shelf is built from, which is all of Shelf: a repository's page is that row. A delisted repository says nothing of it there, since it reads as unpublished. The library's profile of the repository is unchanged.
- **A visitor and a library with no grant read nothing of it**, as it is closed to them. The field is in no view they can reach.

### The libraries are told

When a repository is retired for the first time, and when it is brought back, the Owners and Organizers of every library that holds it are told through the fan-out of [ADR 0301](0301-release-fan-out-and-cooldown.md): the libraries are snapshotted in the transaction of the change (`announce`, types `repository_deprecated` and `repository_undeprecated`) and the notices are written after the response. A holder is a library with a grant or a copy.

- Libraries with a copy and a grant: "*Name* was retired by its Owner", "You keep your copy and its updates; it can no longer be copied.", and "Message: ..." when there is one.
- Libraries that hold an invitation and have not copied it, or a copy whose grant is gone: the same title and "It can no longer be copied.", since they have no copy to keep or no updates to take. *Default: a second announcement, so that no library is told something untrue of it.*
- Bringing it back: "*Name* is available again", "It can be copied again."

Not the repository's own members, who did it. A `PUT` that only changes the message tells nobody again. A repository that is delisted tells nobody (they read it as unpublished), and retiring it again after it was brought back is a new state and tells again.

### In the hub

- **Studio, Overview.** Every member reads a notice: "This repository is retired.", "Libraries that copied it keep their copy and its updates. It cannot be copied or found in Discover.", and "Message: ..." when there is one. An Owner has a card, "Retire this repository", that says what it does in words, takes an optional message of up to 500 characters with a counter, and opens a dialog that says how many libraries hold it (the count "Libraries using it" shows), that they keep their copy and their updates and will be told, and that it can be brought back; retired, the card shows the message and "Bring it back". The visibility card's "Make public…" is disabled while it is retired, with the reason.
- **Shelf.** A repository a library holds that is retired has a "Retired" pill and the Owner's message on its card and its page, says the library keeps its copy and its updates ("Its Owner retired this repository. Your library keeps its copy and its updates, and it cannot be copied again.") or, where the library holds only an invitation, "This repository is retired and can no longer be copied.", and offers no copy: not the button, not "Copy again…", and a link to the wizard opens the repository's page instead. Its entries, its stat groups and what its Owner opened for a look are read as before; the counts and the outline that come from a copy plan are not shown, since a plan is refused.
- **Discover and the storefront** have nothing to add, since it is not listed. Their reads (the listing, the storefront) are no longer answered from what the hub held, so a repository retired a minute ago is not offered again for the time a held answer would have lasted.
- The words are [identity §14.3](../brand/identity.md#143-terminology)'s: library, repository, copy, update, Owner, never tenant, grant or subscription. Nothing of a repository's text is read by any of it: what is shown is the Owner's message, written to be read.

## Not built

- **A successor.** RFC 0038 asks whether a deprecated repository names the one that replaces it. The message can say it, in words; a link that Discover or Shelf follows is a small addition for a later slice, once someone wants it. *Default.*
- **A command of its own** in the command line, and a screen for operators: the route is enough for the first.
- **Retiring on a schedule**, and a message the libraries can reply to.

## What the tests pin

- In the database, as the restricted role: the gate answers null for a visitor and for a library with no grant while it is deprecated, and answers for a library with an invited grant and for one whose own copy of a public repository wrote a `source = public` grant, which also reads the profile through the gated read; the profile's read, `discover_read` and the insert policy agree; delisted and deprecated is closed to everyone; the repository's side still invites; the columns are all or none, 500 characters at most, a message optional, and only a repository.
- Every reader (a visitor, a library with no grant, a library with an invitation only, one that copied by invitation, one that copied a public repository by itself, an Owner, an operator) against public, private, deprecated public, deprecated private, and deprecated and delisted, across the listing, the storefront, the profile, the cover, the releases, the preview, the browse, the stat groups, the dependencies, the copy plan, a dry-run copy, the update check and applying an update.
- Holders keep their updates: after the Owner retires it and releases once more, a library that copied by invitation and one that copied by itself check, apply and are told, and their list carries the message.
- New copies: refused for a library with an invitation only and for one that has copied it with and without `again`, which keeps what it has; `404` for a library that holds nothing, with no message in it; a repository built on a deprecated one is refused naming it unless the library copied that one before, and copies once it is brought back.
- The routes: Owner only (an Organizer, an Author and a library are refused), idempotent with the message replaced and the time kept, 1 to 500 characters, no body, bringing it back and its no-op, members' and holders' views, Discover's facets, the log with the Owner and none of the words, and the audit of the owner tier.
- The flips: made public is refused with nothing kept, delisted first where both hold; made private is allowed and stays deprecated.
- The notices: once however many times it is retired, not for members, once more when it is brought back and not for the no-op, a different body for an invitation that was not used, none while delisted, the announcement a row of libraries as they were that the drain tells.
- In the hub, against the real API: the Owner retires it through the dialog with a message and brings it back, a member reads the notice, a visitor's Discover and storefront no longer have it though they were read before, a holder reads "Retired" and the message and its update and no copy, one that holds an invitation only reads it cannot be copied, the visibility card is disabled with its reason, and at 375 pixels everything fits and the buttons are 44 pixels high.

## Questions for the maintainer

- Is **retired** the word on screen, with **deprecated** kept for the API and the documents?
- Should an Organizer be able to retire a repository? It is the Owner's here, as the flips are.
- Should the message of a repository that has been retired for some time be editable without bringing it back (which tells the libraries twice)? Here it is one `PUT` with a new message and no new notice, and the hub offers it only on the way in.
- Is a **second announcement** for a library that has not copied the repository the right reading of "the libraries that hold it are told", or should every holder read one text?
- Should **making it private** be refused, or warn more, while it is deprecated, since the libraries that copied it by themselves lose the updates this state promises them?
- Does a **successor** link belong in v1.0?

## Consequences

- An Owner can retire a repository in one call, the libraries that use it keep working and are told, and the repository stops being offered to anyone new; undoing it is one more call.
- The rule that decides who may read a repository is, once more, written in four places in the database and tested against each other; this slice changed all of them by one condition, on the row nothing hides.
- One migration: two columns and a check on `tenant`, the gate, and three policies.
- A deprecated repository is closed to everyone who holds no grant to it and refuses every new copy, so a stack that includes one cannot be copied afresh until it is brought back or the library already has it.
- The libraries' update path from a deprecated repository is untouched, so a repository that is made private after being retired still cuts off the libraries that copied it by themselves, as any such flip does.
