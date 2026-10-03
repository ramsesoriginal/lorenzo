# 0159 - `lorenzo repo`: publish, grant, copy-plan, copy and updates

Status: accepted

Follow-up to [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R10) and [RFC 0024](../rfcs/0024-repositories.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)); [ADR 0160](0160-lorenzo-repo-offer.md) adds `repo offer` on top of these.

## Context

`lorenzo tenant create` makes a repository and `lorenzo seed` and `apply` fill it ([ADR 0147](0147-lorenzo-tenant-create.md), [0143](0143-lorenzo-seed-taxonomy-and-stats.md), [0144](0144-lorenzo-import-mapping-identity-plan-apply.md)). After that the CLI stops: publishing it, granting it to a table's tenant, copying it in, and taking its updates are all API routes ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md) to [0121](0121-repository-updates-and-re-sync.md)), and the web apps have no screens for any of them yet. Someone who imports a repository today has to `curl` the rest.

RFC 0025 R10 left the publishing boundary at "the importer builds no `repo offer`" and reserved the name as a follow-up that "needs its own RFC". The maintainer decided on 2026-10-03 to take it straight to ADRs instead, since every step is an existing API call and the RFC's own R10 already says which ones. The reasoning that RFC recorded stands, and [ADR 0160](0160-lorenzo-repo-offer.md) follows it.

## Decision

A `repo` command group, one command per API step, so each can be used on its own. `--tenant` is the tenant the command is about, and says which in each command's help:

```bash
# On the repository itself (--tenant is the repository; its owners only)
lorenzo repo publish     --tenant REPOSITORY      # publish, or announce an update
lorenzo repo unpublish   --tenant REPOSITORY
lorenzo repo grant   SUBSCRIBER --tenant REPOSITORY
lorenzo repo revoke  SUBSCRIBER --tenant REPOSITORY
lorenzo repo subscribers --tenant REPOSITORY

# From the tenant that draws on one (--tenant is that tenant; any member)
lorenzo repo list                      --tenant TENANT
lorenzo repo copy-plan REPOSITORY      --tenant TENANT
lorenzo repo copy      REPOSITORY      --tenant TENANT
lorenzo repo updates   REPOSITORY      --tenant TENANT
```

Every command takes `--json`, and `--tenant` takes `LORENZO_TENANT` like the others.

`unpublish`, `revoke`, `subscribers` and `list` are not in the list that was asked for. Each is the other half of one that was: a publish nobody can withdraw, a grant nobody can take back, and a `copy-plan` that needs a repository's id with no way to find it. They add no new API surface.

### Naming a tenant and a repository

- **A repository** (the argument of `copy-plan`, `copy` and `updates`) is an id or a slug. A slug is looked up in `lorenzo repo list`, that is, among the repositories granted to the tenant or copied by it, since no route looks a repository up by slug ([ADR 0135](0135-slugs-in-inventory-web-addresses.md)'s constraint again).
- **A subscriber** (the argument of `grant`) is an id or a slug. A slug is found among *your own* tenants, as `--tenant` is. The API deliberately has no directory of tenants ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)): a grant names its subscriber by an id its members pass on. So granting to a tenant you don't belong to takes its id, and the error for an unknown slug says so. `revoke` finds its subscriber in `subscribers`, which lists every grant with its slug.

### The commands

