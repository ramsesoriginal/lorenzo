# 0154 - `lorenzo tenant list`

Status: accepted

Follow-up to [ADR 0147](0147-lorenzo-tenant-create.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

Every command that takes `--tenant` wants an id or a slug, and the only way to find out what yours are was to know them already. `tenant create` prints the new slug and `tenant show` reads one tenant, but nothing lists them. The client already makes this call: `resolve_tenant` pages `GET /tenants` to turn a slug into an id ([ADR 0135](0135-slugs-in-inventory-web-addresses.md)'s rule that no endpoint looks a tenant up by slug).

## Decision

```bash
lorenzo tenant list [--kind repository|play] [--json]
```

- **It lists the tenants you belong to**, all pages, one row each: slug, name, kind, and your role in it. That is exactly what `GET /tenants` returns for the caller, so a repository you own and the library you play in sit side by side.
- **`--kind`** is the API's own `?kind=` filter ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). Without it, both kinds are listed.
- **`--json`** prints the rows as one array, as the API returned them.
- **An empty list is not an error.** It says so in a sentence and exits 0.
- Nothing changes in `apps/api`, and no operation is added to the client: `LIST_TENANTS` is already there.

## Not in scope

- **A listing of every tenant on the platform.** That is `GET /admin/tenants`, behind the platform-operator role ([ADR 0057](0057-platform-operations.md)), and not something the CLI offers.
- **Filtering by name or role.** Piping `--json` to `jq` does it.

## Consequences

- `--tenant` no longer needs a lookup in another tool.
- A person with many tenants gets every row, since the command walks the pages rather than showing the first hundred.
