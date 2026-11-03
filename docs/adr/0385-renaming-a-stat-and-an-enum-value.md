# 0385 - Renaming a stat and an enum value

Status: accepted, decided with the maintainer on 2026-11-03. Slice K6 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §6, tracked in #973. Builds on [ADR 0278](0278-stat-definition-display-fields-order-and-patch.md) (the `PATCH`es of a stat group and a stat definition), [ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md) (enum values), [ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md) (what in use means) and [ADR 0121](0121-repository-updates-and-re-sync.md) (what a library sees). Amends [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md), [ADR 0014](0014-stats.md), [ADR 0167](0167-the-api-deletes-an-unused-stat-definition-or-stat-group.md), [ADR 0253](0253-bench-formulas-and-the-stat-vocabulary.md) and [ADR 0278](0278-stat-definition-display-fields-order-and-patch.md) by addenda.

## Context

A stat group can be renamed since ADR 0278. A stat definition cannot: its `PATCH` edits how it is drawn, and its name was left out on purpose, as ADR 0014 and ADR 0167 say neither can be renamed. An enum value can be added and removed and nothing else, so a typo in `legendary` is a delete and an add, which is refused while any entry holds it. Bench's stat form says "A stat cannot be renamed afterwards", and the seed's notes say the same. An author fixing a name has no way to do it short of making a new stat and moving every value by hand.

Writing the change turned up four things the RFC did not list:

- **An enum value has no id on the wire.** `StatDefinitionOut.enum_values` is a list of strings and the `DELETE` of a value takes the value's id, so no client can call it, and the `PATCH …/enum-values/{value_id}` of the RFC could not be called either.
- **The text of an enum value is stored in two kinds of place:** `entity_stat.value_text`, and `true_value` and `false_value` of a comparison formula whose target is the enum. There is no foreign key to the value's row. The `DELETE` of a value checks the first and not the second, so a value a formula returns can be deleted today and the formula then returns a value the stat does not allow.
- **The API reads a few stats by name** (`weight`, `height`, `price`, `rarity`, `hp` and `armor` in the item views; `size`, `carry_capacity`, `containment_capacity` and `max_item_size` in capacity checks; `binding`, whose value `none` the binding code writes; `is_container`). A rename of one of those would change what the API does without a word. Nothing could do that before.
- **Snapshots hold enum text.** A copy link's snapshot, a released row's facts and a release document all carry enum values as text, and the copy links' snapshots carry stat values and formula results.

## Decision

### Renaming a definition

`PATCH /tenants/{id}/stat-definitions/{stat_definition_id}` takes **`name`** beside the fields it has (a non-empty string; it cannot be null, as for a group). A name another definition of the library has is a `409` (`stat-definition-name-taken`, as `stat-group` does for a group), checked before the write. Renaming a definition whose current name is one the API reads by name (the list above) is refused: `409` `stat-name-reserved`, saying which. A rename **to** such a name is as allowed as making a definition of that name is today. Type and group stay not editable: a value stored as one type has no honest conversion, and moving a definition between groups changes what its values mean to a library.

### Renaming and reordering an enum value

`PATCH /tenants/{id}/stat-definitions/{stat_definition_id}/enum-values/{enum_value_id}` takes **`value`** and **`sort_order`**, each optional, neither null. It answers the definition, as the add and remove routes do.

- **A value that is taken** (another value of that stat has it) is `409` `stat-enum-value-already-exists`, as an add is. Renaming a value to itself changes nothing.
- **A rename rewrites what stores the old text, in the same transaction:** every `entity_stat.value_text` of this definition, and the `true_value` and `false_value` of every comparison formula whose target is this definition, each where it equals the old text. That is every column that can hold an enum value; a test reads the schema and fails when another one appears. Nothing is rewritten in a snapshot, a link or a release: those are what a library copied or what was released, and a rename after them is a change the next update or release shows.
- **Not a rename for a name the API reads:** the value `none` of `binding` is refused (`409` `stat-name-reserved`).
- **A reorder** is the `sort_order` of one value. Two values may share one, as ADR 0103 says, and ties break by value.

### Telling a client which value is which

`StatDefinitionOut` gains **`enum_options`**, a list of `{id, value, sort_order}` in display order, beside `enum_values`, which stays as it is. Additive: a client that reads `enum_values` does not change, and a client that edits a value reads the id here.

### What in use means for an enum value

A value is in use while an entry directly holds it **or a comparison formula for this stat returns it** (`true_value` or `false_value`). The `DELETE` of a value and the removal of a value by an update (ADR 0121) both use one definition, in one module, and the message says which. This closes the hole above: a value is no longer deleted from under a formula. A `409` that the deletion would not have given before is the only visible change.

### Who and how it is logged

All three are the vocabulary tier the route already has (`_vocabulary_gate`: Owner, Organizer and Author, [RFC 0040](../rfcs/0040-authors-and-invites.md): rename once RFC 0041 allows it). The `DELETE` of a value stays an admin's. None is written to the activity log, as ADR 0278 says for the other `PATCH`es: they change how things are named and drawn, not what exists or who may see it. An enum rename that rewrites stored values is not logged either; the rows it changes are the ones the same person could change one at a time.

### What a library sees

- **A definition's name** already reaches libraries: the update engine compares `name` and applies a changed one, and skips one whose new name is taken there ([ADR 0121](0121-repository-updates-and-re-sync.md)). The release digest does not call it breaking. Nothing changes.
- **An enum value's rename** still reaches them as an added value and a removed one, since an enum value's identity in a snapshot is its text. The removal is refused where the old value is still in use in the library (now also by a formula), so a library keeps the old value for what holds it. The release digest files it as `enum_value_removed`. Giving enum values an identity in the snapshot would fix it and changes the snapshot format; **it is not done here**, and RFC 0041's open question stays open.
- **A reorder** does not reach libraries: `sort_order` is not in the snapshot, as before.

## Not in scope

- Retyping a definition, moving it between groups, and deleting one in use.
- Enum values with an identity in the snapshot and the digest.
- A stat write bumping the version of an entry ([RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) W1). A rename rewrites stored values without moving the `ETag` of the entries that hold them; a client that has them in memory reads them again.
- The screens of Studio. Bench's vocabulary pane and the command line's notes change in a following PR.

## Consequences

- An author can fix a stat's name or an enum value's spelling in place, and every value and formula that held the old text follows.
- The seed (`lorenzo seed`) finds a definition by name, so after a rename it makes the seed's own name again beside the renamed one, which is what it does for any definition an author deleted. The seed's notes say so.
- `test_api_stat_display.py` asserted that `name` in a definition `PATCH` is ignored; it asserts the rename now.
- The OpenAPI document gains a route, an optional field in a body, a field in a response and new `409`s: additions, so the check for breaking changes finds none. The generated clients change.
- ADR 0143's "a stat can't be retyped or moved" stands and "renamed" no longer applies; ADR 0014, ADR 0167, ADR 0253 and ADR 0278 each get an addendum.
