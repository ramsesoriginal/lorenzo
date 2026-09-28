# 0127 - Contents formulas: adding up a stat over what's inside

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §6 decided a second new formula kind, `contents`. It revises [RFC 0016](../rfcs/0016-stats-computed-values-and-crud-api.md)'s exclusion of cross-entity aggregation, for this one kind.

Every formula so far ([ADR 0104](0104-computed-stats.md), [ADR 0126](0126-sum-formulas.md)) reads stats of the entity being read. A backpack's weight depends on what's in it, and a being's carried weight on what it holds in its hands. Those are stats of other entities.

## Decision

### The kind

`contents` is `Σ stat × quantity` over the entities contained **directly** in this one. `quantity` is each containment row's stack count ([ADR 0041](0041-containment-quantity-and-stacking.md)).

The stat is resolved on each thing inside, with its own formulas. So a formula over nested containers falls out of two formulas that each read one level, with no recursion in the formula itself:

- `contents_weight = contents(weight)`;
- `weight = sum(own_weight, contents_weight)`.

### Schema (one migration)

- **`computed_stat_contents`**: the kind row, keyed and cascading like `computed_stat_linear`, with `source_stat_definition_id`.
  - The source doesn't cascade (`NO ACTION`), as with ADR 0104's other inputs.
  - It has `tenant_id`, same-tenant keys ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)), `tenant_isolation` with `FORCE ROW LEVEL SECURITY`, and `repository_read`, since it's repository content ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)).

### Body and checks

`{ kind: "contents", source_stat_definition_id }`. A `422` refuses:

- a source or target that isn't a number stat;
- an `int` target reading a `float` source, since the total could be a fraction and this kind has no rounding mode (chain a `linear` or `sum` to round).

A `contents` formula may read the stat it defines (`weight = contents(weight)`): that reads the stat of each thing inside, not its own.

### What it counts

- **A thing inside without the stat counts as 0**, and so does one whose stat has no value. An entity with nothing in it gives 0. One unweighed torch mustn't blank a whole backpack.
- **Everything physically inside counts**, including what the reader can't see ([ADR 0040](0040-item-instance-read-visibility.md)). Weight is a physical fact; the maintainer chose this knowingly.
- **Beings too.** A familiar in a backpack weighs what its own stats say.

### Evaluation

Evaluation stays pure Python over loaded rows (ADR 0104). What a `contents` formula reads is loaded first, and only when one wins on an entity being read:

- **The entity's containment subtree**, from `entity_access`'s path-guarded walk ([ADR 0016](0016-containment.md)), to its depth cap of 50. Something deeper counts as having nothing inside.
- **What's directly inside each entity in it**, with stack counts. This also covers a row leading back into the subtree, so a containment cycle is seen, not cut short.
- **The effective stats of every entity in the subtree**, with their formulas.

Each read path that serializes stats does this loading for the entities on its page, in one set of queries per page: entity detail, the item catalog, and item instances (list, detail, by slug, owned-by, unowned, held-by, and the response after each write).

**Cycles.** A formula cycle already leaves the stats in it without a value. A containment cycle now does too: a pack inside its own pouch has no `contents_weight`, and neither does anything whose value depends on it. The same holds for a containing stat outside the cycle. Anything else inside still counts as 0 when it has no value.

### Authoring and repositories

- **The write-time cycle check** adds no edge for a `contents` formula. It reads a level down, never a stat of the same entity, so `weight` reading `contents_weight` reading each child's `weight` is legitimate.
- **Preview** returns the total. Its `inputs` list is empty, since what it reads is spread over what's inside.
- **The dependents lookup** reports a `contents` formula reading the stat as `kind: "contents"`.
- **Repositories** copy, update, re-sync, and purge it like the other kinds ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [ADR 0121](0121-repository-updates-and-re-sync.md)).

### A reference page

`docs/reference/well-known-stats.md` starts here. It names the stats the API reads by name, today only `is_container` ([ADR 0066](0066-is-container-computed-field.md)), and gives the weight recipe as tenant data on base prototypes. Slices 6 and 7 add the names they read.

## Not in scope

- **Capacity checks** that read these totals, slice 6.
- **Scaling or rounding inside a `contents` formula.** Chain a `linear` or `sum`.
- **Aggregating over anything but direct containment**, such as group members (RFC 0030's own exclusion).
- **Caching totals.** They're evaluated live on every read, like every other formula.

## Consequences

- A container's weight, and a being's carried weight, are one recipe of tenant data, and a system without encumbrance simply doesn't define it.
- A read with a winning `contents` formula costs a subtree walk and one effective-stat load for everything in it. A read without one costs nothing more.
- A read path that serializes stats without loading contents first shows no value for a `contents` stat. Each read path is covered by a test.
- **An accepted breaking change to the API contract.** A formula in a response can now be `contents`, and the dependents lookup can report `kind: "contents"`. The oasdiff findings are listed in `apps/api/openapi-breaking-accepted.txt`, and the change ships with a `BREAKING CHANGE` footer.
