# 0160 - `lorenzo repo offer`

Status: accepted

The follow-up [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) R10 reserved. Builds on [ADR 0159](0159-lorenzo-repo-commands.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

R10 named `lorenzo repo offer` and said it needs its own RFC. The maintainer decided on 2026-10-03 to record it as an ADR instead, since R10 already lists its steps and each is an existing API call. The reasoning R10 gave for scope is kept: the realistic caller is **the tenant creator, who owns both the repository and the tenant**, so a person's own token is enough, and unattended use stays out of scope ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)).

What "offer" saves is the pair of steps a new table's tenant needs before it can play on a repository: grant it, then copy it in. They need two different standings (the repository's owner grants; a member of the tenant copies), and for the person who holds both, they are two commands in a fixed order with a plan in between.

## Decision

```bash
lorenzo repo offer SUBSCRIBER --tenant REPOSITORY \
    [--on-collision merge|skip] [--choices FILE] [--apply-updates] [--dry-run] [--yes] [--json]
```

"Offer this repository to that tenant." It does, in order, with R10's steps:

1. **Checks before it writes anything.**
   - `REPOSITORY` must be a repository tenant you own, and it must be **published**. An unpublished repository is refused with "Publish it first: `lorenzo repo publish --tenant …`", not granted and left unusable, since a copy of a draft would be refused anyway.
   - `SUBSCRIBER` must be a tenant you can reach: an id, or a slug among your own tenants. Because resolving it reads the tenant, a tenant you don't belong to fails here, with nothing granted, rather than after a grant that can't be followed by a copy.
2. **Grants it** (`PUT .../subscribers/{id}`). A grant that already exists is fine and is said so.
3. **Copies it into the subscriber**, as a member of that tenant:
   - it plans the copy, and any collision is resolved from `--choices` and `--on-collision` exactly as `repo copy` does ([ADR 0159](0159-lorenzo-repo-commands.md)). An unanswered collision stops it, **after the grant**, which stays: it is idempotent, the plan needs it, and the output says what is left to decide;
   - **`409 repository-already-copied` is success**, not failure, whether the plan shows it or the copy answers it. The tenant already has it. This is what makes `offer` safe to run again.
4. **Optionally takes the clean updates** (`--apply-updates`): when the repository was already copied, it applies what `repo updates --apply` would, and nothing that needs a decision. Without the flag, `offer` says whether updates are waiting and stops.

### Dry runs and asking

- **`--dry-run` writes nothing at all**, which includes the grant. It reports the repository's state, whether the tenant already has a grant and a copy, and, if there is a grant, the copy plan with its collisions. Where there is no grant yet, it says that the plan can only be made after one. It exits 2 if there would be anything to do and 0 if not.
- **Asking.** At a terminal, `offer` shows what it is about to do (grant, copy, updates) and asks once; `--yes` skips it, and `--json` never asks and needs `--yes` ([ADR 0156](0156-json-on-apply-and-pack-give.md)).
- **`--json`** prints one document with what each step did: `granted` (`"new"`, `"existing"`), `copied` (`"copied"`, `"already"`, or the step counts), `updates` (applied counts or the number waiting).

### Many tenants

One subscriber per call. "Run once, offer to every new tenant" is a loop in a shell around an idempotent command, which is the reason it is idempotent.

## Not in scope

- **Unattended use.** Authgear's machine tokens carry a client id as their subject, not a user, and not the `tenant-creator` role ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)); accepting them is an `apps/api` decision of its own.
- **Publishing as part of `offer`.** Publishing announces to every subscriber, so it stays an explicit `repo publish`.
- **Offering to a tenant by hand-picking what it gets.** A copy is the whole repository ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)).
- **Anything `apps/api` doesn't already do.** Nothing changes there.

## Consequences

- Giving a new table's tenant a repository is one command for the person who owns both, and a safe one to repeat.
- A partial `offer` is possible and visible: grant done, collisions open. That is deliberate, since the alternative is a grant that can't be rolled back by a failed copy, and the next run picks up from there.
- Granting notifies the subscriber's members ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), so `--dry-run` first is how to avoid telling people about something that isn't ready.
