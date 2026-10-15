# 0299 - What a public repository says about its publisher, and hides about the libraries that copied it

Status: accepted for build, 2026-10-15. Slice D6c of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) (§6 items 4 to 6), tracked in #746. The wording of the terms line was approved by the maintainer on 2026-10-16. Builds on [ADR 0204](0204-the-owner-sees-who-copied-a-repository.md) (the Owner sees who copied a repository), [ADR 0287](0287-who-may-read-a-public-repository.md) (a library copying a public repository gives itself a grant), [ADR 0290](0290-the-flips-as-routes-and-the-visibility-switch.md) (the flips and the Make public dialog) and [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (Discover and the storefront).

## Context

A public repository is copied by libraries its Owner never invited, and read by strangers. [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §6 asks for three things before `public` is accepted, none of which changes how a private repository works:

- the Owner sees how many libraries copied it and never which ([ADR 0204](0204-the-owner-sees-who-copied-a-repository.md) lists every library with a grant or a copy, by name, which for a public repository would be a directory of who plays what);
- a storefront and a Discover result say who published it, from accounts and not from text the repository writes about itself;
- a storefront has a way to report it, and the dialog that makes a repository public carries a line the Owner agrees to.

## Decision

### What a repository learns of the libraries that copied it

A library is **named** to a repository's Owners and Organizers when the repository invited it: it holds an invitation, or it held one that was stopped and still holds a copy ([ADR 0204](0204-the-owner-sees-who-copied-a-repository.md)'s case). A library that **copied a public repository by itself** is counted and never named.

- **`GET /tenants/{id}/subscribers`** lists the named libraries and no others. Its shape does not change.
- **`GET /tenants/{id}/subscribers/summary`** is the additive sibling: `{named, public_copies}`, for the Owners and Organizers. The list stays a plain page, as every client reads it; a wrapper with one more field would have changed the type each of them parses. `named` is how many the list holds, `public_copies` how many copied it by themselves.
- **What counts as a public copy.** A library whose grant has `source = public`, and a library that holds a copy and no grant at all that the repository's own activity log does not name (`repository.granted` or `repository.revoked` with that library as its target). The second case is what a repository going private leaves behind: its public grants are revoked ([ADR 0289](0289-the-flip-rules-and-the-bridge-skew-gate.md)) and the copies stay, and a copy with no grant would otherwise be indistinguishable from one whose invitation the Owner stopped. The log says which: the Owner already knew the second library, since they invited it and stopped it, and never the first. The copy record has no source of its own, and no migration is made for it.
- **The repository's log** records a public copy as `repository.copied_publicly`, with no actor, no target and no detail: that a library copied it, and nothing that says which or who in it. It is written once for each repository the copy subscribed the library to, a bridge's upstreams included. The library's own log keeps its own record (`repository.subscribed`, `repository.copied`) as for anything it does.
- **The grant is not the repository's to end or to know by id.** `DELETE .../subscribers/{id}` for a grant a library gave itself answers `404 subscription-not-found`, as for a library that has none. `PUT .../subscribers/{id}` for such a library invites it: its grant becomes an invitation (a new row, logged and told as any invitation), the answer is `201` as for any new invitation, and it says nothing of whether the library had copied the repository by itself. That completes the rule of [ADR 0287](0287-who-may-read-a-public-repository.md) that an invitation outranks a public copy, which only wrote the first half.
- **Nothing else names them.** No notification is made to an Owner when a library copies (none was), the flip-check and the going-private warning say numbers, and the activity log carries the entry above. The public repositories built on one, which going private is refused for, are repositories and are named as before: a public repository is listed by name in Discover.

Studio's **Libraries using it** lists the named libraries as before and, under the summary, one line when there are public copies: "1 library copied it by itself from Discover. Their names are not shown: you see how many, not which." ("N libraries copied it by themselves from Discover." for more.) With no named library and a public copy the summary says "No library is invited to it."; with neither it says what it said. `lorenzo repo subscribers` prints the same line under its table and from the same route; its `--json` array is unchanged.

### The publisher

Each of a storefront and a Discover result carries `publishers: [{display_name}]`, additive: the Owners of the repository by their accounts, in the order they became Owners, at most five. The name is the account's display name, else its nickname, else "A Lorenzo account" for an Owner with neither. It is never read from the profile, its credits, its description or its summary, so a repository cannot claim to be somebody else's. Organizers and Authors are not publishers.

A reader of Discover is in no tenant and a membership is its tenant's own row, so the Owners of each repository are read under that repository's context, one repository after another, and the reader's context is put back; what leaves is the names. That is two statements for each repository: a page of 50 results costs about 100 ms more than it did (measured on a local database, 240 to 260 ms against 140 to 160 ms), a page of the hub's default 20 about 40 ms. A cache, or one statement for the whole page, is a change to make when that cost matters.

