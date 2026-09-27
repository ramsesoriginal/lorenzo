# 0126 - Sum formulas: adding up several stats of one entity

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §6 decided two new formula kinds for computed stats ([ADR 0104](0104-computed-stats.md)). This is the first, `sum`. The second, `contents`, is slice 5.

A `linear` formula reads one stat. Many derived stats read several:

- `armour_class = 10 + dex_modifier + worn_ac_bonus`;
- `current_hp = max_hp − damage`;
- `weight = own_weight + contents_weight`, the step that lets slice 5's recipe add a container's own weight to what's inside it.

Chaining `linear` formulas through intermediate stats can't express any of these, since each one still reads a single stat.

## Decision

### The kind

`sum` is `round(Σ coefficient × stat + offset)` over one or more stats of the same entity. It's `linear` with more than one term: it evaluates, is authored, previewed, and cycle-checked the same way.

### Schema (one migration)

- **`computed_stat_sum`**: the kind row, keyed and cascading like `computed_stat_linear`, with `offset` (`NUMERIC`, default 0) and `round_mode` (linear's five modes, default `none`).
- **`computed_stat_sum_term`**: one row per term, with `source_stat_definition_id`, `coefficient` (`NUMERIC`, default 1), and `position`, which keeps the order the author wrote.
  - Its primary key is the formula's key plus the source, so a stat appears in a sum at most once.
  - Terms cascade from their sum row. A source doesn't cascade (`NO ACTION`), as with ADR 0104's other inputs.

Both tables carry `tenant_id`, same-tenant keys ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)), `tenant_isolation` with `FORCE ROW LEVEL SECURITY`, and `repository_read`: they're content a repository can hold ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)).

### Body

`{ kind: "sum", terms: [{ stat_definition_id, coefficient }], offset, round_mode }`. `coefficient` defaults to 1, `offset` to 0, and `round_mode` to `none`.

A `422` refuses:

- no terms, or more than 20;
- the same stat twice (use a coefficient instead);
- a term that isn't a number stat, or a target that isn't one;
- the target stat itself among the terms.

### Rounding an int stat

ADR 0104 made an `int` target need a rounding mode other than `none`, so a formula can never produce a fraction for it. That's needed only when a fraction is possible. A formula whose every input is an `int` stat, and whose coefficients (or multiplier) and offset are all whole numbers, always gives a whole number.

So an `int` target may keep `none` in exactly that case, for `sum` and for `linear` alike. This loosens ADR 0104's rule without breaking anything it accepted: `armour_class = 10 + dex_modifier + worn_ac_bonus` and `carry_capacity = strength × 15` need no rounding mode.

### Evaluation

The sum resolves each term's stat on the entity being read, as `linear` does. If any term's stat has no value, the sum has none either (ADR 0104's rule for unresolved inputs). A sum can read other formulas, including sums, in dependency order.

### Authoring and repositories

- **The same routes.** The `PUT`, `DELETE`, list, preview, and dependents routes of ADR 0104 take and return `sum` like the other kinds. The preview lists every term's stat among its inputs. The dependents lookup reports a sum reading the stat as `kind: "sum"`. The cycle check adds an edge from the target to each term's stat.
- **Repositories.** A sum is copied ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)), updated and re-synced ([ADR 0121](0121-repository-updates-and-re-sync.md)), and purged like the other kinds. Its snapshot names each term's stat by origin, in order. A sum reading a stat that wasn't copied is dropped whole, like a linear formula whose source wasn't.

## Not in scope

- **`contents` formulas**, slice 5.
- **Non-additive kinds**, like `max`, `min`, or `choose` (RFC 0030's own exclusion).
- **Terms that are constants on their own.** The offset is the one constant; `10 + dex_modifier` is `offset: 10`.

## Consequences

- Armour class, hit points, and a container's weight can each be one stat that adds up others, authored once on a prototype.
- A third kind means every place that enumerates kinds grows by one: evaluation, validation, the dependents lookup, the cycle check, and repository copy, update, and purge.
- `linear` formulas with an `int` target no longer need a rounding mode when the result can't be a fraction. Nothing existing changes meaning.
- **A breaking change to the API contract, accepted.** A formula in a response can now be a `sum`, and the dependents lookup can report `kind: "sum"`. A client that only knows `linear` and `comparison` may not handle it. The three oasdiff findings are listed in `apps/api/openapi-breaking-accepted.txt`, and the change ships with a `BREAKING CHANGE` footer. No app in this repository reads formulas yet.
