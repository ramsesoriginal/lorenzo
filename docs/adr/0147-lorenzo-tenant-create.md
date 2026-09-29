# 0147 - `lorenzo tenant create`

Status: accepted

Follow-up to [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R3) and [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md).

## Context

Importing needs a `repository` tenant, and a tenant's kind is fixed when it is created ([ADR 0118](0118-tenant-kind-and-repository-access.md)). The only way to make one was a raw `POST /tenants`: account-hub's create form sends no `kind`, so it makes `play` tenants, and the API treats an omitted kind as `play`. Someone who wants to import homebrew had to `curl` first.

R3 decided the importer never creates its target ("No `--create-if-missing`"): `seed` and `apply` write only into a tenant that already exists and is the right kind, so a typo in `--tenant` can't mint a tenant.

## Decision

A separate command, not a flag on the importer:

```bash
lorenzo tenant create NAME [--slug S] [--description D] [--kind repository|play] [--json]
```

- **Default kind is `repository`.** The CLI exists for the importer, and a play tenant is what every other client already makes. The kind is printed back, and `--kind play` is there for completeness.
- **It creates and stops.** It doesn't seed. It prints the next step (`lorenzo seed --tenant <slug>`), so R3 stands: no command both creates a tenant and writes into it.
- **The caller becomes the owner** and needs the tenant-creator role, as `POST /tenants` already requires; a 403 is shown with the server's reason.
- Nothing changes in `apps/api`.

## Consequences

- Making a repository and importing into it is now three commands (`tenant create`, `seed`, `apply`), none of which needs `curl`.
- account-hub still can't create a repository; a kind selector on its form remains a separate, small change.
