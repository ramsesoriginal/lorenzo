# 0166 - A bare `seed` refuses to add a layer to a tenant that holds another

Status: accepted

Amends [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) and [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md). Decided with the maintainer on 2026-10-04, after a bare `seed` put the D&D 5e layer into the `core` repository.

## Context

`lorenzo seed` without `--layer` seeds every layer the tenant is missing ([ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md)). That default fits an empty tenant that is meant to hold everything, and [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) kept it. It is wrong for a repository that was seeded with one layer on purpose: there a bare `seed` quietly adds the other one. The maintainer ran a bare `seed` over `core` while repairing description titles ([ADR 0165](0165-a-description-is-titled-with-its-items-name.md)), following instructions that left `--layer` out, and got 22 stat definitions, 28 categories, 12 descriptions and 10 tags of D&D 5e in a repository meant to be system-neutral. Stat definitions can't be undone through the API ([ADR 0014](0014-stats.md), [ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)), so the cheap place to stop this is before the write.

## Decision

**A bare `seed` is a problem when the tenant already holds one layer and none of another.** A tenant *holds* a layer when it has at least one of that layer's categories or stat definitions, found by slug and name as the seed always finds them. The plan then says so as a problem, nothing is written, and the exit code is 1, as for any other problem in a plan:

> This tenant holds the core layer and none of dnd5e. A bare seed would add dnd5e. Name the layers you mean: `--layer core` to check or complete what it holds, or `--layer dnd5e` to add that layer.

- **An empty tenant** is seeded with every layer, as before, with the same advisory about publishing them separately.
- **A tenant that holds every layer, or part of each** is completed, as before.
- **`--layer` is never refused by this rule.** Naming a layer is the deliberate act: `seed --tenant dnd5e --layer dnd5e` over a repository that holds a copy of core is the flow [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md) describes.
- **`--dry-run` and `--json` show the same problem**, so a dry run tells the truth about what a real run would do.

## Not in scope

- **Making `--layer` mandatory**, or changing what an empty tenant gets. That would break every existing invocation for no gain to someone seeding a table's own tenant.
- **Remembering which layers a tenant is meant to hold.** Nothing is stored for it: what the tenant holds is read from the tenant, so a copy of a repository, a seed and a hand-built tenant are all judged the same way.
- **Taking a layer back out.** [ADR 0168](0168-lorenzo-unseed.md).

## Consequences

- `plan.problems` gains one entry for this case, and `seed`'s README and `--help` say to name the layer on a tenant that holds one.
- Anyone relying on a bare `seed` to add a second layer to a seeded repository now types `--layer` once.
