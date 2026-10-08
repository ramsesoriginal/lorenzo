# 0196 - Shelf: the repositories list and a repository's page

Status: accepted, decided with the maintainer on 2026-10-07. Slice S2 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #503. Builds on [ADR 0195](0195-brand-phone-base.md) (the phone base and the outline) and on [ADR 0194](0194-user-facing-terminology.md) (the words). Part of the v1.0 row "Publish, subscribe, update screens".

## Context

The API has everything a library admin needs to look at repositories: the list (`GET /tenants/{id}/repositories`), what a copy would bring and what a repository is built on (`copy-plan`), the names a repository holds (`entities`, `stat-groups`). The command line uses all of it ([ADR 0159](0159-lorenzo-repo-commands.md)). The hub uses none of it: account-hub lists the repositories you are a member of, for their owners ([ADR 0178](0178-account-hub-repositories.md)), and a library's admin has no screen that says which repositories are on offer or what is inside one.

## Decision

### The page

A page of the account hub at `/repositories/`, linked from the header as **Repositories** for anyone who owns or organizes a library. "Shelf" stays what it is called when talking about it, not the label ([RFC 0036 §1](../rfcs/0036-repository-tooling.md)). It follows the hub's pattern: a thin `.astro` page and a `RepositoriesPanel` component of markup with `data-*` hooks and `<template>`s, painted by a renderer, with reads through the hub's cache and warmed on hover.

- **A library at a time.** A person who runs more than one library chooses it from a list at the top; with one, the list is not shown. The address says which: `?tenant=<library slug or id>`, and `&repository=<id>` for a repository's page. Both are plain links, so they can be opened in a new tab, shared and gone back to; a plain click moves within the page and keeps the address true.
- **Owners and Organizers.** The list is the library admin's; a player or a GM who is neither has no library here, and sees a sentence saying so.

### The list

One card per repository the library is invited to or has copied, with its picture (or its first letter, until the picture has loaded, since a repository nobody gave one answers "not found"), its name, the first line of its description and a state. The state comes from the list alone, in words:

| State | When |
| --- | --- |
| Not copied yet | invited, published, nothing copied |
| Copied | copied, and nothing was published after the last update |
| Update announced | published after the library's last update (copying counts as the first) |
| No longer offered | the invitation is gone; the copy stays |
| Not published | invited, but the owner has not published it or has unpublished it |

"Update announced" is exactly what `published_at` against the last update can say, so it is an announcement and not a count: counting what changed needs the updates check, which is one repository at a time, and whether a badge for a whole library can be exact is the scale spike's result ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) R2). Repositories with news come first, the rest by name. A library with none says what to do: ask the owner of a repository to invite it.

### A repository's page

Its name, picture and state; one sentence that says what the state means and what follows from it; its description, rendered as LorenzoScript like every other description in the hub; and then, where they can be known:

- **What is inside**: counts of entries, stat groups, stats, and descriptions and notes, and one sentence for attachments, which have no noun in the interface ([identity §14.3](../brand/identity.md)). The counts are the copy plan's step for this repository, which is only there for one that is offered and published; for any other the API answers "not found", and the page shows that as a state, not a failure. It says plainly that only names show until the library copies the repository.
- **Built on**, as an `.outline` ([ADR 0195](0195-brand-phone-base.md)): this repository, and beneath it each repository it is built on, in the plan's order, with its state in words: Copied, Invited not copied, Not invited, Not published. A node the library cannot take in says whom to ask. The plan lists every repository a copy needs, and a repository that builds on another has already copied that one's own dependencies ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)), so what the plan lists are all direct and the outline is one level deep; it does not invent a chain the API did not give. A repository the library has no invitation to at all is only in the plan once the dependencies endpoint of RFC 0036 (A2) exists, so until then the outline shows what the plan returns.
- **Your library and this repository**: when it was invited, copied, last updated and published, and what the copy brought.
- **Entries** and **Stat groups**, two sections that read when opened. Entries are paged, searchable by name, and show each entry's kinds and what it inherits from by name; a parent that has not been loaded yet is counted, never shown as an id. Stat groups show their stats, with an enum's values.

### What is not here

- **No action.** Copying (S3), checking for and applying updates (S4) and stopping updates come in their own slices; this page reads.
- **No count of what changed.** See above.
- **Nothing for a repository the library is not invited to.** The list is what the API returns: repositories granted to the library, published or not, and ones it has copied, granted or not.

### Phone

The page uses the phone base: one column, targets at least 44px, the outline and the key-value lists stacking, no control that needs hover. It is checked at 375px in a real browser as part of the slice.

### Tests

The decisions about states, the outline, the counts and the parents line are plain functions (`lib/shelf.ts`) with unit tests. The page is covered by a browser test against the real API and a fake Authgear, in which a library, a repository with entries and a stat group, an invitation and a copy are made through the API and the page is read at desktop and at 375px. The hub's browser tests run in CI from this slice, as inventory-web's do ([ADR 0114](0114-inventory-web-end-to-end-tests.md)), so every later Shelf and Studio slice is tested where it is merged: a new `account-hub-real-api` suite in the CI graph, run when the hub, the API or inventory-web is affected.

Getting there showed that the suite had not been run since the hub's pages were reworked: 37 of its 51 tests failed on selectors that no longer exist (`#tenant-list`, `#account-signed-in`, and others), and `signIn` pointed at a button the home page also has. `signIn` is repaired, as are the two `join` smoke tests (one selector, and a real bug: `Base.astro` did not pass a page's `head` slot to the document head, so `/join` lost its `<meta name="referrer" content="no-referrer">`; the `Referrer-Policy` header in `public/_headers` was never affected). CI runs what matches the pages today: the logged-out smoke tests and `shelf.spec.ts`, as `pnpm run test:real-api:ci`. The other ten spec files stay in place, listed in `tests/real-api/README.md` and tracked in #505, to be repaired one at a time and added to that command; none is deleted or skipped to make a run green.

The plan's counts are the one thing the page does not take at its word: when a repository the plan needs is not offered to the library, the API returns the plan with nothing counted, and a repository the library has copied is not counted again. A row of zeros would be a lie, so `countsKnown` decides, and the page says why it has no counts.

## Not in scope

- Copying a repository, and checking for and applying updates ([RFC 0036](../rfcs/0036-repository-tooling.md) S3, S4).
- The dependencies endpoint (A2) and display values in diffs (A1).
- Discover and public repositories ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)).
- Studio: a repository owner's side of this.

## Consequences

- A library admin can see what the library may copy from and what it has copied without the command line, on a phone.
- The state of a repository is derived in one place, from what the API returns, and is testable without a browser.
- Entries and stat groups are read only when someone opens them, so the page costs two reads (the list and the plan) until then.
- The page is an area of the hub, so it uses the hub's login, cache and error handling, and adds no app, client or dependency.