The hub says it as "Published by Ada Author, Bob" under a result's summary and under a storefront's, and as small print, not as a field the Owner fills.

`GET .../flip-check` carries the same `publishers`, so that the dialog can say whose names are shown.

### The report link

`report_address` is a setting (`REPORT_ADDRESS`, unset by default). `StorefrontOut.report_mailto` is a `mailto:` to it with "Report a repository: *name* (*id*)" as the subject, every part percent-encoded, built by the server, and null while the setting is unset. The hub shows "Report this repository", a plain link, under the credits, only when the answer is a `mailto:`; there is no report inbox in Lorenzo.

### The terms line

`PUT /tenants/{id}/public` takes `accept_terms`, and answers `422 terms-not-accepted` ("Agree to the terms to make it public") without `true`, keeping nothing, after the answer that public repositories are not available and before everything else. A client that does not send it, as every client written before this was, is refused; the one in this repository that sends it is the account hub's dialog. A flip that is made records `repository.terms_accepted` in the repository's activity log with the user and no wording, in the transaction that makes it: a flip refused for anything else logs no agreement. The wording is the dialog's and may change, so it is not stored.

**The maintainer's wording, approved on 2026-10-16**, kept in one constant in the hub (`TERMS_LINE` in `lib/visibility.ts`) and written once in the API's documentation of `accept_terms`:

> I have the right to publish this repository. Publishing cannot be recalled: libraries that copied it keep their copies.

The Make public dialog shows it as a checkbox the Owner ticks, after the release's fields and before the last button, and says before it which account names are shown: "People will see who published it, by the name of your account: Ada Author. You can change it in your profile." (for several Owners, "by the names of the accounts of its Owners: Ada, Bob. Each Owner can change theirs in their profile."). The last button checks the summary first, then the box ("Tick the box to agree before you make it public."), then the release.

`lorenzo` has no command that makes a repository public, so none sends `accept_terms`; `lorenzo api` sends whatever a script says.

## What the tests pin

- The list names the invited and no library that copied a public repository, the summary counts the others, and neither the list, the log, the Owner's notifications nor any answer holds the library's name or id; the log has a `repository.copied_publicly` entry with no actor, target or detail, and the library's own log keeps its record.
- A repository made private keeps its public copies as a count, and a library invited and then no longer invited is still named while it holds a copy.
- A grant a library gave itself is `404` to a revoke and becomes an invitation, answered `201`, when the Owner invites the library.
- The summary is for Owners and Organizers, a stranger and a library's Owner get `404`, and the audit of routes lists it.
- A storefront and a listing say the Owners' accounts, by display name or nickname, five at most, and the profile's summary, credits and the repository's description do not change them; an Owner with no name is "A Lorenzo account"; reading them leaves the reader in no tenant.
- `report_mailto` is null while the setting is unset, and with it set is a `mailto:` to the address with the name and id in the subject, encoded.
- `PUT .../public` without `accept_terms` is `422 terms-not-accepted` and keeps nothing, with it logs `repository.terms_accepted` once with the user and no detail, and a flip refused for another reason logs none.
- In the hub, against the real API: Libraries using it names the invited library, says one number and no name for the public copy, and the Activity tab holds neither the name nor the id; a result and a storefront say "Published by", whatever the credits say; the Report link is there where an address is set and not where the answer has none; the dialog says whose account is shown and asks for the box; and the storefront at 375 pixels fits with its Report link pressable. In unit tests: the lines, the checks and the body of the dialog, the summary lines and `publishedByLine`/`reportHref`.
- The CLI's `repo subscribers` says the number and never a name.

## Not in scope

- **Anything in the database the repository's side could read.** `repository_subscription.created_by` and `repository_copy.copied_by` of a public copy are the copying user, readable by the repository's own context at the SQL level as ADR 0204 made the copy rows, and no route returns them. Stripping them is a migration, and RFC 0038 asks only that what the API answers does not name.
- **Showing who published it from a profile field.** The Credits stay a field of their own.
- **A report inbox, and what is done with a report.** A takedown process is a future matter ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §8).
- **A command that makes a repository public.** Not in the CLI; the terms line is the dialog's.

## Consequences

- An Owner of a public repository sees how many libraries use it and which ones they invited, and nothing that identifies the rest.
- A client that makes a repository public has to send `accept_terms`; the only one in this repository is the dialog, which asks for it.
- `GET /subscribers` no longer lists a library with a public grant, which it did when nothing could make one. A caller that wants a count reads the summary.
- Reading the publishers adds two statements for each repository a Discover page shows.
- No migration.
