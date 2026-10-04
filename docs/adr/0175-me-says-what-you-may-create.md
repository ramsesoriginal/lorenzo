# 0175 - `GET /me` says what you may create

Status: accepted, decided with the maintainer on 2026-10-04, for account-hub's one-click setup ([ADR 0180](0180-account-hub-one-click-setup.md)) and its "Create a repository" form ([ADR 0178](0178-account-hub-repositories.md)). It is the "`/me` capabilities" item of the [v1.0 goal](../../v1.0.md).

## Context

Creating a tenant, a library or a repository, is gated by one platform role: `POST /tenants` answers `403` to anyone whose token lacks the Authgear role `tenant_creator` ([ADR 0033](0033-tenant-creation-and-update-api.md), `require_tenant_creator_role`). The role is granted by hand in the Authgear Portal ([deployment setup](../operations/deployment-setup.md#granting-the-tenant-creator-role-adr-0033)), and nothing in the API says who holds it. ADR 0033 named exposing it on `GET /me` as a deferred follow-up, and [ADR 0155](0155-lorenzo-whoami.md) noted that `lorenzo whoami` and `tenant create` are waiting for it.

So every client that offers a create form offers it to everyone, and a `403` is the only signal. account-hub's "Create a library" form does exactly that (`tenants.astro` says so in a comment). That is tolerable for one small form. It is not for a setup page that creates a library, a campaign and invite links in a chain ([ADR 0180](0180-account-hub-one-click-setup.md)): a newcomer would fill in four fields and be refused at the first call.

## Decision

`GET /me` gains one field, `capabilities`:

```json
{ "capabilities": { "create_tenant": true } }
```

- **`create_tenant`** is true when the caller's token carries the tenant-creator role: the same claim, read through the same function, as the gate on `POST /tenants`, so what `/me` says and what `POST /tenants` does cannot drift. It covers both kinds of tenant, as [RFC 0024](../rfcs/0024-repositories.md) puts them behind one gate.
- **An object, not a flat flag or a list**, so a later capability is one more key. A client treats a missing key as false.
- **Nothing else from the token is exposed.** Not the role list (Authgear role keys have already changed once, ADR 0033's addendum, and are not API contract), and not the platform-operator role, which no client needs to render.
- **It is a convenience, not authorization.** The `403` stays; a client still shows it if it comes. A role granted in Authgear appears with the next token, exactly when the gate would start to admit it.

## Alternatives considered

- **`GET /me/capabilities`.** A second request on every page load that wants it, for one boolean; `GET /me` is already called on every page by every client.
- **A flat `can_create_tenants` field.** Reads well and doesn't extend.
- **The raw role list.** Leaks Authgear's role keys into the contract.

## Not in scope

- **`lorenzo whoami` showing it.** ADR 0155 foresaw that; it is a separate, small CLI change.
- **Granting the role in the app.** Still Authgear's concern (ADR 0033).
- **Per-tenant capabilities.** What someone may do inside a tenant stays in its roles and its `403`s.

## Consequences

- **One additive field**, no migration, no query: the roles are already on the request's user. `GET /me`'s generated clients are regenerated, and a test covers a caller with and without the role, and the same answer from `POST /tenants`.
- account-hub shows its create forms, and the setup page, only to those who can use them.
