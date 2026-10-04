# 0168 - `lorenzo unseed`

Status: accepted

The inverse of `lorenzo seed` ([ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md)), and the use of [ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md). Decided with the maintainer on 2026-10-04: after a layer went into a repository by mistake, "an unseed layer that needs confirmation and removes everything from a layer". Its sibling is [ADR 0166](0166-a-bare-seed-refuses-to-add-a-layer-to-a-tenant-that-holds-another.md), which makes that mistake harder to make.

## Context

Taking a layer back out was a script of `lorenzo api` calls, and could not finish: the 28 categories could be deleted, the 22 stat definitions could not. With ADR 0167 the API can delete what is unused, so a command can do all of it, and say what it will do first.

## Decision

```bash
lorenzo unseed --tenant TENANT --layer LAYER [--layer LAYER ...] [--dry-run] [--yes] [--json]
```

**It removes, from one tenant, what the built-in seed made for a layer**, and nothing else. It finds its targets the way `seed` does, by slug and name, so it can't touch anything the seed doesn't name.

1. **The layer's categories** (the seed's nodes: their descriptions and tags go with them).
2. **Its stat definitions.**
3. **Its stat groups.** `core` holds the six conventional ones; `dnd5e` holds none.

`--layer` is required and there is no default: removing is never an accident of leaving an option out.

### Reading before writing

The plan reads the tenant and says what it will do, and what it won't:

- **A category that something outside the layer inherits from is a problem**: imported items under `dnd5e-martial`, say. The plan names it and how many, nothing is deleted, and the exit code is 1. Deleting it would take those items' parents away. What inherits is read from the entity's own record, and the layer's own categories inheriting from one another is fine.
- **A category with item instances** is a problem for the same reason; the API refuses it too ([ADR 0018](0018-sqlalchemy-modeling-conventions.md)).
- **What the plan can't know is whether a stat definition is used**: the API has no list of its users. It is attempted, and the API's `409` is the answer.

### Asking, then doing

- **It asks once**, with what it found: "Delete 28 categories, 22 stat definitions and 0 stat groups of the dnd5e layer from `core`? This can't be undone for the stat definitions." The default is no. `--yes` skips it; `--json` never asks and needs `--yes`; with no terminal it says to run again with `--yes` ([ADR 0156](0156-json-on-apply-and-pack-give.md)).
- **`--dry-run` writes nothing** and exits 2 if there is anything to remove, 0 if not.
- **Order and failure.** Categories first, then definitions, then groups. A definition the API refuses as in use is **kept and listed with its reason**, and the rest go on; a group is only attempted once everything in it went. Anything kept makes the exit code 1. Nothing is undone, and the command can be run again: it finds what is left.
- **`--json`** prints the plan, what was deleted, and what was kept with its reason.

### What it doesn't do

It doesn't treat copied rows differently: unseeding a layer from a tenant that copied it removes the copies, and `repo updates` reports them as deleted locally ([ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md)). The usual use is the other way round: taking a layer out of the repository it went into by mistake.

## Not in scope

- **Removing items that were imported** into a layer's categories. They are the importer's, not the seed's.
- **Forcing past a category or definition that is in use**, or removing the values that use it.
- **A `seed --remove` flag.** A command that deletes is named for it.

## Consequences

- `lorenzo` gains `unseed`; the README's seed section says what it does and that it asks.
- The CLI's operation table gains the two deletions of ADR 0167 and the deletion of an item.
- A mistaken layer can be removed completely, and re-seeded with `seed --layer` if it was wanted after all.
