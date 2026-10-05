# 0184 - Deleting a tenant

Status: proposed

[ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md) left "deleting a tenant" out of scope, and the maintainer asked for it right after: rebuilding the local repositories needed a command that doesn't exist. This ADR adds it to the API and to the CLI. Tracked in a milestone of its own.

## Context

Nothing deletes a tenant. The API has no `DELETE /tenants/{id}`, so a repository that was seeded wrongly, a table that was only a trial, or a stack that is to be built again stays for good, with its slug taken. The only way out today is to delete the row in Postgres as a superuser, which skips every rule of the API, and which was tried on 2026-10-05 against a four-repository stack and a table: the row goes, every table that carries a `tenant_id` cascades, nothing is left behind, and the slug is free again.

Two things make this more than `session.delete(tenant)`:

- **Some tables restrict instead of cascading.** `campaign.entity_id` references `entity` with `ON DELETE RESTRICT`, and a cascade from the tenant doesn't promise which table it clears first.
- **Deleting a repository other tenants draw on** would quietly cut them off from their updates.

## Decision

*(To be filled in as the API is built and tried, before this ADR is accepted: who may delete, what is refused, what goes, what is left, the CLI.)*

## Not in scope

- **An undo, or a soft delete.** A deleted tenant is gone.
- **Deleting an account**, which exists ([ADR 0036](0036-user-player-character-crud-api.md)), and anything about what `loot-bot` keeps about a tenant in its own database.
- **Account hub.** It isn't given a button.
