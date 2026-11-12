# 0457 - The `features` slot of a template

Status: accepted, built (2026-11-12). Slice F4 of [RFC 0054](../rfcs/0054-features-grants-and-choices.md), the last. Builds on
[ADR 0451](0451-templates-a-sheet-as-data.md) (templates and their slots), [ADR 0454](0454-features-two-kinds-and-what-a-holder-has.md)
(what a holder has and who may read it) and [ADR 0456](0456-the-grants-read-apply-picks-and-revocation.md) (what gave it).

## Context

A template says what a sheet shows of an entry: its stats, its notes, what it holds and its tags. What it has as features (its
spells, its feats, its class features) is held as feature instances, which the `held` slot does not show (it reads item instances) and
which a sheet would want grouped by what kind of feature each is.

## Decision

- **A slot of the kind `features`** shows the features the entry holds. It is written as a `held` slot is: a stat group (with `exclude`
  for the stats of it to leave out) or an ordered list of stats, one of the two, each a column; the list's stats may carry a label. It has
  no `held_order` and no `information_type` (422), and a template of any filter may have any number of them.
- **The view of the slot**, in `GET /entities/{id}/templates/{template_id}`, has `columns` (as a held slot's) and `feature_groups`: the
  features grouped by type, a type being the first category entry among the feature's parents the caller may see. Each group has its
  `type` (an entry, none for the features of no type, which come last) and its `features` by name, each with the instance's `id`, its
  `name`, the `feature` it is of, its `active` switch and a cell for each column: the instance's effective value of the stat (its own
  over what it inherits, formulas evaluated), null when it has none. Groups come by type name.
- **What the caller reads** is what `GET /entities/{holder}/features` gives (ADR 0454): an entry that holds nothing, or one the caller
  neither reaches nor manages, shows `feature_groups: []`, and a feature the library hides is left out.
- **A repository carries the slot** as any other: a slot has a kind, a group or a list and its exclusions, and nothing in a copy or the
  document changes (the kind is text).
- **Link previews.** A feature and an instance preview as an entry does, with its description and no stats named: the stats a library
  gives its features are its own names, which the card does not know.

## Design

The check of `template_slot.kind` allows `features`; no table is added. The view is built with the reading of ADR 0454
(`held_feature_outs`), so a column is a stat of the instance as the features list gives it, and the one query of a holder's instances is
shared. The slot is one more branch of the view beside `held`.

## Validation and delivery

A test for each: the slot refused without columns, with an order, with a note type or with `exclude` and no group; the features of an
entry shown by type and by name with a cell for each column, the type-less last, labels, a feature a column has no value for, the
switch; an entry that holds nothing; a player seeing their own features and not another's. The OpenAPI change is the new slot kind
(accepted in `openapi-breaking-accepted.txt`: a response enum that grew) and the view's `feature_groups`; the CLI models and
`packages/api-client` are regenerated.

## Not in scope

A sheet drawn from a features slot (the sheet read's three settings stand for the first stats, held and information slots only); a
feature in a second type group; any app or command-line display.

## Consequences

- RFC 0054 is built (ADR 0454 to 0457): features, grant rules, grants and revocation, and the slot that shows them.
- A library's sheet template can list a character's features by type with the stats it cares about.
