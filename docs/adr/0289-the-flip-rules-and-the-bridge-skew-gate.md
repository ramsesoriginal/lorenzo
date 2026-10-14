# 0289 - The flip rules and the bridge-skew gate

Status: accepted, decided with the maintainer on 2026-10-14. Slice R8 of [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md), tracked in #711. Builds on [ADR 0288](0288-retention-and-making-a-release-current.md) (the current release), [ADR 0286](0286-the-read-switch-for-public-repositories.md) (what is read of a public repository), [ADR 0287](0287-who-may-read-a-public-repository.md) (the public grant a library gives itself) and [ADR 0213](0213-the-repository-profile-and-the-source-of-a-grant.md) (`visibility`, which the API still refuses to set to `public`).

## Context

[RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) §6 says what must hold when a repository goes between private and public: the flip to public is atomic with its first release, it requires every repository it is built on to be public, going private revokes the grants libraries gave themselves, and a public repository can publish only while it is up to date with what it is built on. [RFC 0038](0038-public-repositories-and-discovery.md) §7 adds that going private is refused while a public repository is built on it. The routes that make a flip an action, with the preview switch, the summary, the terms line and the dialogs, are RFC 0038's D5 and RFC 0036's T7. This slice is the rules, as functions the routes will call, and the gate on publishing, which is reachable now.

## Decision

### Publishing is a function

`PUT /tenants/{id}/published` did its work inside the route. That work is now `repository_publishing.publish_release(session, repository, user_id, body, flipped)`: the unproven-kinds check, the gates below, the breaking-change check, the release, the released rows, the document and its files, the pointer, retention, the log and the notice to the libraries. The route authorises, calls it and commits; making a repository public calls it too, so the first public release is made with exactly the steps of every other. Nothing in it commits.

### Making a repository public

`repository_flips.make_public(session, repository, user_id, body)`:

- **One transaction, together or not at all.** It sets the visibility and then makes the release, the document and the pointer; a refusal anywhere, the gates included, raises and the caller commits nothing. There is no public repository without a release, and no release of a repository that did not become public.
- **Every repository it is built on has to be public** (and published): `409 built-on-not-public`, `repositories` naming each one that is not, with whether the caller owns it, so a dialog can offer to make it public and otherwise say whom to ask. A library copying the repository could not be granted a private upstream by an Owner who never saw it (grants are not transitive, [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)). What a repository is built on is the set of repositories it has copied, as the manifest reads it.
- **Already public** is `409 repository-already-public`.
- **The libraries that already read it live keep their grants and their links.** Their next update check reads the release, so edits made since quietly leave their inbox; the notice they get from this release says so ("It is now public: you read its releases, so what its author changes between releases is not visible to your library until the next one").
- **Logged** as `repository.made_public`, beside `repository.published`.
- **Not here** (D5): the preview switch, that a summary is required, the terms line and the publisher's account, the warning that GM-only text is in what a library copies, and the route. `PATCH .../profile` still refuses `public`.

### Making a repository private

`repository_flips.make_private(session, repository, user_id, acknowledge_revokes)`:

- **Refused while a public repository is built on it**: `409 public-repositories-built-on-it` with the repositories, since that would leave a public stack no one can copy. "Public" means public and published, which is what a library can read; a draft bridge does not hold it.
- **Told how many it cuts off.** The libraries that hold a grant they gave themselves by copying it (`source = public`, [ADR 0287](0287-who-may-read-a-public-repository.md)) lose their update path. Without `acknowledge_revokes`, `409 public-copies-would-be-cut-off` carries the number and nothing changes. A repository nobody copied is made private without asking.
- **What it does**: revokes every `source = public` grant, tells each library's Owners and Organizers with the words of any revoke ("is no longer shared with your library", and that it is no longer public), sets the visibility. **The copies stay**, as after any revoke; the grants the Owner made by invitation stay and read the repository live again; its documents are kept under retention and nothing reads them while it is private.
- **The notices** are written in the request, one library at a time. Past a few hundred libraries that is the asynchronous fan-out of [RFC 0038](0038-public-repositories-and-discovery.md) §6 (D6), which takes that loop over; the rule and the words are this slice's.
- **Already private** is `409 repository-already-private`. Logged as `repository.made_private` with the number revoked.

### The bridge-skew gate

A bridge copied from repositories at one release each; if one of them has since released, a library copying the bridge would get rows made against another state of it, which [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md) drops and reports. `repository_built_on.built_on_behind` lists the repositories a repository is built on whose **current release** is not the one it took (`repository_copy.synced_release_id`; a copy from before releases took none), read through the gated read. Both directions count, since a rollback of the upstream ([ADR 0288](0288-retention-and-making-a-release-current.md)) puts the bridge ahead of it. One it cannot read (unpublished, or no longer granted) is listed as behind with `readable: false`: nothing can be told, and a library could not copy it either.

- **A public repository cannot publish a release while the list is not empty**: `409 built-on-behind`, `repositories` with the release it took and the one it should take. The same gate stands in front of the first release a flip makes, so a stack is made public upstream first and each repository takes the current releases of what it is built on before its own flip, by applying their updates (there may be nothing to apply; the take is the point).
- **A private repository is warned and not stopped.** `GET .../release-preview` gains `built_on_behind` and `built_on_blocks_publish` (true for a public repository), for the composer to say.

## What the tests pin

- Making a repository public: the visibility, a new release with a document that is current, a library that read it live reads the release and is told; refused if already public; refused and written nowhere while a repository it is built on is private, naming it and whether the caller owns it; a stack made public upstream first, the bridge refused for the releases it has not taken (and left private, with no document), then made public once it has.
- The gate on a public bridge: refused with the repository, the release it took and the one it should; allowed after it takes it; a private bridge publishes and the preview warns; a repository built on something it cannot read is behind.
- Making a repository private: told the number first, then the self-given grants gone, the invited one kept and reading live, the copy kept, the library told and no longer reading it, the documents kept; no ask when nobody copied it; refused when already private; refused while a public repository is built on it, and allowed when that one is private.

## Not in scope

- **The routes, the preview switch, the dialogs and what they say** ([RFC 0038](0038-public-repositories-and-discovery.md) D5, [RFC 0036](0036-repository-tooling.md) T7); `public` stays refused by the API until D3 to D6.
- **The asynchronous revoke notices** (D6), **deleting a repository** with public grants (D5), and **deprecating** (D8).
- **Making the upstreams public for the Owner** when the dialog offers to: it is a call of `make_public` for each, upstream first.

## Consequences

- A repository cannot be public without a release, and cannot become so with a private repository under it.
- A public repository's stack stays copyable: an upstream cannot go private under a public dependent, and a public bridge cannot publish against upstreams it has not caught up with.
- Making a stack public takes one flip and one sync for each repository, in dependency order. A sync with nothing in it is the cost of the gate; an Owner of the bridge who does not own an upstream waits for its Owner to flip it.
- Publishing is one function the route and the flip share.
- No migration.
