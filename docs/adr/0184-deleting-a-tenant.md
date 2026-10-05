# 0184 - Deleting a tenant

Status: proposed

[ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md) left "deleting a tenant" out of scope, and the maintainer asked for it right after: rebuilding the local repositories needed a command that doesn't exist. This ADR adds it to the API and to the CLI. Tracked in a milestone of its own.

## Context

Nothing deletes a tenant. The API has no `DELETE /tenants/{id}`, so a repository that was seeded wrongly, a table that was only a trial, or a stack that is to be built again stays for good, with its slug taken. The only way out today is to delete the row in Postgres as a superuser, which skips every rule of the API, and which was tried on 2026-10-05 against a four-repository stack and a table: the row goes, every table that carries a `tenant_id` cascades, nothing is left behind, and the slug is free again.

Two things make this more than `session.delete(tenant)`:

- **Some tables restrict instead of cascading.** `campaign.entity_id` references `entity` with `ON DELETE RESTRICT`, and a cascade from the tenant doesn't promise which table it clears first.
- **Deleting a repository other tenants draw on** would quietly cut them off from their updates.

## Decision

### The route

`DELETE /tenants/{tenant_id}` answers `204`. One transaction deletes the tenant and everything in it, or nothing.

### Who may

Both of these, and neither is enough alone:

- **The platform `tenant-creator` role**, the one that gates creating a tenant. It is checked first, so a caller without it gets `403` (`tenant-creation-forbidden`) whatever the tenant is.
- **Being one of the tenant's OWNERs.** A caller who isn't a member of the tenant gets the same `404` as for a tenant that isn't there ([ADR 0023](0023-authgear-token-verification.md)); a member who isn't an owner gets `403` (`tenant-deletion-forbidden`). Narrower than renaming it, like membership management ([ADR 0036](0036-user-player-character-crud-api.md)).

Any one owner may delete it, with other owners present or not. They are told (below), not asked.

### What is refused

A tenant that is a **repository other tenants still hold a grant on** answers `409` (`repository-still-granted`) and nothing is deleted. Deleting it would cut those tenants off from its updates without anyone having chosen to. The way out is the existing one: take the grants back (`lorenzo repo revoke`), or delete the tenants that hold it. Deletion then follows the order the stack was built in, backwards: the table, the bridge, the equipment and the rules, core.

There is no `force`: revoking is one explicit step per tenant, and the repository API already has it ([ADR 0032](0032-item-and-item-instance-crud-api.md) took the same view of deleting an item that something inherits from). Nothing else is refused. A tenant that *holds* grants loses them, and the repository it held is untouched.

### What goes

Everything that carries the tenant's `tenant_id`, which is every tenant table ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md), [0018](0018-sqlalchemy-modeling-conventions.md)): one `DELETE` of the tenant row, and the foreign keys cascade. Tried on 2026-10-05, through the API as the restricted role, on a tenant that holds one row of every content table plus a campaign, a GM, a player and a character: no row with its `tenant_id` is left. The campaigns are deleted first, in the same transaction, because `campaign.entity_id` is the one reference to `entity` that restricts instead of cascading, and a cascade doesn't promise the order it clears tables in. (It cleared them in a working order in the test; the explicit delete makes that not a matter of luck.)

What stays: **accounts** and their roles, and **what other tenants copied** from the tenant, which they keep as their own data ([RFC 0024](../rfcs/0024-repositories.md) §6) but which no longer knows where it came from, so it can't take updates. A tenant's record that it copied the repository stays as well, as it does when a grant is only revoked (it holds a plain id, because the repository is another tenant's and may go): `repo list` still names it, as it was, with no slug. `loot-bot` keeps its own record of a linked tenant ([ADR 0050](0050-loot-bot-stack-linking-and-isolation.md)), and a link to a deleted tenant answers `404` when it is used.

### Who is told, and what is recorded

- **The tenant's own activity log goes with it**, and the log has no platform scope to keep a copy in ([ADR 0063](0063-tenant-activity-log.md)).
- **Everyone with standing in it is told**, except the person deleting it: members, players and GMs get a notification, "*name* was deleted". It is platform-scoped, with no `tenant_id`, because a tenant-scoped one would be deleted with the tenant. `created_by` is the deleting owner.
- **The application logs it** (`tenant_deleted`, with the tenant's id and slug and the actor's id), the one trace outside the database.

### The CLI

`lorenzo tenant delete <tenant> [--yes] [--json]`, through one new operation (`DELETE_TENANT`) and no new model:

- It reads the tenant first (a slug or an id, as `tenant show` does), shows it, and asks the person to **type its slug**. A wrong one deletes nothing. A y/N wasn't enough for something that can't be undone.
- `--yes` skips the question. `--json` never asks and needs `--yes`, like every command that writes ([ADR 0156](0156-json-on-apply-and-pack-give.md)); it prints the tenant that was deleted.
- The API's refusals are shown in its words with the HTTP status. The `409` adds the next step: `lorenzo repo subscribers --tenant <slug>` lists who holds it and `lorenzo repo revoke <tenant> --tenant <slug>` takes one back.
- Exit 0 when it is deleted, 1 for anything else, including a declined question.

## Not in scope

- **An undo, or a soft delete.** A deleted tenant is gone.
- **Emptying a tenant and keeping it** (a purge). Deleting and creating it again under the same slug does the same, and the slug is free.
- **Several tenants in one command.** Five tenants are five commands, each with its own question.
- **Account hub.** It isn't given a button, and `GET /me`'s `capabilities` doesn't gain a `delete_tenant`.
- **Deleting an account**, which exists ([ADR 0036](0036-user-player-character-crud-api.md)), and anything `loot-bot` keeps about a tenant in its own database.

## Consequences

- **Starting a stack over is a command**, and the README's "empty the local database" advice for rebuilding goes. [ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)'s record of what was done at the time stands as written.
- **One owner can delete a tenant that has others.** They are told afterwards. A guard that needs the other owners' agreement would be a feature of its own.
- **The order of deleting a stack is the order of building it, backwards**, and the refusal names the way out.
- **Nothing in the database says a tenant was deleted.** The notifications and the application's log are the trace, which is what the missing platform-scope log ([ADR 0063](0063-tenant-activity-log.md)) allows.

## Tests

- **API, through real tokens** (`test_api_tenant_deletion.py`): an owner with the role deletes a tenant that holds a row of every content table, a campaign with a GM, a player and a character, and no row with its `tenant_id` is left (every table that has the column is checked), the members, GM and player are notified on notifications that survive and the owner is not; a non-member gets `404`, a member who isn't an owner and an owner without the role each get `403`, and nothing is deleted or sent; a repository with a grant is refused with `409` and deleted after the grant is revoked; deleting the tenant that holds the grant ends it and keeps the repository; a table's copy, and its record of having copied it, outlive the repository it came from.
- **CLI unit tests**: the slug is asked for and a wrong one deletes nothing; `--yes`; no question and no request where nothing can be asked; `--json`; the `409`'s way out; a `403` and a `404` in the API's words.
- **CLI end to end against the real API** (`test_tenant_delete.py`): a stack of core, the equipment and a table is refused top-down and deleted bottom-up, built again under the same slugs; `--json`; an owner without the role is told so.
