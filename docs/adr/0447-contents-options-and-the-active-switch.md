# 0447 - The options of a `contents` formula, and the `active` switch of an item instance

Status: accepted, built (2026-11-11). Slice K4 of [RFC 0053](../rfcs/0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md),
the last. Builds on [ADR 0127](0127-contents-formulas.md) (`contents`), [ADR 0128](0128-capacity-and-moving-anyway.md) and
[ADR 0129](0129-binding-and-lifting-it.md) (what holding a thing means), [ADR 0040](0040-item-instance-read-visibility.md) (who reads an
instance) and [ADR 0444](0444-min-max-and-a-bool-or-an-enum-as-a-number-in-a-formula.md) (how a kind is added).

## Context

`contents` sums a stat over everything directly inside an entry, so a spare armour that is only carried counted, a count of what is
attuned was a sum of ones, and the best of what is worn had no formula. The workaround was a container for each rule, and the
decision of what counts sat in the container instead of on the thing.

## Decision

- **A contents formula takes options, each with the default that is today's behaviour.**
  - `aggregate`: `sum` (the default, `Σ stat x stack count`), `min`, `max`, or `count`. `min`, `max` and `count` ignore the stack
    count; `count` ignores the stat too, so `source_stat_definition_id` is left out for it and is needed for the others.
  - `only_active` (false): skip a held thing whose `active` switch is off. A thing that has no switch is never skipped.
  - `only_kind` (none): keep one kind of held thing; `item_instance` is the one there is, and a feature instance joins it with
    RFC 0054.
  - `where_stat_definition_id` (none): a `bool` stat that must be true on the held thing, else it is skipped.
  - `if_none` (none): a constant for `min` and `max` of nothing, which have no value without it. `sum` and `count` of nothing are
    0, as `contents` is today. `if_none` for any other aggregate is a 422.
  A `min` or `max` takes what has a value and ignores what has none; the stat is a number, and an `int` stat does not take a `float`
  one, since a contents formula does not round (as before). The body is `{"kind": "contents", "source_stat_definition_id": ...,
  "aggregate": "sum", "only_active": false, "only_kind": null, "where_stat_definition_id": null, "if_none": null}`, every option
  optional.
- **An item instance has `active`, true by default.** It is a `bool` field of the instance, read as `active` on every item
  instance response, written by `PATCH /item-instances/{id}` with `{"active": false}` under the rule that already governs editing the
  instance (anyone whose characters or groups reach it, or a GM of its owner's campaigns, ADR 0124), and not nullable. It does not
  move, free or bind the thing: weight, size and capacity count it either way, and a binding is unchanged. It is not an activity-log
  event.
- **A prototype says how its instances start.** An item has `starts_inactive` (false), in `POST /items`, `PATCH /items/{id}` and the item
  response. An instance made from it, directly or from a pack, starts inactive unless the request carries `active`; one that
  already exists keeps its switch when the prototype's rule changes. A piece split off a stack, and a part that changes hands,
  keep the switch of what they came from.
- **A repository carries the options and the rule.** A copy carries a contents formula's options and an item's `starts_inactive`, and
  a copied instance starts as its prototypes say, as a new one would (an instance's own switch is play state, not content). An
  update that changes either is proposed like any other field; the snapshot of a contents formula that sums everything, and of an
  item that starts active, is what it was, so no update is proposed for the ones that were there before.
- **The explanation counts what was taken.** `contents.things` is how many things the options kept (after `only_active`, `only_kind`
  and `where`, and for `min` and `max` those that had a value); `source_stat_definition_id` and `source_name` are empty for a `count`.
- **A stat that a formula reads is not deleted.** `DELETE /stat-definitions/{id}` already answered 409 for a stat a formula reads; it
  now counts what every kind since ADR 0444 reads, and a contents formula's `where` stat.

## Design

`computed_stat_contents` gains the columns `aggregate`, `only_active`, `only_kind`, `where_stat_definition_id`, `if_none`, with a
same-tenant key for the stat and checks for the values; its stat column may be null, which a check allows for `count` alone.
`item_instance.active` and `item.starts_inactive` are columns, and `v_item_instance` exposes `active` (a view gains a column only at
the end, so it is replaced with the same query and the new column last). `stat_contents.load_contents` reads each held thing's
switch in the containment query it already runs, with an outer join to the instance, so a read that uses a contents formula costs the
statements it did. Release documents move to **format 40**: a formula carries the options, and the document carries which items start
inactive (version 39 is read as a sum of everything inside, and every item as starting active).

## Validation and delivery

A test for each: the default still summing every thing times its stack, `only_active`, `only_kind`, a `max` over what is worn with
`if_none` and without, `min` ignoring a thing with no value, `count` with a `where` and no stat, a stack multiplying a sum and no
other aggregate, the shape and type errors, a stored formula's defaults, preview, `things` and dependents, the 409 for a stat a
formula filters by, an instance active by default and flipped by its holder (and 422 for null), starting as the prototype says, a
repository copy carrying the options, an item's `starts_inactive` and an instance's start, and a release document round trip. The
OpenAPI change is `active`, `starts_inactive` and the options, none of which breaks a client; the CLI models and
`packages/api-client` are regenerated.

## Consequences

- Armour class from what is worn, a dexterity cap, and attunement used are each one formula, and the thing says whether it counts.
- A held thing grows a switch which a library's sheets and boards may show.
- RFC 0053 is built: ten formula kinds, and the guide "Modelling a game system" loses the recipes these replace.
