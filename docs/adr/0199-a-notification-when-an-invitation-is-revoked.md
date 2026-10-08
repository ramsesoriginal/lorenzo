# 0199 - A notification when an invitation is revoked

Status: accepted, decided with the maintainer on 2026-10-07. Slice A3 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #509.

## Context

[ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) lets a repository's Owner invite a library with `PUT /tenants/{id}/subscribers/{subscriber_id}`, and that tells the library's members: a `repository_granted` notification to each person with a membership, written inside the request ([ADR 0058](0058-notifications.md); there is no job queue, since [ADR 0008](0008-deferred-taskiq-and-fastapi-limiter.md) deferred one). `DELETE` on the same address ends the invitation and tells no one. A library that was getting updates stops getting them with no word, and Shelf has to explain a repository that went quiet without being able to say why ([RFC 0036](../rfcs/0036-repository-tooling.md) §3).

## Decision

### Revoking from the repository's side tells the library

`DELETE /tenants/{id}/subscribers/{subscriber_id}` writes one notification for each member (Owner or Organizer) of the invited library, through the same `_notify_members_of` the invitation and the publish notices use: each member's `Membership` is read under the library's own row-level-security context, the repository's context is put back, and the notifications are committed in the same transaction as the removal. Nobody else is told: not the library's players or GMs, not the repository's own people, and not another invited library.

- **Type:** `repository_revoked`, scope `tenant`, in the library. A notification's `type` is free text (no enum or schema lists the values), so no schema, OpenAPI document or generated client changes, and a client that does not know the value shows the title and body as it does for any other type.
- **Title:** "{repository name} is no longer shared with your library".
- **Body:** "What your library already copied from it stays yours. It will not get updates from it unless it is invited again."

The words follow [ADR 0194](0194-user-facing-terminology.md): the repository is named, the reader's side is "your library", and the text carries no id, no role and no "tenant". It does not name the library, since the reader is in it, and it does not say who revoked the invitation or why: the activity log, which keeps its `repository.revoked` entry as before, is where an administrator of the repository looks for that.

### What does not notify

- **A revoke that finds nothing.** A `404` for an invitation that does not exist, a `403` for a caller who is not an Owner of the repository, and a `409` for a library that is not a repository all stop before anything is written, so no one is told. Revoking twice tells the library once.
- **A library giving up its own access.** `DELETE /tenants/{id}/repositories/{repository_id}` is the library's Owner's own act and stays silent, for the library and for the repository. The repository's side is not told that a library stopped using it: the list of libraries using it shows who is left, and a notification there would reach people who did nothing to cause it.

## Not in scope

- **Notifying the repository's people when a library leaves.** Decided against above; a later slice may add it if Studio needs it.
- **Revokes made by something other than this route.** Public repositories ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)) revoke their public grants when they turn private; that revoke sends this same notice, and fanning it out to many libraries is decided there, not here.
- **A queue for the fan-out.** The notices are written in the request, as the publish and invitation notices are.
- **Changing the words of the existing notices.** The invitation and publish notices still say "tenant"; bringing them into line is the API's terminology sweep ([ADR 0194](0194-user-facing-terminology.md)).
- **Telling the library which update path it lost.** The body states the consequence; what a library does next is Shelf's screen.

## Consequences

- A library's Owners and Organizers learn that a repository was taken away, and that their copies are theirs, on the day it happens.
- One more `type` value, `repository_revoked`, is in the feed. Nothing in the account hub or loot-bot switches on a notification's type: the hub lists title, body and the raw `scope/type` label, which the terminology sweep replaces for every type at once, so neither changes here.
- Revoking costs one more read of the library's memberships and one insert for each member, inside the request, like the invitation.
- No migration: notifications already carry a free-text type and the library's `tenant_id`.
