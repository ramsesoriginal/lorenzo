# 0204 - The owner sees who copied a repository

Status: accepted, decided with the maintainer on 2026-10-08. Slice A5 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #524. Needed by T2, Studio's "Libraries using it". Extends [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) and [ADR 0119](0119-copying-a-repository-into-a-tenant.md).

## Context

`GET /tenants/{id}/subscribers` tells a repository's members which tenants it is granted to: name, link name, when, by whom. [RFC 0036](../rfcs/0036-repository-tooling.md) §4 wants Studio's **Libraries using it** to say more: for each library, **invited on**, **copied or not** and **last updated**. The API cannot say that. Whether and when a library copied a repository is in `repository_copy`, a row of the *library*, under its own `tenant_isolation` policy and the `repository_read` policy that lets a library read the repository's content: nothing lets the repository's side read it.

The list also misses a case that matters to the person who runs a repository. An owner who **stops inviting** a library ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md), [ADR 0199](0199-tell-a-library-when-its-invitation-is-revoked.md)) removes the grant, and the library keeps its copy and the right to be told nothing more. From then on the list no longer shows it, though it holds the repository's content. "Who uses it" is those with an invitation and those with a copy.

## Decision

### The repository's side may read who copied it

A new `SELECT` policy on `repository_copy`, `repository_owner_read`: a row is visible to the tenant it was copied **from** (`repository_tenant_id` is the current tenant). Nothing else changes: the row is still the library's own for every other purpose, and writes stay under `tenant_isolation`. A repository sees that a tenant copied it and when it last updated, which it already knew from granting it and from the notifications it sent, and nothing of what the library did with the copy.

### `GET /tenants/{id}/subscribers` lists invited and copied

Every tenant with an invitation to the repository **or** a copy of it, by name. Each entry gains `copied_at` and `synced_at`, null for one that has not copied it. `granted_at` becomes null for a tenant that copied the repository and is no longer invited (`granted_by` too, as before when the person is unknown). The route's name, parameters and access (any member of the repository) are unchanged.

That widens a field that was never null, which oasdiff counts as breaking; it is accepted in `apps/api/openapi-breaking-accepted.txt` the way [ADR 0119](0119-copying-a-repository-into-a-tenant.md) accepted the same for the library's list, since the only reader is the command line's `repo subscribers`, which prints it, and it is updated in the same change.

### Not changed

- Who may read: the repository's members, as before. A library sees nothing new.
- No row is written; no table is added. One policy.
- The count and names of the libraries using a **public** repository are [RFC 0038](0038-public-repositories-and-discovery.md)'s question (counts, not names); this route is the owner's own view of a repository they invited libraries to.

## Not in scope

- Which release a library is on ([RFC 0037](0037-releases-and-public-snapshots.md) R3 adds `synced_release_id`).
- What a library did with the copy, or its contents.

## Consequences

- Studio can say, for each library, when it was invited, whether it copied the repository and when it last updated, and can still list a library that holds a copy after its invitation went.
- A client that read `granted_at` as always present must handle null. The command line does ("no longer invited").
- The policy is the one place a tenant reads another tenant's `repository_copy` rows other than through the gated repository read, and a test holds it to exactly that: the repository's own tenant, nobody else.
