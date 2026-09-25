# 0120 - Bridge repositories and dependency manifests

Status: accepted

## Context

[RFC 0024](../rfcs/0024-repositories.md) §5 and §9 describe **bridge** repositories. `dnd_faerun` joins a setting (`Faerûn`) to a rule system (`D&D 5e`) by holding its own copies of both and authoring entities that inherit from each: "Blackstaff (D&D 5e)" has two prototype parents. A tenant copying the bridge needs both dependencies too, and it should take one action, not three.

The amendment (A8) settles what that means here. Grants aren't transitive, since a bridge's owner can't grant somebody else's repository. A bridge carries only what it authored. Every copy link names an origin. This ADR builds that on [ADR 0119](0119-copying-a-repository-into-a-tenant.md)'s copy.

## Decision

### A bridge is a repository that has copied others

No new kind or flag. A repository tenant can be granted other repositories and copy them ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)/ADR 0119), like any tenant. Its **dependencies** are the repositories its `repository_copy` rows name. Its own entities can then inherit from, contain, own, or know about its copies, which is how Blackstaff (D&D 5e) is authored.

### The manifest

A repository's manifest is its dependencies, then itself, in dependency order. A dependency's own dependencies are already among the bridge's, because the bridge had to copy them before it could copy that dependency. So one level is the whole set. The order comes from each dependency's own `repository_copy` rows, read through the gated read.

ADR 0119's `copy-plan` shows the manifest, one step per repository. Each step says whether the subscriber holds a grant for it, whether it is published, and whether the subscriber has already copied it. `POST .../copy` on a bridge:

- is refused with `409 repository-copy-needs-grants` while any step lacks a grant or is unpublished, naming each one;
- otherwise copies every step not yet copied, in order, in one transaction;
- reuses steps already copied. A tenant that copied `D&D 5e` last month and `Faerûn` last week, then adds `dnd_faerun`, gets only the bridge's own rows, with every edge pointing at the copies it already has.

Collisions across all the steps are gathered into one list and resolved in one call, in manifest order (ADR 0119).

### Re-targeting

Only a repository's own rows are copied. When one of them refers to a row the repository itself copied, the reference is re-targeted in two steps:

1. The repository's own copy link names that row's origin: `(source_tenant_id, source_id)`.
2. The subscriber's link for the same origin names its local copy.

If the origin belongs to the subscriber itself, which happens when two tenants have copied each other, the local id is the origin id. If the subscriber skipped the origin, or has deleted its copy, that one row is dropped and reported, as in ADR 0119.

A stat group or definition a repository merged into one of its own (ADR 0119's `merged`) counts downstream as a copy of the origin it was merged with, not as the repository's own row. The merge said "this is the same Strength", so a subscriber's references land on its own copy of that Strength.

### What a bridge doesn't carry

- **Its edits to its copies of its dependencies.** If `dnd_faerun` renamed its copy of Waterdeep, or gave it a stat value, that stays in `dnd_faerun`. Subscribers get Waterdeep from `Faerûn` directly. To make an upstream entity behave differently under a system, the bridge authors a new entity that inherits from it.
- **Rows between two copied entities.** A containment or ownership between two of the bridge's copies isn't the bridge's own, for the same reason.

## Consequences

- One copy brings in a whole stack, in the right order, and it's repeatable: adding a second bridge onto the same dependencies costs only the bridge's own rows.
- A subscriber needs a grant from every owner in the stack. That's more asking than the RFC's "one action" suggested. It is the honest cost of not letting one owner hand out another's content.
- A bridge's authors learn that editing a copied entity doesn't reach anyone downstream. The copy-plan says so for a bridge, and the RFC's own reasoning (curated, reviewed composition over live pass-through) is why.