- **`publish` / `unpublish`** are `PUT` and `DELETE .../published`. They print the tenant, with its `published` state, and `publish` says whether it was a first publish or an update (every granted tenant's members are told, [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)).
- **`grant` / `revoke`** are `PUT` and `DELETE .../subscribers/{id}`. `grant` says whether the grant is new or already existed, and that the subscriber's members have been told.
- **`list`** prints each repository a tenant holds a grant for or has copied: name, slug, whether it is published, granted, copied, and **updated since the last sync** (`published_at` later than `synced_at`, or than `copied_at` before a first sync, as [ADR 0121](0121-repository-updates-and-re-sync.md) defines it).
- **`copy-plan`** is the choice-free preview ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)): each step of the manifest, dependencies first, with whether it is granted, published and already copied, what it brings in, anything it would leave out, and every collision with its allowed choices and the ids a choice names. **Exit codes follow `seed` and `plan`: 0 the copy could go ahead as it stands, 2 it needs choices, 1 it would be refused** (a step without a grant or not published, or the repository already copied).
- **`copy`** copies, with the API's own safeguards:
  - **Choices.** `--choices FILE` is a JSON list of resolutions as the API takes them (`kind`, `source_id`, `action`, `name`), written from `copy-plan --json`'s collisions. `--on-collision merge|skip` answers every collision that allows it, for the common case of a repository whose stat names overlap the tenant's own. An explicit choice in the file wins over the flag. A collision with no answer stops the command before anything is written, lists what is open, and exits 2. Nothing is guessed, as [ADR 0119](0119-copying-a-repository-into-a-tenant.md) requires.
  - **`--dry-run`** is the API's, which does every check and rolls back. It prints what would be copied and exits 0.
  - **`--again keep|purge`** is the API's, for a repository already copied. `purge` deletes what the earlier copy created and what hangs off it, so it never runs without `--yes` or an explicit, plainly worded confirmation, and `--dry-run` shows the cost first (`also_removed`).
  - **Asking.** Like `seed` and `apply`, it asks "Copy these?" at a terminal unless `--yes`, and with `--json` it never asks and needs `--yes` ([ADR 0156](0156-json-on-apply-and-pack-give.md)).
- **`updates`** reads what a copied repository changed since the copy or last sync ([ADR 0121](0121-repository-updates-and-re-sync.md)), row by row, with each field marked clean or conflict. Exit 0 nothing to take, 2 updates available. Then it can apply:
  - **`--apply`** takes what needs no decision: every changed row whose fields are all clean, and every added row that has no collision. A row with any conflict is left alone and listed. A row gone upstream is left alone too, since detaching it is a decision about a row that may be in play.
  - **`--actions FILE`** is the API's own action list (`apply` with `keep_local` and `take_upstream` for each conflict, `add` with a resolution, `detach`), for anyone who wants to decide row by row. It cannot be combined with `--apply`.
  - **`--dry-run`** and **`--yes`** as for `copy`; `--dry-run` is only for `--apply` or `--actions`, since `updates` alone writes nothing.
  - **After `--apply`**, the exit code is 2 if anything was left for a decision (a conflict, a collision, a row gone upstream) and 0 if everything was taken. With `--json` it prints `{"result": <the API's answer or null>, "left": {...}}`.

### What it needs

Nothing in `apps/api` changes. The client gains the operations these routes already have, each checked against the dumped schema, and the generated models already include every request and response type involved.

## Not in scope

- **Browsing a repository before copying it** (`GET .../repositories/{id}/entities` and `/stat-groups`), and **the contributions listing**. Both are reads a person can make with `lorenzo api` ([ADR 0161](0161-lorenzo-api-passthrough.md)) and neither blocks the rest.
- **Removing a grant from the subscriber's side** (`DELETE .../repositories/{id}`). The repository's owner can `revoke`; a subscriber giving one up is rare and also available through `lorenzo api`.
- **The `dnd5e` layer split** (RFC 0025 R8). It has to be decided before the first publish or grant, and these commands are what make that moment reachable from the terminal. They don't decide it. Anyone running `repo publish` on a seeded repository should have read R8 first.
- **Copying part of a repository, and rewriting links after a slug rename**, which ADR 0119 left out.

## Consequences

- The whole life of a repository, from `tenant create` to taking its updates, can be done from the terminal and scripted.
- `copy` and `updates --apply` write many rows in one API transaction. Nothing here limits their size, as RFC 0024 already notes.
- The CLI now carries a second table of the API's problem types it has opinions about (`repository-already-copied` and the needs-choices ones), kept to what the commands say in words, as `pack give` does for packs.
