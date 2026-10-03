# 0163 - `lorenzo repo offer` offers what a bridge builds on

Status: accepted

Amends [ADR 0160](0160-lorenzo-repo-offer.md). Needed by [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md), which makes D&D 5e a bridge over core.

## Context

ADR 0160's `offer` grants a repository to a tenant and copies it in. For a bridge that is not enough: a tenant copying it needs a grant on every repository in its manifest, and grants aren't transitive, since a bridge's owner can't hand out somebody else's content ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)). `POST .../copy` is refused with `409 repository-copy-needs-grants` while a step has no grant. With D&D 5e as a bridge over core, offering it would grant D&D and then fail on core, leaving the person to find that out and run a second command.

A repository's dependencies are the repositories its own `repository_copy` rows name, and its members can already read them: the bridge's own `GET .../repositories` lists what it has copied.

## Decision

`offer` also offers what the repository builds on. Besides ADR 0160's steps:

- **It reads the dependencies** from the repository's own list of what it has copied, and, for each, whether the subscriber already holds a grant, and whether the subscriber has already copied it. A dependency the subscriber copied needs nothing: a copy of the bridge reuses it (ADR 0120).
- **It grants each dependency that needs it, first**, before the repository's own grant, with the same rules: an existing grant is fine, and the subscriber's members are told. Doing them first means a dependency that cannot be granted leaves the repository itself not granted.
- **A dependency it cannot grant is a stop, said in words.** Only a repository's owners can grant it. If the person doesn't own it (the API answers `403` or `404`), `offer` says which repository, why, and the command its owners need to run: `lorenzo repo grant <the tenant's id> --tenant <the dependency>`. Anything already granted before it stays, as grants stay in ADR 0160.
- **A dependency that isn't published is refused before anything is written**, as the repository itself is: a copy of it would be refused.
- **One level.** ADR 0120 shows a bridge's dependencies are the whole set, since a dependency's own dependencies are already among the bridge's.
- **`--dry-run`** lists each dependency as `copied`, `granted`, `needs-grant`, or `unknown` (the person isn't a member of it, so can neither see its grants nor make one), and writes nothing. `steps` names each grant as `grant:<slug>`.
- **`--json`** gains `dependencies`: `{slug: "new" | "existing" | "copied"}`, and the asking prompt names them.

A repository that copied nothing has no dependencies, and `offer` behaves exactly as ADR 0160 says.

## Not in scope

- **`repo grant` following dependencies.** It stays one grant per call, which is what it says; `offer` is the command that knows a tenant is about to copy.
- **A dependency's dependencies.** Not needed, per ADR 0120.
- **Granting what the person doesn't own.** Only an owner can, and unattended use stays out of scope ([ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)).

## Consequences

- Offering the D&D 5e repository to a table is one command for whoever owns core, D&D and the table's tenant, and a safe one to repeat.
- Someone who owns the bridge but not core gets a clear message and the exact command to send to core's owners, instead of a bare `409`.
- Where a dependency is already granted or already copied, nothing extra is written, so offering a second bridge over the same core costs only that bridge.
