# 0287 - Who may read a public repository

Status: accepted, decided with the maintainer on 2026-10-14. Slice D2 of [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md), tracked in #702. Builds on [ADR 0286](0286-the-read-switch-for-public-repositories.md) (what is read of a public repository: its current release), [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) (the `visibility` column and the `source` of a grant) and [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (the gated read, which this extends).

## Context

[RFC 0038](../rfcs/0038-public-repositories-and-discovery.md) §3 says three things about a public repository: any signed-in user may read it, with no library, role or grant; copying it subscribes the library to it, and to every repository it is built on, as the library's own act; and the rule that makes that safe, that every repository in a stack is public, is enforced when a repository is made public. [ADR 0286](0286-the-read-switch-for-public-repositories.md) made the library's reads of a public repository go through its current release. This slice makes the gate let a reader in, with the routes to use it and the copy that subscribes. `public` is still refused by the API ([ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md)), so nothing in a deployment is public yet: D3 to D6 add the rest of what must stand before it is.

## Decision

### The gate

`repository_read_tenant_id()` returns the requested repository when it is a published repository and either the current tenant holds a grant to it or its profile says `public`. Nothing else about it changes, as the RFC asks: still asked for with `reading_repository` and never ambient, still `FOR SELECT`, and a draft, a private repository and one that does not exist are all the same `null`. The public branch is independent of the current tenant, so a user with no library reads through it.

**Why the profile's own policy changed.** The function now reads `repository_profile`, and the profile's `repository_read` policy called the function: a policy that reaches its own table through a function is an infinite recursion for Postgres, whatever the query. The profile's `repository_read` is written out instead (the requested repository, published, and public or granted) and does not call the function; every other table's still does. The function, the profile's policy and the insert policy below say the same rule in three places, and the tests run them against each other.

**Why not a flag on `tenant`.** The one table with no policies would break the recursion without touching the profile's, at the price of a second place that says whether a repository is public, kept in step by a trigger. A rule written out three times in the database and tested was judged better than one fact stored twice.

**What is not in the gate yet.** RFC 0038 says "public, published, listed, not delisted and not deprecated". Listing, delisting and deprecating are D3, D6 and D8, and add their columns and their condition here when they are built. "With at least one release" is not in the gate either: the policy cannot read the release table without the same recursion, and the reads answer `409 public-repository-has-no-release` ([ADR 0286](0286-the-read-switch-for-public-repositories.md)) for a repository without one.

### A request in no library

RLS policies cast `app.tenant_id` to a uuid, so a request that has none fails on the first table it touches, not with an empty result. A request with no library sets it to an id no tenant has (`NO_TENANT`, all zeros), through `get_public_reader`, which also asks for a signed-in user. Nothing of any tenant is visible to it, and a public repository is read through `reading_repository` like any other.

### The routes

Under `/repositories/{repository_id}`, for a signed-in user with or without a library:

| Route | What it answers |
| --- | --- |
| `GET .../profile`, `GET .../profile/cover` | The profile and cover the Owner wrote |
| `GET .../releases` | The releases, newest first |
| `GET .../entities`, `GET .../stat-groups` | What to browse, at the current release ([ADR 0286](0286-the-read-switch-for-public-repositories.md)) |
| `GET .../dependencies` | The repositories it is built on, dependencies first, each with whether it is public |

They are the library's own reads (`/tenants/{id}/repositories/{repository_id}/...`) without the tenant, sharing their code: the handlers of both call one function each, which takes the error to raise for a repository the reader may not read. A user's `404` says "No public repository", a library's says what it said. A library with no grant reads a public repository through its own routes too, as the gate lets it, and a private one stays `404` for it.

`GET .../dependencies` answers a smaller object than the library's, `PublicDependencyOut` (id, name, slug, public): the library's `invited` and `copied` are about a library, and there is none. Whether each is public is whether the stack can be copied in one action.

