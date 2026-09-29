# 0143 - `lorenzo seed`: the item taxonomy and the stat definitions

Status: accepted

Slice 5 of [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R3, R8, R9). Builds on [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md), and uses [ADR 0139](0139-name-an-item-when-it-is-created.md) and [ADR 0141](0141-fractional-weights-in-the-named-columns.md).

## Context

Before an MPMB item can be imported, a tenant needs somewhere for it to go: prototypes to descend from (a weapon, a container, "martial"), the stat groups and definitions its values are written to, and the weight recipe that makes a backpack weigh its contents. RFC 0025 decided what these are (R8, R9) and that the importer creates them itself, once, with its own step.

Two properties make this the part to get right first. Stat groups and definitions have no `PATCH` or `DELETE` ([ADR 0014](0014-stats.md)) and are frozen in every copy of a repository ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [ADR 0121](0121-repository-updates-and-re-sync.md)), so a name or a type chosen here is chosen for good. And a tenant's `kind` is fixed when it is created ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), so where it is written decides whether it can ever be published.

## Decision

### The seed is data

`src/lorenzo_cli/seed/builtin.toml` holds it, and `seed/spec.py` validates it on load (unique names and slugs, parents listed before children, tags that are `bool` definitions, recipes that refer to things that exist). A mistake in the seed is a failing test, not a half-seeded tenant.

- **Six stat groups:** `physical`, `economic`, `destroyable`, `damaging`, `tags`, `sourcebook`. The conventional five exist in every seeded tenant, empty or not, so two game systems never both try to create one.
- **Twelve stat definitions,** as R9 decided: `own_weight`, `weight`, `contents_weight` (float), `range_normal`, `range_long` (int), `price` (int, in copper), `armor` (int), `is_container` (bool), `sourcebook` (text, the citation), and `damage_dice_count`, `damage_die` (int), `damage_type` (text).
- **Twenty-two taxonomy nodes.** Core: `physical-object`, under it `weapon` (with `melee-weapon` and `ranged-weapon`), `armor` (with `shield`), `tool`, `container`, `ammunition`, `gear`. D&D 5e: three abstract axis roots (`dnd5e-weapon-proficiency`, `dnd5e-armor-tier`, `dnd5e-tool-proficiency`), each with its three members as parentless mixins under it. Every node is an ordinary item created with `in_public_catalog=false`, so the re-parenting tools of [ADR 0073](0073-item-prototype-graph-inspection-and-bulk-editing.md) work on it.
- **A `layer` on every group, definition, node and recipe:** `core`, or `dnd5e`. D&D's slugs start with `dnd5e-` exactly when their layer is `dnd5e`, which the loader checks, so a taxonomy slug never has the shape of an item slug. The `damage_*` definitions are `dnd5e` now, since a definition can't be moved later; their group is `core`.
- **The weight recipe,** on `physical-object`: `contents_weight = contents(weight)` and `weight = sum(own_weight, contents_weight)`. Importing MPMB's weight into `own_weight` and never into `weight` is what keeps a direct value from beating the recipe and stopping a container from counting its contents.
- **`container` carries the `is_container` tag,** which everything under it inherits.

### The command

`lorenzo seed --tenant <id|slug> [--layer core|dnd5e ...] [--dry-run] [--yes] [--allow-play-tenant] [--json]`.

- **It reads, then plans, then writes.** It lists the tenant's groups and definitions, resolves the seed's slugs in one batch, and reads the existing nodes and recipes. Everything is find-or-create by name or slug; nothing is ever changed or removed, so it is safe to run again, and to run over a tenant that already has some of it.
- **A problem stops it before it writes anything,** and exits 1: a definition that already exists with another type or in another group (a stat can't be retyped or moved, so the person fixes that by hand), a slug held by something that isn't an item, or something a selected layer needs from a layer the tenant doesn't have (D&D's dice need core's `damaging` group, so `--layer dnd5e` on an empty tenant says to seed core first).
- **A warning does not stop it:** a node that exists under other parents than the seed has, or a recipe with another kind of formula. Both are left as they are; putting them right is `--reconcile`'s job in a later slice.
- **Exit codes:** `0` done or nothing to do; `2` with `--dry-run` when there is something to create; `1` on a problem. `--json` prints the plan (tenant id, kind, whether it is published, layers, actions, problems, warnings) for a script to chain on.
- **It asks before writing.** With `--yes` it doesn't; without it and with nobody to ask (stdin isn't a terminal) it refuses and says so, so a script can't write by accident.
- **Where it writes** is R3: an existing tenant only, no `--create-if-missing`. A `play` tenant is refused with the reason (nothing put there can ever be published, since the kind can't change) unless `--allow-play-tenant`. A published repository is allowed and flagged, since subscribers will see the changes.
- **A failure part-way needs no cleanup.** Each step is find-or-create and a node is created and named in one request (ADR 0139), so running it again continues.

### Proof against the real API

`tests/e2e/` starts the real `apps/api` on a fresh database (migrated by Alembic), trusting a fake Authgear that signs real RS256 tokens over a real JWKS document, the counterpart of inventory-web's stack ([ADR 0114](0114-inventory-web-end-to-end-tests.md)) in Python. It runs in `test (apps/cli)`, skips when Postgres isn't reachable, and fails (not skips) in CI. Its tests seed a fresh repository tenant, run it again and find nothing to do, and then use what was seeded: a `Backpack` under `container` holding two lengths of 1.5-weight rope weighs 5.0, and is a container by inheritance.

## Consequences

- The names, types and groups in `builtin.toml` are permanent for every tenant that has been seeded. Adding one later is additive; changing one is impossible in a tenant that has it. `version` in the file is the seed's own version, recorded in the plan header.
- The dnd5e layer can become a repository of its own as a filter ([RFC 0025 R8](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md#r8-the-taxonomy-a-system-neutral-core-and-a-dnd5e--layer)): every entry already says which layer it is in. Whether a copy of a bridge keeps a category minted under an axis root that lives in the core repository is assumed, not tested, and is the first thing to try then.
- About twenty-two items, six groups and twelve definitions are written into a tenant before its first import. That is the cost R8 accepted. ([ADR 0146](0146-a-richer-item-taxonomy-and-keeping-what-the-sheet-says.md) later grew the seed to 61 nodes and 40 definitions.)
- The end-to-end stack costs about a minute in CI, and it is what slices 4 and 6 will be proved with.
