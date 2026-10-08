# 0206 - Studio: the guarded publish dialog

Status: accepted, decided with the maintainer on 2026-10-08. Slice T3 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #527. Builds on [ADR 0202](0202-studio-my-repositories.md) (the Overview), [ADR 0205](0205-studio-libraries-using-it-and-built-on.md) (who uses it, what it is built on) and [ADR 0204](0204-the-owner-sees-who-copied-a-repository.md).

## Context

Publishing is one request: `PUT /tenants/{id}/published` sets a timestamp and sends a notification to the members of every library with an invitation; `DELETE` takes it back to a draft ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). Until now the hub could not do either: Studio's Overview said to use the command line.

Both matter more than a button suggests. A publish tells people who did not ask to be told, and a copy of this repository is refused while any repository it is built on is unpublished ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)), so a publish that looks fine can leave every library unable to copy it. An unpublish takes the look, the copy and the updates away from every library invited to it at once.

## Decision

### Buttons, for an Owner

On the Overview, under the state: **Publish…** for a draft; for a published repository **Tell libraries about an update…** (publishing again, which is all that says "look now", [ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)) and **Unpublish…**. Each opens a dialog and **changes nothing until its last button**. An Organizer, who edits and cannot publish ([ADR 0202](0202-studio-my-repositories.md)), sees no buttons and is told that only an Owner can.

### The dialog says what will happen, from what is true now

It is a real `<dialog>` opened modally, so focus stays inside it and Escape closes it; Cancel has the focus when it opens, so that Enter does not publish. What it says is read when it opens (the libraries with an invitation and what the repository copied from, asked fresh), not taken from the page behind it.

**Publish** and **Tell libraries about an update**:

- **Check before you go on**, first, where it applies: each repository this one is built on that is **not published** ("A copy of this repository is refused until it is, since a copy brings what it is built on"), and that a library needs an **invitation to each repository this one is built on** as well, since invitations are not passed on.
- How many libraries will be told, in words ("2 libraries have an invitation and are told when you publish: each one's Owners and Organizers get a notification"), or that nobody is, with where to invite one.
- What the libraries can do after: look inside it, copy it, take its updates.
- That a library reads the repository **as it is**, not as it was when published: edits made later are what it sees when it next checks for updates ([ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)).
- That notes marked **GM only** are copied along and stay GM only, and players never see them ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)).

The confirm button says what it does: "Publish and tell 2 libraries", "Tell 2 libraries", or "Publish".

**Unpublish**: it goes back to a draft; how many libraries lose the look, the copy and the updates until it is published again; that what libraries **already copied stays with them** and nothing is deleted; and that **nobody is sent a message**, which is true of the API. The confirm button is "Unpublish".

After either, the page reads the repository again, so the state and the Live notice are the API's, and says what was done.

### Not here

- **A release label, notes and a breaking flag.** The dialog carries none: publishing is still a timestamp and a message. T4 replaces the dialog's body with the release composer once [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) R3 and R4 give it something to say.
- **Whether a library is invited to each repository this one is built on.** Only the library's own invitations say, and the repository's owner cannot read them; the dialog says it as a fact about copying, not as a finding.

### How it is built

The sentences and the facts they rest on are plain functions with unit tests (`lib/publishing.ts`), including that no sentence uses an internal word. The buttons and the dialog are `Repository/publish.ts`; `publishRepository` and `unpublishRepository` in `lib/repositories.ts` are the client's additions. No API change.

## Consequences

- A publish and an unpublish are no longer a click away from a surprise, and neither needs the command line.
- The warning about a built-on repository that is not published is given before the publish, where it used to be found by the first library whose copy was refused.
- The dialog is the first modal in the hub; the brand's own `<dialog>` rules and the phone base cover it, and it is checked at 375px.