Not here, by the RFC's own order: the Discover listing and search (D3), the preview of a repository's entries (D4), and what a repository's Owner sees of who copied it (D6).

### Copying subscribes the library

`POST .../copy` of a repository the library holds no grant to, but which is public, writes the copy as for any other and then a grant of the library's own, `source = public`, to each repository of the copy that it did not hold a grant to: the repository and every repository it is built on. One action, in one transaction, by a member who may copy (an Owner or an Organizer: an Author may not, as ever, because copying changes what the library holds). A step is *readable* when it is published and the library holds a grant or it is public; a copy is refused with `409 repository-copy-needs-grants`, and nothing written, unless every step is, so a stack with one private repository is not copied half. The Owner of the private one invites the library as before, and the rest are the library's own grants.

- **An invitation outranks a public copy.** A library that holds an `invited` grant keeps it; no second row is written, and a repository going private later does not cut off a library it invited.
- **A dry run writes none.** It rolls back like the rest.
- **After the copy it is an ordinary subscription**: it is listed with the library's repositories, updates and gives up like one (the copy stays when the grant goes, as for any revoke).
- **The insert policy.** `repository_subscription_grant` had one case, the repository writing an `invited` grant. It has a second: the library writing its own, `source = 'public'`, to a repository that is published and whose profile says `public`. The write is made inside the gated read of that repository, which is where the database lets the library see that it is, and a library cannot write an `invited` grant, a grant for another library, or a public one to a private repository or a draft.
- **Said to nobody.** `grant_repository_access` tells the library's members and logs it for the repository. A library giving itself a grant tells the repository's Owner nothing here (what they see of public copies is RFC 0038 §6, D6), and logs `repository.subscribed` with `source=public` in the library's own activity.
- **Revoking a public grant when the repository goes private** is the flip's ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §6, slice R8), not the gate's: until then a `public` grant row reads the repository like any grant.

### What the answers gain

`GET .../copy-plan`, `POST .../copy` and `GET .../dependencies` of a library name a `public` flag for each step, next to `granted`: it can read it without an invitation. `repository-copy-needs-grants` lists it too. The additions are to responses, so they break no client.

## What the tests pin

- The gate: a grant reads a private repository and nothing else does; a published public one is read, inside the gated read only, by a library with or without a grant and by a request in none; a draft or a private one is not; a library cannot write an `invited` grant or one for another library, a public one only to a public published repository, and the repository's side still writes `invited` only; and the read is still asked for and never ambient.
- The routes: a user with no library reads the profile, releases, entries, stat groups and dependencies of a public repository, at its release and not at what its author edited since; a private repository, a draft and one that does not exist are the same `404` for a user and for a library; a public one with no release is `409`, its profile still readable; reading needs a signed-in user; a library with no grant reads it through its own routes.
- Copying: a public repository is copied with no invitation and the library holds a `public` grant, lists it, updates it and may give it up, keeping the copy; an invitation stays; a dry run writes no grant; an Author is refused; a public stack of three copies in one action with a grant to each; a stack with a private repository copies nothing and grants nothing, and copies once the Owner invites the library, with the invited one left `invited`.

## Not in scope

- **Listed, delisted and deprecated**, and Discover: D3, D6, D8.
- **Who may see a public repository's entries before a library copies it**, and the showcase: D4.
- **Making a repository public**, the flips, the rule that every repository of a stack is public, and what a repository going private does to `public` grants: D5 and [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) R8. `public` stays refused until they are in.
- **What the Owner sees of public copies**, quotas, abuse limits and the terms: D6 and D7.

## Consequences

- A public repository can be read, browsed and copied by anyone who may copy into a library, with no invitation, and what they read is a release, never a draft.
- A repository's content is still never readable by accident: the read has to be asked for, and the gate lets in only what is published and either granted or public.
- The rule that decides whether a repository can be read is written in three places in the database. A change to it (the listing and the delisting are two) is made in all three and found by the tests if it is made in one.
- One migration: the function, the profile's policy and the insert policy. No table changes.
