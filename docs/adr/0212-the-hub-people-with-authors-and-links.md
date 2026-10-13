# 0212 - The hub: People with Authors, and the links panel

Status: accepted, decided with the maintainer on 2026-10-08. Slice U3 of [RFC 0040](../rfcs/0040-authors-and-invites.md), tracked in #547. Builds on [ADR 0202](0202-studio-my-repositories.md) (the People tab, whose code it reuses), [ADR 0219](0219-the-author-role.md) (the role and what the API lets it do), [ADR 0220](0220-one-invite-table-with-kinds.md) (the links and the routes that make them) and [ADR 0171](0171-account-hub-campaign-invite-links.md) (the status function, the link builder and the shown-once box a campaign's links already use). The words are [ADR 0194](0194-user-facing-terminology.md)'s.

## Context

The hub's People tab said Owner and Organizer, and its role meanings said that an Organizer is the one who edits "until there is a role for people who only write content". There is one now, and a person can be brought in with a link the API makes. The hub offered neither, and an Author who opened a repository in Studio would have met pages that ask the API for what an Author may not read.

## Decision

Hub only: nothing in `apps/api` changes.

### People, in a library and in a repository

One tab, **People**, in each repository's page and in a library's page (which called it Admins). For an Owner it is the membership panel with three roles:

- **Owner, Organizer and Author** in every choice (adding a person, changing a role, the bulk invite), never `orga`. A person is added as an Author unless the Owner picks otherwise, the least a role can be. Under the choice, one line says what the chosen role allows.
- **What each role allows**, listed above the people, in the words of what it is run on: `roleMeanings('repository' | 'play')` in `lib/studio.ts`, which replaces the fixed list and the note about Organizers editing. They say what the API enforces (ADR 0219): an Owner has full control; an Organizer edits the repository and everything in it and cannot publish it, invite libraries or change who works on it; an Author edits what is in it and cannot also delete stat groups or other structure; in a library an Author edits the catalog and reaches no campaign, character or player.
- **Who added each person**, where that person is in the list too ("Added by Ana").

An Organizer, who the API lets read the roster, gets the list and nothing to change it with, as before.

### What an Author sees of a repository

An Author reads no roster (it is the people who run a repository's to read, ADR 0219), so their People tab shows their own role, **You: Author**, with what each role allows. They have **Leave this repository**, as anyone with a role has; the library page's leave button is now shown to an Author as well. They do not get the tabs whose reads the API refuses them, **Libraries using it** and **Activity**; Releases, Built on and the Overview they do, with the publish buttons replaced by the sentence that only an Owner publishes. A repository an Author works on is in My repositories, which already lists what `GET /me/managed` lists.

### The links panel

A `TenantInviteLinks` component for an Owner, reusing what a campaign's links use (the status, the link, the box that shows it once, revoke with a confirmation) and the routes of ADR 0220:

- **In People** it makes **role links**: Author or Organizer (never Owner: the choice has two), how long it lasts (1 hour, 1 day, 3 days or 6 days, 3 by default, never more than the API's 7), and for an Author link **how many people may use it**, 1 to 10, one when empty. An Organizer link is for one person and the box is not shown. A box that is not a whole number from 1 to 10 is said and not sent.
- **On a repository's Libraries using it tab**, under the invitation by id, it makes **library links**: how long (1 hour to 4 weeks, a week by default) and how many libraries, 1 to 10. The id stays, as the RFC says.
- **The link is shown once**, with Copy and Done and what it does: an Author link says that whoever opens it first, or the first *n* people, become Authors of this library or repository, that it never makes an Owner and never changes a role someone already has; an Organizer link that whoever opens it becomes an Organizer and it works once; a library link, as the RFC asks, that a private repository is open to whoever uses the link first, and that it should go only to the person it is for. It is not put in the page again, and the list below holds only counts.
- **Listed**, newest first and each kind in its own place, with **Active, Revoked, Expired** or **Used up**, how many have used it, when it ends, and **Revoke**, which asks first and takes nothing back from people who already used it.

The panel is only drawn for an Owner; an Organizer or an Author, who the API refuses, is not offered it.

### Words and phones

Owner, Organizer, Author, library and repository: never `orga`, tenant, grant or subscription in anything a person reads. Every control is a brand control and the panel is checked at 375 px.

### How it is built

Pure functions with unit tests in `lib/inviteLink.ts` (the team-size box, the roles a link can make, the notices) and `lib/studio.ts` (the meanings); `lib/tenantInvites.ts` is the three calls. The panel is a component with a renderer and `<template>`s, bound by the Repository and Tenant components. Browser tests against the real API (`tests/real-api/people-authors.spec.ts`, in the CI script) cover an Owner's panel and the three roles, making, seeing once, listing and revoking a link, a person following an Author link and landing in Studio as an Author, an Author's own view, the library link, a library's People and leave, and 375 px. The existing specs that clicked **Admins** click **People**.

## Not in scope

- **A role link for a campaign's GM** and the GM's title: its own ADR.
- **Showing co-authors to an Author**: the RFC proposes no, so the API does not allow it.
- **Notifications for a role change** are the API's (ADR 0219); the hub shows them as it shows any.
- **The activity log's names for the new actions**: it shows what the API wrote.

## Consequences

- An Owner can bring in an Author, or a small team, or an Organizer, with a link, and see and revoke every link, without leaving the page they manage people on.
- An Author who opens a repository or a library meets only what the API serves them.
- A library's Admins tab is called People, so a link or a test that named the old tab changes.
