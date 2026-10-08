# 0198 - The dependencies endpoint: what a repository is built on, as the asking library sees it

Status: accepted, decided with the maintainer on 2026-10-07. Slice A2 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #508.

Builds on [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) (the gated read), [ADR 0119](0119-copying-a-repository-into-a-tenant.md) (the copy and its records) and [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md) (bridges and the manifest).

## Context

A repository that copied other repositories is built on them (a bridge, ADR 0120). Today the only place the API says what a repository is built on is `GET .../repositories/{id}/copy-plan`, and it answers more than a screen that only wants the outline needs, and less than that screen needs:

- it plans a copy: it loads the content of every repository it can plan and works out collisions, rows and counts, for a question that is only "built on which repositories?";
- it returns counts, and zeros for any step it could not plan;
- it needs every step granted and published to plan anything, so for exactly the case the outline most needs (a library invited to a bridge and to none of what the bridge is built on) it can only name the steps, with zero counts, and it gives no slug.

Shelf and Studio draw a dependency outline: a repository, what it is built on, and where the library stands with each (RFC 0036 §3 and §4). A library invited to a bridge and not to its dependencies has to know whom to ask, and the name and slug are what it asks with.

## Decision

### The endpoint

`GET /tenants/{tenant_id}/repositories/{repository_id}/dependencies`, for any member of the library `tenant_id`. It returns a list, one item for each repository `repository_id` is built on, in the order `copy-plan` puts its steps:

```json
[
  {
    "id": "…",
    "name": "D&D 5e",
    "slug": "dnd-5e",
    "invited": false,
    "copied": false,
    "published": true
  }
]
```

- `id`, `name` and `slug` are the built-on repository's.
- `invited`: the asking library holds an invitation (a `repository_subscription` row) to it.
- `copied`: the asking library has copied it (a `repository_copy` row of the library's own).
- `published`: it is published, true or false, never the date.

A repository built on nothing answers `[]`.

**The order** is the manifest's: dependencies first ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)), ties by name and then id. One level is the whole set, because a bridge had to copy its own dependencies' dependencies before it could copy them. The endpoint shares `repository_copying.manifest`'s ordering, not a second implementation: `dependencies_of` is the manifest without its last step, and `manifest` no longer loads the library's copy links, which it never used beyond the ids of what it had copied. The ordering of two dependencies against each other comes from each one's own copy records, which the asking library can read only for a dependency it is invited to that is published; for one it cannot read, the two fall back to name order, exactly as `copy-plan` does.

**What is left out.** The asking library itself, if the repository is built on it (its own rows are the origins, as in the manifest), and the repository itself. A dependency whose tenant no longer exists (a copy record keeps a plain id, ADR 0119) is left out: there is nothing to ask, invite or copy.

**Never content.** It plans no copy and loads no content. It returns no count, no entry, no text, no description and no information about who owns or belongs to a repository.

### Who may ask, and what the answer for everyone else is

The same gate as browsing and planning: the asking library holds an invitation to `repository_id` and `repository_id` is published. Anything else is `404 repository-not-found`, the same answer for an id that does not exist, a repository the library is not invited to, a draft, and a tenant that is not a repository, so the endpoint tells a stranger nothing about which ids are repositories. A caller who is not a member of `tenant_id` gets `404` for the library, as everywhere ([ADR 0023](0023-authgear-token-verification.md)).

**Offered and published, not offered and unpublished.** A draft is invisible to every library whatever invitations exist ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), and what a repository is built on is read from its copy records, which are repository content: the database lets a library read them only through the gated read, which refuses a draft. Answering for a draft would mean either a second read path or a second policy on those tables, and a draft's list of what it is built on is unfinished work. A library invited to a draft has nothing to ask yet. The same holds after unpublishing: libraries lose browse, copy, updates and this list, and keep their copies.

### What a library that is not invited to a dependency may learn

The library is invited to the repository (that is the gate) and not to something it is built on. The point of the endpoint is that it learns **that repository's name and slug, and that it is not invited** (`invited: false`), because it has to ask that repository's owner. It also learns whether that repository is published, because an owner who has not published it cannot be asked for a copy yet, and its own `copied` fact. It learns nothing else about it: not its description, its owners or members, the libraries invited to it, when it was published, what it holds or how much, and not what it is itself built on (only the order, indirectly, and only for a dependency it can read).

Why this is safe, and not a way to look around:

- The library reaches a dependency only through the repository's own copy records: the ids it asks about are the ones the repository's owner built on, in a repository the owner invited the library to. There is no way to ask about an id it was not shown, and no listing.
- `copy-plan` already names every step, granted or not (ADR 0120). The slug is the one new fact, and it is the repository's handle in addresses and the command line.

### How it is read

No migration, and no policy of any table changes. Each read is one that already exists, and each runs under the policy that already governs it:

| What | From | Under |
| --- | --- | --- |
| The repository's copy records, to find what it is built on | `repository_copy` of `repository_id` | The gated read of `repository_id` (`reading_repository`), which needs the library's invitation and publication ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). Only that one query runs inside the block. |
| Each dependency's own copy records, for the order | `repository_copy` of the dependency | The gated read of that dependency, which yields nothing unless the library is invited to it and it is published. |
| The library's state of each dependency | `repository_subscription` and `repository_copy` of the library | The library's own rows (`tenant_isolation`, and the subscription's either-side read). |
| Name, slug, whether published | `tenant` | `tenant` has no row-level policy: it is the root, and every route that names another tenant already reads it (`copy-plan`, the browse routes). Only `id`, `name`, `slug` and whether `published_at` is set are read. |

The gated read stays "asked for, never ambient": the setting is set for one query and cleared on the way out, and nothing in this endpoint reads any other table inside it.

### Names are returned, and may be masked later

Whether the owner of a repository may hide the name of a repository that belongs to someone else is an [open question in RFC 0036](../rfcs/0036-repository-tooling.md#open-questions). This endpoint **returns the names**, as `copy-plan` already does, and builds no masking. If it is decided, it is a later, explicit decision that changes this ADR's table of what a library learns; nothing here assumes it.

## Not in scope

- **Masking names** (above).
- **Reading a draft repository's dependencies**, for its own authors: they read their own repository through the ordinary routes.
- **What each dependency is built on**, beyond one level: a bridge holds all of them already.
- **How many updates are waiting, or when a copy was last updated.** `GET .../repositories` and `.../updates` carry those; the outline can join them.
- **A client for it.** The generated clients gain the operation; screens and the command line use it in their own slices.

## Consequences

- A screen can draw a repository's outline, and tell a library whom to ask, without planning a copy or holding the content of anything.
- A library learns the slug of a repository it is not invited to, and only through a repository whose owner invited it.
- Draft repositories answer `404`, so Studio draws a draft's own outline from what its authors can already read, not from this endpoint.
- `manifest` no longer loads the copy links of the library; `copy-plan` and `copy` are otherwise unchanged. The change to the OpenAPI schema is additive, so no entry in `openapi-breaking-accepted.txt` is needed.
