# 0202 - Studio: My repositories

Status: accepted, decided with the maintainer on 2026-10-07. Slice T1 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #517. Builds on [ADR 0178](0178-account-hub-repositories.md) (repositories in the hub), [ADR 0175](0175-me-says-what-you-may-create.md) (who may create one), [ADR 0194](0194-user-facing-terminology.md) (the words) and [ADR 0195](0195-brand-phone-base.md) (the phone base). Part of the v1.0 row "Publish, subscribe, update screens".

## Context

[ADR 0178](0178-account-hub-repositories.md) put repositories on `/tenants`, in a group beside libraries, with the library page's component doing for a repository what it could: rename it, manage its people, show "Draft" or "Published". [RFC 0036](../rfcs/0036-repository-tooling.md) names where a repository is run **Studio**, under the label **My repositories**, with a page per repository and tabs for what its owner does. This is its first cut, on the API as it is: creating a repository, an Overview, and People, with the meaning of each role written next to the people who have it.

Two things were wrong with the arrangement on `/tenants`. A repository's page was a library's page with parts left out, so everything a repository will need next (a publish dialog, libraries using it, releases) had no place to go that a library did not also have. And the people panel said "orga", which is a column value, not a word ([ADR 0194](0194-user-facing-terminology.md): Owner, Organizer).

## Decision

### A page of its own

`/studio/`, in the header as **My repositories** for anyone who works on a repository or whose account may create one ([ADR 0175](0175-me-says-what-you-may-create.md)). It is laid out like `/tenants`: the repositories a person works on as a list, with **New repository** in it where they may make one, and the open one beside it. The address says which: `?repository=<link name or id>`, or `?new=1` for the form. Both are plain links, so a link, Back and a reload land where they were. Only the open repository is loaded. With one, it opens; with none and the account allowed to create, the form; with none and no right to create, one sentence saying so.

**Create** is the form that was on `/tenants`, for a repository only, shown only where `GET /me` says the account may create ([ADR 0175](0175-me-says-what-you-may-create.md)); creating a repository stays behind the `tenant-creator` platform role. A repository made opens on its Overview.

### A repository's page

Name, link name, role and description, the picture for those who edit, and **Edit repository** (the form libraries use, with the same stale-edit check). Two tabs.

- **Overview.** Its state in words, from `published_at`: **Draft** ("Libraries it has been offered to cannot look inside it or copy it until you publish it") or **Published** with the day. On a published repository, a persistent **Live** notice: "Libraries that copy from this repository see your edits when they next check for updates." That is true today ([ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md): publishing is an announcement and reads are live) and stays true for private repositories after the work in the other RFCs. Publishing and inviting a library stay on the command line until their own screens (T2, T3), and the page says so, naming the two commands.
- **People.** Everyone with a role on the repository, and under a heading, what each role means: an **Owner** has full control (publishes it, invites libraries, adds and removes people, edits its content); an **Organizer** edits the repository and its content and cannot publish it, invite libraries or change who works on it. These are what the API enforces: publishing, unpublishing, granting and revoking a library, and changing memberships are an Owner's alone ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)); editing is an Owner's or an Organizer's. One sentence says that, until there is a role for people who only write content ([RFC 0040](../rfcs/0040-authors-and-invites.md)), an Organizer is the one who edits. An Owner gets the people panel that libraries use, with its roles in the glossary's words (**Owner**, **Organizer**: the option values stay `owner` and `orga`), to add a person, change a role, remove someone and invite in bulk. An Organizer, who the API lets read the roster, gets the list and nothing to change it with. **Leave this repository** is here, in the words of a repository ([ADR 0178](0178-account-hub-repositories.md)).

Other tabs come with their slices: Profile, Built on, Releases, Libraries using it. A tab that has nothing in it is not drawn.

### What moves out of `/tenants`

`/tenants` lists libraries. Its **Repositories** group, the **New repository** item and the repository branch of its component are removed, since Studio does all of it. An address that names a repository (`/tenants/?tenant=<slug>`, which notifications and old links use) goes to Studio, as does `?new=repository`, so no link breaks. The home page's "Your repositories" links to Studio. `/beings` keeps showing a repository's beings for reading, as before.

### Words

"Owner" and "Organizer" label the roles in the people panel, for libraries too, since it is one component; the sweep of the rest of the hub's surfaces is [G2](../rfcs/0036-repository-tooling.md). A repository's page says "link name" nowhere new: the form still asks for a slug, which G2 renames.

### How it is built

Decisions that are plain functions with unit tests (`lib/studio.ts`): the addresses, the role labels and meanings, the state of a repository, what an Owner may change. The page is a `StudioPanel` component (list and form) and a `Repository` component (the page of one), each with a renderer, reusing the components libraries use: the edit form, the picture, the people panel, leaving. A cache warmer reads a repository and its people when a link to it is hovered.

### Tests

Browser tests against the real API and a fake Authgear, in the hub's CI suite ([ADR 0196](0196-shelf-the-repositories-list-and-page.md)): an account that may create makes a repository which opens on its Overview; one that may not is told so; People for an Owner (roles explained, change a role, remove someone) and for an Organizer (read only); a published repository and its Live notice; renaming and leaving; `/tenants` without repositories and its addresses going to Studio; and 375px. They replace the tests of `repositories.spec.ts` that were about the old arrangement, which had been among the specs that went stale ([ADR 0196](0196-shelf-the-repositories-list-and-page.md)); what in that file is about `/beings` and the pages about playing stays, still waiting to be repaired.

## Not in scope

- **Libraries using it, built on, the activity log** (T2), **the publish dialog** (T3), **releases** (T4), **the profile** (T5), **view as a subscriber** (T6), **the visibility switch** (T7).
- **The Author role and invite links** for people ([RFC 0040](../rfcs/0040-authors-and-invites.md)).
- **A count of libraries on the Overview.** The invitation list says whom a repository is offered to, not who copied it; the table of T2 is where that belongs.
- **Anything in `apps/api`.** Every read and write used is already served.

## Consequences

- A repository's owner has one place to run it, and the next slices have somewhere to put what they add.
- A library's page no longer carries a repository's code; the component of libraries is simpler.
- Anyone who had `/tenants` open on a repository, or a link to one, lands in Studio on the same repository.
- The people panel reads Owner and Organizer in libraries too, a small step of G2 that cost nothing.
