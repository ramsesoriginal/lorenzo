# 0178 - account-hub: repositories

Status: accepted, decided with the maintainer on 2026-10-04. Builds on [ADR 0175](0175-me-says-what-you-may-create.md) (who may create one). Part of the v1.0 row "Simple repository create".

## Context

A repository is a tenant of kind `repository`: a place whose content other tenants copy from and take updates from, where nobody plays ([RFC 0024](../rfcs/0024-repositories.md), [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). `lorenzo tenant create` makes one ([ADR 0147](0147-lorenzo-tenant-create.md)); account-hub cannot, and it has never read a tenant's `kind`.

That is a bug, not only a gap. RFC 0024 said every surface that lists or offers tenants "must be aware of `tenant.kind` and correctly exclude repository-tenants", and none of account-hub's does. `GET /tenants` returns `kind` and filters on it; a repository its owner made with the CLI therefore appears on `/tenants` as a library, with a "Create a campaign" form the API refuses (`RepositoryHasNoCampaignsError`), and as an empty entry on `/overview`, `/characters` and `/beings`. This is read from the code; it has not been looked at live.

[Identity §14.3](../brand/identity.md) did not help: it says a library "contains the campaigns, characters, repositories", and that `Library` does not mean `repository`. In the model a repository is not inside a library; it is a tenant of its own kind.

## Decision

### Wording

**Repository** is the user-facing name for a tenant of kind `repository`, and it is not a library. Identity §14.3 is corrected in the same change: a library holds a group's campaigns, characters and other material; a repository is a separate kind of space whose content libraries copy; neither is called the other. Product copy says "repository" for it everywhere: its heading, its badge, "Create a repository", "Leave this repository".

### Where repositories show

- **`/tenants`** loads `GET /tenants` once and splits it by `kind`. Libraries are listed as today. **Repositories get a section of their own**, "Your repositories", below.
- **`/overview` and `/characters`** (which become one page, [ADR 0179](0179-account-hub-one-campaigns-page.md)) **list libraries only.** Nobody plays in a repository.
- **`/beings` keeps listing them**, with a "Repository" badge: a repository's beings are content its owners author. It shows them for reading, with **no hand-off panel**, since there are no players to give to.

### What a repository row offers

- **Rename and edit**: name, slug and description, with the concurrency check the library editor already has ([ADR 0136](0136-account-hub-client-and-tenant-slug.md), [ADR 0170](0170-account-hub-readable-errors-self-service-exits-and-admin-basics.md)).
- **People and invitations**: its owners are its authors ([RFC 0024](../rfcs/0024-repositories.md) §2); the membership admin panel, bulk invite included, applies unchanged.
- **Its published state**, read-only: "Draft", or "Published *date*", from `TenantOut.published_at`. Publishing, granting and subscribing stay on the CLI until the "Publish, subscribe, update screens" row is built.
- **Leave this repository**, as for a library, with its own wording.
- **Not offered**: campaigns, invite links, a player roster, characters.

### Creating one

A second form, "Create a repository", beside "Create a library": name, optional slug and description, sending `kind: "repository"`. Both create forms appear **only when `GET /me` says `capabilities.create_tenant`** ([ADR 0175](0175-me-says-what-you-may-create.md)); otherwise one sentence says creating one is not open to the account yet. A `403` is still shown if it comes.

## Alternatives considered

- **One create form with a kind selector.** ADR 0147 called that "a separate, small change". It buries the choice a person should make on purpose, and puts a word, "kind", on screen that product copy avoids.
- **Hide repositories from the hub entirely.** Their owners would have no way to rename one or to invite a co-author without the CLI.
- **Two requests, `?kind=play` and `?kind=repository`.** One call and a split is cheaper and cannot disagree with itself.

## Not in scope

- Publishing, granting and subscribing; browsing a repository's content; deleting one.
- Changing a tenant's kind: it is immutable ([RFC 0024](../rfcs/0024-repositories.md) A10).
- Anything in `apps/api`: every field used (`kind`, `published_at`) is already served.

## Consequences

- **Client-only, plus one docs change** (identity §14.3).
- The latent bug above is fixed for everyone who already owns a repository, in the same slice as the feature.
- Pages that name a tenant in a sentence (the leave and sole-owner messages of [ADR 0170](0170-account-hub-readable-errors-self-service-exits-and-admin-basics.md)) pick "library" or "repository" from the tenant's kind.
- Verified in a real browser against the real API with a library and a repository side by side, and the logged-out smoke specs stay green.
