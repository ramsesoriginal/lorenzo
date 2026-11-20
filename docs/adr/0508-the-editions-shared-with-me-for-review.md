# 0508 - The Editions shared with me for review

Status: accepted, built in the Writing stack of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (its question Q3, answered yes on 2026-11-18) so that the shelf can list the writing that has been shared with a person.

## Context

A review grant ([ADR 0343](0343-book-scoped-reviewers.md)) lets an account that is not a member of the library read one Edition's manuscript tree and write its own notes. Today the reviewer has only the review address they were given: nothing lists what has been shared with them, and the app's own library list, which is for people who write, does not know the grant.

## Decision

- **`GET /me/writing-reviews`** lists the Editions shared with the caller, in every library, as `{tenant_id, edition_id, name}`, ordered by name. It is authenticated and not tenant-scoped, like `GET /me/managed`, and is resolved library by library for the same reason: the grant rows are read before any one library is set, and the names are read inside each library's own context.
- **It says no more than a review shows.** The Edition's name and where to open it. Not the library's name, not the Book, not who else reviews, not the other Editions of the library. A person with no grant gets an empty list, and a revoked grant leaves the list at once. The response is `Cache-Control: private, no-store`.
- **One migration, and no new table.** The `writing_review_grant` table gets a select-only policy that admits the caller's own rows (`user_id = app.user_id`), as membership, player and campaign GM have for `GET /tenants`; its tenant policy changes only in reading the setting as `NULLIF(…, '')`, so a pooled connection that last served a library does not make the cast fail. Every write is unchanged.
- **Not paginated:** it is bounded by the caller's own grants.

## Consequences

- The generated clients (`packages/api-client`, `apps/cli`) gain the read.
- Writing's shelf draws "Shared with you to review" from it (W1). A person who is not a member of any library, and so has no shelf of their own, can still be shown what they are asked to read.
