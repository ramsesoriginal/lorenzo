# 0343 - Book-scoped reviewers and private review notes

Status: accepted implementation of RFC 0047 W4 and ADR 0327.

## Decision

An Author grants a named, already signed-in account review access to selected Editions of a
Book. Each tenant-scoped grant names one Edition and account. It creates no membership or
campaign role. Authors use the existing exact email lookup and share a review address; this
slice sends no email. Grants can be independently revoked and newly created Editions are not
automatically shared. Grant changes are serialized with manuscript composition changes.

A dedicated review API projects only the selected Edition's current manuscript tree, including
its Book title and placed Chapters and tellings. Shared tellings project their designated Scene
manuscript in place, without exposing the Scene identity, viewpoint, world references or other
Information. An explicit grant authorizes these manuscript bundles, not unrelated entry content.
Review reads and picture bytes recheck the current grant and current tree on every request.
Ordinary entity, Information, resolution, preview, history, export and write APIs do not gain a
reviewer bypass. Thus a review address cannot be used to browse a library or resolve other links.

Review notes are operational LorenzoScript records attached to an entry within the reviewed
Edition. They are separate from ordinary Information: their fixed audience is the note's author
and the library's Authors, and they cannot accidentally inherit public or campaign audiences.
A reviewer may append and conditionally edit only their own notes; Authors read all notes but
cannot rewrite another person's words. Stable client ids make note creation retry-safe. Notes
survive grant revocation for Authors, but the revoked reviewer loses the access supplied by that
grant. Detached entries are no longer reviewable through the Edition. The author view retains
notes on detached entries without disclosing them to reviewers.

Both tables force RLS and use same-tenant foreign keys. Grants and review notes are operational,
not repository content, and are explicitly excluded from copies and releases. No new release
format is needed. The API uses private no-store responses; file requests do not return a cached
304 without authorization. The review UI keeps no persistent manuscript cache, clears its DOM
when hidden or signed out, and revalidates on return and periodically while open. A failed
revalidation clears manuscript, pictures and notes. Revocation prevents subsequent reads; it
cannot erase text already read or downloaded by a person.

Writing uses an in-page Review view and existing brand and LorenzoScript controls. Authors
manage reviewers from the Edition and inspect notes in the same review view. Reviewers follow
the shared address, sign in and read without the library picker. No manuscript editing, recovery
history, arbitrary reference expansion or reviewer-to-reviewer discussion is added.

## Validation

Exercise two reviewers without memberships, selected versus unselected Editions, descendants,
shared tellings, protected pictures and unrelated content. Verify own-note retries and stale
edits, note isolation, removal and revocation, cross-tenant keys and FORCE RLS, repository
exclusion and real-API browser sharing/review/revocation on desktop and phone. Later Writing
slices remain deferred.
