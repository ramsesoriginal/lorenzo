# 0222 - Ids made by the client

Status: accepted, decided with the maintainer on 2026-10-09. Slice W2 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) (section 6). Builds on [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md) (`POST /entities`) and [ADR 0002](0002-multi-tenancy-shared-schema-rls.md) (row-level security).

## Context

Bench writes a change down before it sends it, and sends later, possibly after a closed tab or a lost connection. A command that makes an entry has to be able to name it before the server has: a later command, a rename or a note, uses the entry's id while the create is still waiting. And a create that was sent but whose answer never came must be safe to send again, or the entry is made twice.

## Decision

- **A create takes an optional `id`** (a UUID): `POST /tenants/{t}/entities`, `POST /tenants/{t}/items` and `POST /tenants/{t}/entities/{id}/information`. Left out, nothing changes: the server makes the id. These are the creates Bench queues now; any other create gets the field when Bench queues it.
- **The replay rule.** If a row with that id is **visible in the caller's tenant**, the create was already done: the existing row is returned with **200** (the first create answers 201), with its `Location` and, for an entry, its `ETag`, and nothing is written, logged, or checked again. A singleton note type or a taken link name does not make a replay fail, because the check for them comes after the replay check.
- **An id that is not the caller's to use is a generic 409** (`Id not available`), and it says no more: the row belongs to a tenant the caller cannot see, or it is a row of another kind (an `id` given to `POST /items` that names an entry which is not an item), or a note of another entry. The answer is the same for each and never names another tenant, so an id is not a way to learn what other tenants hold.
- **How a clash is found.** The visible row is looked up first (the tenant is checked as well as the row-level policy). Otherwise the row is inserted under the id inside a savepoint, and a violation of the primary key, which is what an id held by an invisible row is, is the 409; any other integrity error is not translated. Two creates with the same id sent at the same moment from one tenant may both miss the first look-up, and the second then gets the 409 rather than the replay. Bench sends one command at a time, so it does not meet this; it would treat a 409 on a create as needing attention, not as done.
- **A replay does not compare the body.** The same id with another name returns the first row unchanged. The client chose the id, and an id it reuses for something else is its own mistake to see; comparing would make a retry after a partial edit fail.
- **The interim rule of RFC 0039** (always send a link name and treat a taken link name as done only after reading the entry back) is not needed once Bench sends ids, and is not built.

## Consequences

- Bench can queue a create and a rename or a note on the new entry in one go, offline or not, and send them in order.
- A client that sends ids must make them random (v4); an id guessed or reused clashes, which is a 409 and not a leak.
- The generated clients (`packages/api-client`, the CLI's models) carry the new field.
