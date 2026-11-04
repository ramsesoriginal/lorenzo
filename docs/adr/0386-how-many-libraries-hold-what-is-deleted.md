# 0386 - How many libraries hold what is about to be deleted

Status: accepted, decided with the maintainer on 2026-11-03. Slice K9 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §9 and its Spike 2, tracked in #974. Builds on [ADR 0119](0119-copying-a-repository-into-a-tenant.md) (the copy links), [ADR 0204](0204-the-owner-sees-who-copied-a-repository.md) (the policy this follows), [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md) (`DELETE /entities/{id}`), [ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md) (deleting a stat) and [RFC 0040](../rfcs/0040-authors-and-invites.md) (who may delete what).

## Context

Deleting an entry, a stat definition or a stat group in a repository does not touch what a library copied: the library sees the row as removed upstream and keeps its own ([ADR 0121](0121-repository-updates-and-re-sync.md), [ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)). The author deciding to delete has no way to know whether anyone holds it. The links that say who copied what are rows of the copying library, under its own `tenant_isolation`, which the repository cannot read. RFC 0041 decided that the delete warns with a number and never blocks, and left the mechanism to a spike.

## Decision

### The mechanism: a gated `SELECT` policy on the copy links

Spike 2 (findings in RFC 0041) tried a `SECURITY DEFINER` function, a policy and a maintained counter against 20,000 copy links as the restricted role. The policy won:

- **`repository_owner_count`**, a `SELECT` policy on `repository_copy_link_entity`, `repository_copy_link_stat_group` and `repository_copy_link_stat_definition`: a row is visible to the tenant it was copied **from** (`source_tenant_id` is the current tenant) **and only while `app.library_count` is `on`**. Writes stay under `tenant_isolation`. It is the setting-gated pattern of the release fan-out ([ADR 0301](0301-release-fan-out-and-cooldown.md)) on the owner-side read of [ADR 0204](0204-the-owner-sees-who-copied-a-repository.md), and `library_counts.counting_libraries` is the only code that sets the setting, for the one query, as `reading_repository` is for the gated read.
- **A `SECURITY DEFINER` function is not used.** Every tenant table has `FORCE ROW LEVEL SECURITY`, so such a function counts nothing unless its owner is a superuser or has `BYPASSRLS`, which the repository does not say of the production role. No migration uses one, as RFC 0041 says.
- **A partial index** on each table, `(source_tenant_id, source_id)` where the local id is not null, keeps the count an index scan.
- **What it exposes.** A session that sets the setting can read the copier's tenant id, its local id and the snapshot of every link to this repository, not only the number. The routes select `count(*)` and nothing else, and the only helper that sets the setting is the count's; this is what ADR 0204 accepted for `repository_copy`, one table further.

### What is counted

The number of tenants that hold a copy of the row: a link to this row whose local id is not null. A library that deleted its copy has a link with a null local id and is **not** counted; one that copied it twice (a copy again) is counted once, as a link is one row for each origin. A link recorded as `merged` (a stat the library already had, merged into its own) counts: the library holds it. A repository that copied another one (a bridge) counts as a holder like a play library; the screens say libraries.

### The routes

Under `/tenants/{tenant_id}`, each answering `{count}` (`LibraryCountOut`) and **never a name**:

- `GET /entities/{entity_id}/libraries`: any member of the repository, an Author included, since an Author may delete an entry nobody inherits from "with the count warning" ([RFC 0040](../rfcs/0040-authors-and-invites.md)).
- `GET /stat-definitions/{id}/libraries` and `GET /stat-groups/{id}/libraries`: an admin, as the deletes are.

A row that is not in the tenant is `404`. A tenant that is not a repository answers `0` (nothing was ever copied from it), so a client need not ask what kind a tenant is first. It is a read, not a gate: nothing requires it before a delete, a script may skip it, and the deletes are unchanged.

### The activity log

`DELETE /entities/{id}`, `DELETE /items/{id}`, `DELETE /stat-definitions/{id}` and `DELETE /stat-groups/{id}` count in their own transaction before the row goes, and append `libraries=N` to the activity entry when N is more than 0. Quiet for the common case; the number is what the person was shown when they decided.

### In Bench and the command line

- **Bench** deletes an entry for the first time. The entry pane has **Delete**, which opens a line of its own under the name: it says what goes, how many libraries have copied it ("3 libraries have copied this. They will see it as removed upstream.", "No library has copied this." or, when the count could not be read, "Could not tell how many libraries have copied this."), and asks to confirm. The delete is a direct, online call like the vocabulary's ([ADR 0253](0253-bench-formulas-and-the-stat-vocabulary.md)), not a command: it cannot be undone, is refused while changes of that entry wait to be sent, and says so. The stat delete in the Vocabulary pane says the same count in its confirmation.
- **The command line** gets `lorenzo repo libraries`, which prints the count for an entry, a stat or a stat group, and `lorenzo unseed` (the one command that deletes) prints how many libraries hold the stats and items it is about to delete when the tenant is a repository, in its plan.
- **Studio** has no screen that deletes an entry, a stat or a stat group, so it gets nothing here.

## Not in scope

- Who the libraries are. The names are not read, and the owner can already list who copied a repository ([ADR 0204](0204-the-owner-sees-who-copied-a-repository.md)).
- Counts for anything but an entry, a stat definition and a stat group, and a count of libraries that still use a row in play.
- Requiring an acknowledgement, or blocking: both were decided out in the RFC.

## Consequences

- The author sees what a delete will mean before it is made, and the log records what they saw.
- Three policies, three indexes and one setting are added to the database; the conformance tests pin only `repository_read`, so a test here pins this policy: only the repository's own session, with the setting, reads the links.
- The count is one query per delete in the four delete routes of a repository.
- Entry deletion in Bench is new and online only; making it a command with undo is later.
