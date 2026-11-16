# 0454 - Features: two kinds, and what a holder has

Status: accepted, built (2026-11-12). Slice F1 of [RFC 0054](../rfcs/0054-features-grants-and-choices.md). Builds on
[ADR 0447](0447-contents-options-and-the-active-switch.md) (`active`, and `only_kind`, which gains the one kind it was waiting
for), [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md) (kinds are marker tables and the publishable
matrix), [ADR 0040](0040-item-instance-read-visibility.md) (who reads what a holder holds), [ADR 0218](0218-the-copyable-table-registry.md)
(the registry) and [ADR 0437](0437-hiding-the-entries-of-a-repository-built-on-another.md) (hidden entries). Resolution does not
change ([ADR 0037](0037-effective-stat-resolution.md), [ADR 0266](0266-stat-tie-break-by-parent-order.md)).

## Context

A character feature, a spell, a feat, a boon or a playbook move was attached five ways, each falling short (RFC 0054 "What it is
like today"): as a parent it has no per-holder state, as an item instance it lists as inventory and carries a weight, as a being
it has to be a member of something, as a relationship it has no list with stats, and as information it has no stats. This slice
adds the thing and how a holder has it; the rules that say when a holder is entitled to one are F2 and F3.

## Decision

- **Two kinds, each its own and combining with none.** `feature` is the prototype: a marker with `repeatable` (a holder may have
  it twice, false) and `starts_inactive` (its instances begin with `active` off, false). `feature_instance` is what a holder has: a
  marker with `active` (true), one prototype (the feature) whose stats it inherits, its own stats for what the holder keeps
  (`uses_spent`, `prepared`), contained by its holder in the containment table. It has no quantity: a feature held twice is two
  instances. Both are in `EntityKind`, in `kinds` of every response that lists an entry's kinds, and in the publishable matrix as
  `("feature",)` and `("feature_instance",)`.
- **A feature type is not a table.** It is a category entry among the feature's parents (a spell school, a feat group, a class's
  feature list). The catalogue of features is the bulk effective-stat read with `kind=feature`, `parent_id` and `recursive`; no new
  route.
- **Making a feature.** `POST /entities` takes `"feature"` in `kinds` with `repeatable` and `starts_inactive`; `PUT
  /entities/{id}/kinds/feature` gives the kind to a bare entry and, on one that is a feature, sets the two columns (a column left
  out stays; a different one is "changed", not "created"). A feature does not combine: another kind with it, or `feature` on an entry
  that has another, is a 422. `feature_instance` is not made by the kind routes (422): the award makes it. `GET
  /features/prototypes/{id}` reads the two columns (404 for an entry that is no feature, or one the library hides). An Author of a
  library may make features, as items.
- **The routes** (all under `/tenants/{t}`):
  - `GET /entities/{holder}/features`: the instances the holder has, by name then id, each with the instance (`id`, `name`), the
    feature, the feature's types (its direct parents the caller may see), `active` and the effective stats (the instance's own over
    what it inherits, formulas evaluated as on an entry's read). `422` when the entry is no holder.
  - `POST /entities/{holder}/features` `{feature_id, active?}`: an award. `201` with the instance and its `Location`.
  - `GET /features/{instance}`: one instance.
  - `PUT /features/{instance}/active` `{active}`: the switch.
  - `DELETE /features/{instance}`: removal. `204`.
- **A holder is a being, an item instance or a group.** A group has no table (ADR 0045), so an entry is a group while it has
  members. A group's features are its own and do not pass to its members. A feature instance holds nothing.
- **An award** makes an entry named as the feature (no slug), the marker, the one prototype and the containment, switched on unless
  the feature starts its instances inactive or the body says. It refuses a feature the holder has and that is not `repeatable` (409),
  an entry that is no feature in this library, a hidden one included (422), and a holder that holds nothing (422). It writes an
  activity entry (`feature.awarded`) and a change-feed row for whoever now holds it (ADR 0099). No capacity check runs: a feature has
  no weight a container could be full of.
