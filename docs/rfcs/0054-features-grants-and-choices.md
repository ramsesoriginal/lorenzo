# 0054 - Features: what an entry has, how it comes to have it, and what it may choose

Status: accepted (2026-11-11), decided with the maintainer, not built; slices F1 to F4, each its own ADR. It builds on RFC 0052 (a system as a thing, and
templates) and RFC 0053 (formula kinds, including aggregation over what an entry holds and the `active` switch), and on
[RFC 0041](0041-entity-kinds-and-author-freedom.md) (kinds are marker tables) and
[RFC 0030](0030-carrying-holding-binding-and-capacity.md) (holding, binding and capacity). It changes nothing decided about
how a stat resolves ([ADR 0037](../adr/0037-effective-stat-resolution.md), [ADR 0266](../adr/0266-stat-tie-break-by-parent-order.md)).

## Purpose

Give Lorenzo one setting-agnostic way to say that an entry has a typed thing with effects: a character feature, a spell, a
feat, a boon, a playbook move, a cyberware upgrade that is not a physical object, a vehicle modification. Say how an entry
comes to have it (at creation, from a level, from a held item, from another feature, from a GM's award), what it may choose
from a set, what it keeps as its own state, and what stops it having it.

## Decided inputs

1. **Held instances and rules, not a pile of tables.** A feature is held as an instance with its own state, and a small set of
   grant rules says what a source entitles; nothing duplicates containment, stats, capacity or the repository machinery.
2. **Two kinds:** `feature` (the prototype) and `feature_instance` (what a holder has). A feature instance has its own
   `/features` route and no item vocabulary; inventory, the board and the loot bot leave it out by kind.
3. **A grant has a source, and a source is an ancestor or a held thing.** An ancestor of the holder (a race, a class, a
   background, an archetype) or an instance the holder holds. A held source counts only while its `active` switch is on.
4. **A rule's conditions are inline comparisons**, all of which must hold; an OR is a separate rule. Each condition names its
   subject, the holder or the source.
5. **A rule's count is a constant or a holder stat.** Its options are an explicit list or a category entry, and each option may
   carry prerequisites.
6. **Grants are materialised.** Applying them creates instances and records, on demand; a read never writes.
7. **Choices are enforced:** a minimum, a maximum and a whitelist, with a GM override.
8. **Revocation:** a grant lasts while its source does, and revocation cascades down a chain of grants; or it is permanent.
9. **`active` is true by default** on a held instance, and a prototype may declare that its instances start inactive.
10. **Effects are aggregated, not inherited:** a holder reads what its features give with RFC 0053's `contents` options.
11. **System-agnostic.** Nothing is seeded, nothing assumes a game or a level, and a feature belongs to a system by the system
    root among its ancestors (RFC 0052).
12. **Revocation happens in the request that removes a source;** granting stays on demand.
13. **A prerequisite is the same inline comparisons as a rule's conditions.**
14. **A hidden entry in a choice** (a library's hide, [ADR 0437](../adr/0437-hiding-the-entries-of-a-repository-built-on-another.md))
    is offered under the label "a hidden entry".
15. **`repeatable` and `starts_inactive` are columns of `feature`.**
16. **A revoked record keeps its feature and loses its instance,** which is deleted.
17. **A holder is a being, an item instance or a group.**

## What it is like today (tried against the API, 2026-11-10)

Findings, not proposals. A feature can be attached five ways, and each falls short.

- **A bare entry as a parent of the holder.** Effects inherit and the list is the holder's `prototypes`, but there is no
  per-holder state, two features that set one stat tie by parent order (the first wins), and the stats pollute the flat read.
- **An item instance held by the holder.** Per-holder state works (`uses`, `prepared`) and capacity works, but a spell or a
  feat lists as inventory and carries a weight.
- **A group of beings.** Members must be beings, so a feature has to become a being.
- **A relationship with a `prepared` stat.** The ends can be any entry, but a list of one character's relationships has no
  stats, and the bulk read has no end filter: one relationship type per character was needed to list them.
- **Information of a free-form type.** Text only, per entry, not inherited, no state.

For rules: "gets this at level N" is not conditional, since parents are rows; it worked as a chain of level prototypes whose
parent is swapped at each level-up. "Choose 2 of 5" worked only as a container with a capacity of 2, which has no minimum, no
whitelist and is bypassed by the override. A recursive listing of a spell category returned the category nodes with the
spells, and `parent_id` given twice kept the last one. The containment table links entry ids with no kind check; the kind
rules are in the routes.

## Hard invariants

- **Resolution does not change.** Features add rows and an aggregation; values still resolve over the prototype graph by
  distance, then group priority, then parent order (ADR 0037, 0266).
- **Rules are data, not code.** A condition is a comparison, a count is a constant or one stat, options are a list or a
  category. No expression, no script.
- **A read never writes.** Granting happens in apply or in an award; revocation happens in apply, in a removal or in the
  request that removes a source (section 5). Each is one transaction with an activity entry (ADR 0225's pattern).
- **A (rule, source) pair grants once.** Applying twice grants nothing new, and a chain of grants stops on that, with a depth
  cap behind it.
- **A choice is only made from what the rule offers**, within its count and the option's prerequisites, unless a GM
  overrides.
- **Nothing is seeded.** The platform ships no feature, no feature type and no rule.
- **Tenant isolation is by RLS** (ADR 0002): every table has `tenant_id`, same-tenant foreign keys (ADR 0117) and a line in
  the copyable-table registry ([ADR 0218](../adr/0218-the-copyable-table-registry.md)).
- **Visibility follows what exists:** a feature instance is as visible as a thing the holder holds
  ([ADR 0040](../adr/0040-item-instance-read-visibility.md)), and an entry's own audience applies
  ([ADR 0305](../adr/0305-facts-and-entry-audiences.md)).

## Design (proposed)

### 1. The kinds

`feature` is a marker table keyed by `entity_id`, with two columns: `repeatable` (a holder may hold two instances; default
false) and `starts_inactive` (its instances begin with `active` off; default false). A feature prototype is an entry with
stats, a description, parents and a type, like any prototype.

`feature_instance` is a marker table keyed by `entity_id`, with `active` (default true unless the prototype starts
inactive). An instance has one prototype, a feature, and inherits its stats; per-holder state is the instance's own stats
(`uses_spent`, `prepared`). It has no quantity: a repeatable feature held twice is two instances. It is contained by its
holder in the containment table that links entries today.

A **feature type** is not a table. It is a category entry among the feature's parents (a spell school, a feat group, a
class's feature list), exactly as the seed's taxonomy and the tested spell categories work. A feature is a leaf of that
taxonomy and carries the kind, so lists of features are leaf-only and the category nodes are not in them.

A holder is a being, an item instance or a group. A group's features are its own and do not pass to its members, and a
group's sources are the group entry's ancestors and what it holds, so a party can hold a feature and its grants. A feature
instance holds nothing: sub-features are grants of the feature.

### 2. Reading and changing what is held

All under `/tenants/{t}`:

| Route | Does |
| --- | --- |
| `GET /entities/{holder}/features` | the held instances: the feature, its types, effective stats, `active`, and `granted_by` (rule and source) when there is one |
| `POST /entities/{holder}/features` | an award: a feature, no rule; the GM's, or the holder's controller where the library allows |
| `DELETE /features/{instance}` | removal, with the cascade of section 5 |
| `PUT /features/{instance}/active` | the switch |

The catalogue of features is the bulk effective-stat read with `kind=feature`, `parent_id` and `recursive`, as for any entry;
no new route.

### 3. Grant rules

A rule hangs on a **source** entry, which may be a race, a class, an archetype, a feature, an item prototype or any entry.

- `grant_rule(id, tenant_id, entry_id, label, position, mode, min_count, max_count, count_stat_definition_id, option_category_entry_id, lasts, changeable)`.
  `mode` is `all` (every option is granted) or `choose`. `max_count` is a constant or, with `count_stat_definition_id`, a
  holder stat read at apply. `lasts` is `while_source` or `permanent`; `changeable` says whether a pick can be swapped.
- `grant_rule_condition(id, rule_id, subject, stat_definition_id, comparator, right_constant, right_stat_definition_id)`:
  a comparison with the `comparison` kind's comparators, all ANDed. The subject is the `holder` or the `source`.
- `grant_rule_option(rule_id, option_entry_id, position)`: the explicit options. With `option_category_entry_id`, the options
  are the features under that category.
- A feature may carry **prerequisites**, `feature_prerequisite(feature_id, stat_definition_id, comparator, right_constant,
  right_stat_definition_id)`: the same comparisons, on the holder, which every rule that offers the feature respects.

A holder has a source in two ways: the entry is an ancestor of the holder on its prototype walk, and the rules it carries are
the rules of the whole walk (a Champion archetype brings its parent Fighter's rules); or the holder holds an **active**
instance, whose prototype's rules, with its own ancestors', then apply. The **source reference** names which: the ancestor
entry, or the held instance, so an item held twice or a feat taken twice counts separately.

### 4. Records and apply

`grant_record(id, tenant_id, holder_id, rule_id, source_ref_id, feature_id, feature_instance_id, state, created_at, created_by)`.
`rule_id` is null for an award. `state` is `active` or `revoked`; a revoked record keeps its `feature_id` and loses its
instance, which is deleted. Unique on (holder, rule, source reference, feature) while active.

`GET /entities/{holder}/grants` computes, without writing: what is held; what is **due** (automatic grants whose conditions
hold and which have no record); the **open choices** (rule, source, minimum, maximum, picked, the options that pass their
prerequisites); and what is **orphaned** (records whose source or conditions no longer hold).

`POST /entities/{holder}/grants/apply` takes optional picks (`rule`, `source`, the chosen options), `dry_run` and, for a GM,
`override`. It creates the due automatic grants and records the picks, then repeats until nothing more is due, because a
granted feature is itself a source. It refuses a pick outside the options, below the minimum where a minimum was asked,
above the maximum, with an unmet prerequisite, or of a feature the holder holds and that is not `repeatable`, and it
reports what it created, what is still open and what it revoked.

Level-up is a client changing the holder's stats and then calling apply; creation is calling apply on a holder with sources
and no features.

### 5. Revocation

A record whose rule `lasts` `while_source` is revoked when its source is gone, its source is inactive or its conditions stop
holding. This happens **in the request that causes it**, not at the next apply: a move of the source out of the holder, a
change of the holder's parents, a flip of `active`, the deletion of the source, or a write of a stat that a condition of one
of the holder's active records reads. The check runs only for a holder that has active `while_source` records, and a stat
write looks up whether any such condition reads that stat before it does more. Granting is never done there; a feature
that becomes due waits for apply. The feature instance is deleted, and so is every record whose source reference was that instance, and their
instances in turn: an item that gives a feature that gives a spell choice takes all three with it when it is dropped. A
`permanent` grant is checked for its conditions only when it is made. A pick of a `changeable` rule can be swapped by the
holder; any other pick is removed by a GM only.

### 6. Effects

A feature's effects are stats on the feature prototype and the instance. The holder reads them with RFC 0053: a bonus total is
`contents(sum, only_kind=feature_instance, only_active)` of the bonus stat; a count of features of a type is
`contents(count, only_kind=feature_instance, where=<a flag>)`; a flag feature is a `product` factor. A feature does not
replace the holder's formulas, and none is a parent of the holder.

### 7. Repositories

`feature`, `feature_instance`, `grant_rule`, `grant_rule_condition`, `grant_rule_option`, `feature_prerequisite` and
`grant_record` are content: copied as rows, with ids re-pointed (the source, options, category and stats of a rule are
re-targeted as a formula's inputs are). A feature instance and a grant
record are copied once and never changed by an update, as an item instance is; the rules and the prototypes update as
entries do. Deleting a rule or a feature is a breaking change, with `grant_rule_removed` added beside `entity_removed`. Two
single kinds join the publishable matrix of [ADR 0217](../adr/0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md).
A class or a race therefore ships with its grants.

### 8. Templates, hover cards and the feed

RFC 0052's templates gain a `features` slot kind: the held features, grouped by type, with columns from a list of stats or a
group. A feature's hover card reads its description and a few stats. A grant, an award and a revocation write an activity
entry and reach the player on the change feed ([ADR 0099](../adr/0099-player-facing-change-feed.md)).

### Who may do what

Authoring features and rules is the vocabulary's tier (any member). Applying and picking is the holder's controller, and any
GM. A GM may override a minimum, a maximum or a prerequisite. A player's lists and apply responses omit what they may not read.

## Delivery

Each slice is its own ADR.

1. **F1.** The two kinds, the marker tables, `/features` (list, award, remove, switch), the exclusion from inventory and the
   board, the publishable matrix, copy. Needs RFC 0053's K4 to be read by a holder's formulas.
2. **F2.** Grant rules: tables, authoring routes, prerequisites, copy and update, the breaking reason.
3. **F3.** Records, the grants read, apply with picks, and revocation.
4. **F4.** The `features` template slot, once RFC 0052's templates exist.

Beings and Bench work, a level-up flow and a rule editor, follows as the apps' own work.

## Not in scope

- Spell slots, preparation limits and rests: stats and formulas, as the guide shows.
- Spending a resource or points to take a feature, and swapping one feature for another beyond a changeable pick.
- Grants derived at read time rather than materialised, and an apply that runs on a stat write.
- A feature that changes how the holder's formulas compute (RFC 0053's kinds cover the effects).
- A feature that holds features, and a group's features passing to its members.
- An undo of an apply beyond removal and revocation.
- Physical upgrades, which are items in a container with `active`, and need nothing here.

## Open questions

None.

## Alternatives considered

- **A full set of feature tables** (feature, feature type, a character-feature link with its own state, grants, choices). It
  names the thing exactly, and duplicates containment, stat state, capacity, visibility and the whole repository machinery,
  each of which then has to be kept in step.
- **Reuse `item_instance`.** Less code, but a spell lists as inventory and carries weight, price and binding; a kind of its
  own was chosen.
- **Features as parents.** Effects inherit, but no per-holder state, a tie when two set one stat, and no list.
- **A relationship per feature.** State on the link, but an entry per holder and feature, and no list with stats.
- **Conditional parent edges** ("this parent applies from level 3"). Changes resolution (ADR 0037) and costs a read.
- **Grants derived at read time.** A choice has to be stored anyway, and every read would evaluate every source.
- **Grants as a script or a rule language.** The comparisons, one count and a list say every case met in the tests.

## Consequences

- A class, a race, a playbook or a magic item can ship its grants in a repository, and a library gets a character that is
  complete after one apply.
- The level-chain prototypes of the guide go away: a class is one entry with conditional rules.
- Two marker tables (the kinds) and five more tables are added, each a place a rule can be wrong, and each needing RLS, a
  registry line and copy handling.
- Choices are enforced, so a library that needs a looser rule uses the GM override or leaves the rule out.
- Revocation in the request that removes a source adds a small check to moves, parent changes, `active` flips and stat
  writes; it runs only for holders with active `while_source` records, and the slice that adds it carries the
  statement-count test of [ADR 0285](../adr/0285-api-reads-that-cost-what-they-read.md) for a stat write.
- A holder's features and their effects need RFC 0053's `contents` options, so F1 is read by a formula only after that
  slice.
