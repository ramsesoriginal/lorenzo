# 0261 - Studio: view as a subscriber

Status: accepted. Slice T6 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #495. RFC 0036 decides the shape (a button that makes a scratch Test library the owner owns, invites it, opens Shelf for it; "Reset" copies again with purge; nothing added to the API); the details below, where the RFC is silent, were chosen in the implementation and are open to the maintainer's change. Builds on [ADR 0202](0202-studio-my-repositories.md), [0205](0205-studio-libraries-using-it-and-built-on.md), [0206](0206-studio-the-guarded-publish-dialog.md), Shelf's copy wizard ([ADR 0201](0201-shelf-the-copy-wizard.md)) and update inbox ([ADR 0203](0203-shelf-the-update-inbox.md)).

## Context

An author who publishes a repository cannot see what a library sees without a real library to copy it into, and copying into a real one is not a test. The hub already has everything a subscriber uses (Shelf), and a library is an ordinary thing an Owner can make and delete.

## Decision

On a repository's Overview, a section **See it as a subscriber**, using only existing routes: `POST /tenants` (a library), `PUT /subscribers/{id}` (the invitation), `POST .../copy` with `again: "purge"`, `DELETE /tenants/{id}` ([ADR 0184](0184-deleting-a-tenant.md)), and the reads Shelf already makes.

- **View as a subscriber** makes a library named `Test library: <repository name>`, invites it, and opens Shelf on that repository for it. It has not copied yet: the owner goes through the copy wizard and, after publishing a change, the update inbox, exactly as a library's admin does. There is no second read path.
- **One Test library per repository.** It is found, not remembered: a library the person owns, with that name, that the repository has an invitation to. The button then opens it instead of making another.
- **Reset the Test library** (shown once it has copied) copies again with `purge`, after a confirmation that says what it does.
- **Remove the Test library** deletes it, after a confirmation. The repository and its invitations to real libraries are untouched.
- **Who sees it:** an Owner whose account may create libraries (deleting is gated by the same platform role, so a Test library can always be removed again), on a published repository (a draft cannot be copied). Otherwise the section says why not.
- **No leftover.** If the invitation fails after the library was made, the library is deleted again before the error is shown. If that delete fails too, the message names the library so it can be removed by hand. The Test library is otherwise kept on purpose, until Remove, because the second half of the point (updates) needs it to outlive the visit.

Pure decisions are in `lib/subscriber.ts` (finding it, who is offered the button, the sentences, and the making with its cleanup, with the API calls passed in so the failure path is unit-tested); the DOM is `components/Repository/viewAs.ts`. `deleteTenant` is the client's one addition.

## Open to the maintainer

- The Test library is told by its **name**, since the API has no marker for a scratch library. Renaming it in Shelf makes the button make another. A marker would be an API change and is not made here.
- The Test library shows in the owner's libraries (and in "Libraries using it") like any library; it is not hidden.
- "Opens Shelf for it" is read as: opens at the repository's page, not copied yet, so the copy wizard is part of what is seen. The alternative, copying at once, is a one-line change.

## Consequences

- An author sees the copy and then the updates a subscriber would, without a real library.
- A Test library costs one library per repository until removed.