- **Who may do what.** Awarding and removing are the holder's manager's: a GM of a campaign the holder plays in (a group's are its
  members'), an administrator or the GMs ADR 0151 names for one in none, for an item instance whoever manages its owner (any GM in
  the tenant when nobody owns it), and an Author in a repository (ADR 0219) (403). The switch is the holder's to flip, by the rule
  that lets them edit what they hold (ADR 0124), or a manager's; like an item's it is no activity-log event. A reader must reach the
  holder (ADR 0040's sets, as `held-by`), else `404`; a manager reads what they manage, so that what an administrator awarded can be
  read back, which ADR 0040 gives up for an item instance on purpose and this does not. An instance a library hides is left out.
- **What goes with what.** Removing a feature takes the instance and what it kept; the change feed tells whoever held it. A holder's
  features go with the holder: the entry route, a being's permanent deletion (with those of the items that go with it), an item
  instance's deletion (before what is inside it moves out), and a group that stops being one and holds nothing else. A feature a
  holder has is not deleted (409) and does not lose its kind (409); an instance is not deleted through the entry route (409, its own
  route).
- **Inventory reads leave it out by kind.** The item-instance lists, `held-by` and the sheet's weapons select item instances, so a
  feature instance is not in them; this slice adds the tests that say so. `GET /entities` lists it as any entry, with its kind; that
  list is no gate of ownership for an inventory item either.
- **A formula reads features with the options it has.** `only_kind` of a contents formula takes `feature_instance` beside
  `item_instance` (the check constraint, the body and the held thing's kind), and `only_active` reads the instance's switch. A `sum`
  with no `only_kind` still takes anything inside, and so sees a feature instance only if the library gave one the stat it reads.
- **A repository carries them.** The release document moves to **format 43**: `repeatable` by entry, and a feature's
  `starts_inactive` in the map items already use (version 42 is read with none repeatable). A copy makes the markers as the document
  says; a copied instance starts as its feature says, as an item instance does (ADR 0447); the containment copies as it does for
  everything. An update proposes a feature's `repeatable`, `starts_inactive` and a gained or lost kind `feature` (the loss skipped,
  with the reason, while a holder has it here); an instance is made in the library, as an item instance is, and is not changed by an
  update. The kinds join the matrix.

## Design

`feature(entity_id, tenant_id, repeatable, starts_inactive)` and `feature_instance(entity_id, tenant_id, active)`, each with a unique
key on `(entity_id, tenant_id)` for the same-tenant keys of F2 (ADR 0117), a same-tenant key into `entity` (cascade), `tenant_id`
indexed, and the two policies of a content table (ADR 0118) with `FORCE ROW LEVEL SECURITY`. Both are registry lines
(`carried_by="entity"`). `computed_stat_contents_only_kind` is replaced to allow the second value. The reading is
`features.py` (who holds, who manages, the instances with their stats) and `routers/features.py`; the instance's stats are loaded
for all of a holder's instances in one query, as the sheet loads what a being holds.

## Validation and delivery

A test for each: a feature made, its columns read and changed, the combinations refused, the award (instance, types, stats,
Location), what may hold, `repeatable`, how an instance starts, the switch read by a formula with `only_active` and `only_kind`, the
plain sum unchanged, removal, the delete guards, what goes with a holder, what the inventory reads leave out, a player's reads and
switch and what they may not do, the release document round trip and the version 42 reader, and the matrix rows. The OpenAPI change
is the new routes, the two kind values (accepted in `openapi-breaking-accepted.txt`, each a response enum that grew), `only_kind`
widened, and the columns on the kind routes; the CLI models and `packages/api-client` are regenerated.

## Not in scope

Grant rules, records and apply (F2, F3); the `features` template slot (F4); the update engine does not change an instance; an award
by the holder's controller (RFC 0054 says "where the library allows", which is a setting nobody has asked for); `If-Match` on the
instance routes.

## Consequences

- A character feature, a spell or a boon is an entry with stats that a holder has, with its own state, and an aggregate reads.
- A library that never makes a feature changes nothing; no existing request changes, and no row is seeded.
- Two more kinds on the matrix, and a deletion of a holder that now also looks for what it holds.
