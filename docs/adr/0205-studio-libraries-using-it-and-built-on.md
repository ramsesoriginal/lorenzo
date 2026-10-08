# 0205 - Studio: libraries using it, built on, and activity

Status: accepted, decided with the maintainer on 2026-10-08. Slice T2 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #526. Builds on [ADR 0202](0202-studio-my-repositories.md) (Studio's page), [ADR 0204](0204-the-owner-sees-who-copied-a-repository.md) (who copied it), [ADR 0199](0199-a-notification-when-an-invitation-is-revoked.md) (stopping an invitation is told), [ADR 0198](0198-the-dependencies-endpoint.md) and Shelf ([ADR 0196](0196-shelf-the-repositories-list-and-page.md), [0201](0201-shelf-the-copy-wizard.md), [0203](0203-shelf-the-update-inbox.md)).

## Context

[ADR 0202](0202-studio-my-repositories.md) gave a repository's owner a page with an Overview and People. What a repository's owner also needs is where it stands among others: which libraries use it, what it is itself built on and whether that has moved, and what has been done to it. The API serves all three; the hub shows none.

## Decision

Three more tabs on a repository's page, each read when the repository is shown, each saying its own failure in its own place, so that one that fails does not blank the rest.

### Libraries using it

Every library, or repository, that has an invitation to this repository or a copy of it ([ADR 0204](0204-the-owner-sees-who-copied-a-repository.md)), by name, each with a state in words: **Invited, not copied yet**, **Copied**, **Not invited any more**, and a line with the days it was invited, copied and last updated. A copy that outlived its invitation says what that means: it keeps its copy and gets no more updates unless invited again. A sentence on top counts them. Whoever works on the repository reads it.

An **Owner**, and only an Owner, can:

- **Invite a library** by its id, which is what the API takes and what the library's owner can give. The id is checked for shape before it is sent, and what the API refuses is shown in its words. Invitation by link is [RFC 0040](../rfcs/0040-authors-and-invites.md)'s and does not replace this.
- **Stop inviting** a library that has an invitation. The button asks first, in words that say what it does: what the library copied stays with it, it gets no more updates unless invited again, and its Owners and Organizers are told ([ADR 0199](0199-a-notification-when-an-invitation-is-revoked.md)). The row stays, as one that keeps its copy.

### Built on

The repositories this one copies from, or has been invited to copy from, by name: the state in Shelf's words (Copied, Update announced, Invited and not copied, No longer offered, Not published), when it was copied and last updated, and, for a copy of what is still offered and published, **how many updates are waiting** (counted with the updates check, a few at a time, each row filling in as its answer comes) and **Review updates**. A repository that builds on nothing says so.

**Review updates is Shelf's own screen, for this repository.** A repository copies as a library does ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)), so the update inbox of [ADR 0203](0203-shelf-the-update-inbox.md) needs nothing new: Shelf now takes a repository the person runs as the one it acts for, listed after their libraries and marked "(repository)", and its address (`?tenant=<slug>`) works for either. **Add** is the same: the repositories offered to this one are Shelf's list for it, with its copy wizard ([ADR 0201](0201-shelf-the-copy-wizard.md)). The tab says how a repository gets another to build on: only the other's Owner can invite it, and then it is copied from the repositories offered to this one. A link goes there.

Shelf's sentences still say "your library" when it acts for a repository; the terminology sweep ([RFC 0036](../rfcs/0036-repository-tooling.md) G2) takes that, and nothing here is built around it.

### Activity

The repository's activity log, with the hub's own component for it and its names for people and the repository, for whoever works on it.

### Phone

The tabs are five now, which do not fit a phone's width. The brand's tab row wraps onto a second line below 720px instead of running off the screen ([identity §8.5](../brand/identity.md)). Every control is the brand's 44px target; the new tabs are checked at 375px.

### How it is built

Pure decisions in `lib/using.ts` with unit tests: a library's state with a repository, the line for a row, the summary, whether an id can be sent, the confirmation, and the built-on rows. The three tabs are `Repository/sections.ts`, each bound once and filled when a repository is shown. `listSubscribers`, `inviteLibrary` and `stopInviting` are the client's additions. No new API beyond A5.

## Not in scope

- **The publish dialog** (T3) and **releases** (T4, [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md): "which release" a library is on needs the ledger).
- **Names of the libraries using a public repository**: RFC 0038 makes them counts there. This tab is an owner's view of the repository they invited libraries to.
- **Hiding built-on names** from a library that is not invited to them (an open question of RFC 0036, A2's).

## Consequences

- A repository's owner sees who uses it, can invite and stop inviting from the hub, and sees what the repository is built on and whether it has moved, without the command line.
- The repositories a person runs now open in Shelf as well, so the update inbox and the copy wizard serve a repository that builds on another without a second implementation.
- A library that holds a copy after its invitation was withdrawn stays visible to the repository's owner.
