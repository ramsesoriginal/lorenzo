# 0025 - Character (being), roster reuse, and ownership

Status: accepted — partially superseded by [ADR 0031](0031-character-table-and-read-api.md), which moves `owner_player_id` off `being` onto a new `character` table layered under it, and retargets `character_player.character_entity_id` from `being.entity_id` to `character.entity_id` (a being now has to be "promoted" to a character row before it can be rostered); the roster-reuse/ownership decisions themselves stand

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) reserved `being` for anything sentient/agentive, deferred until something needed it. [RFC 0002](../rfcs/0002-campaign-player-character-model.md) is that something: a character is a `being` owned by a **player**, not directly by a user, and item ownership needs to be decoupled from physical location (`containment`) - a character can own something they aren't carrying. This sub-slice builds `being`, the roster-reuse join, and the generic `ownership` table, and reconciles it against `item_instance.owner_entity_id` - a placeholder ADR 0019 built specifically "until character exists."

## Decision

### `being(entity_id PK/FK, tenant_id, owner_player_id)`

Mirrors `item`'s exact shape (a bare class-table-inheritance marker) plus one column: `owner_player_id`, nullable, `ON DELETE SET NULL` - matching `item_instance.owner_entity_id`'s own precedent exactly (the one deliberate exception to ADR 0018's cascade-everything default): losing the owning player shouldn't destroy the character, just leave it player-less (it becomes an NPC - RFC 0001's own framing, "whether a being is player-controlled is a derived fact - does it have an owning player").

Whether a `being` is a PC is still not a stored type (RFC 0001) - `owner_player_id IS NOT NULL` is that derived fact.

### `character_player(character_entity_id, player_id, tenant_id)` - genuinely n:m, not a single "primary owner"

RFC 0002 is explicit that a single player can control more than one character at once (a Vampire coterie), and a single character can be linked to several player rows across campaigns (the roster-reuse mechanism - a user's character appearing in more than one campaign in the same tenant keeps the same inventory by default). Composite primary key `(character_entity_id, player_id)`, matching every other pure n:m join in this schema (`entity_prototype`, `entity_stat_group`) - no surrogate id, since there's nothing this join needs to be addressed by beyond the pair itself.

This is deliberately kept separate from `being.owner_player_id`: the latter is "who created/primarily owns this character" (singular, nullable), the former is "which player rows can currently pilot it" (multi-valued). Collapsing them into one mechanism was considered and rejected - there's no way to derive a single canonical "primary" owner from a genuinely multi-valued roster link without an arbitrary tie-break rule the RFC never specifies.

### `ownership(owned_entity_id PK/FK, owner_character_id, tenant_id)`

`owned_entity_id` alone is the primary key, not a composite - matching `containment.child_entity_id`'s own precedent exactly, and for the identical reason: an entity can only have one owner at a time, globally, so the PK only needs to name the owned side. `owner_character_id` is a plain `FK → entity.id`, **not** `FK → being.entity_id` - RFC 0002's own words: ownership "isn't restricted to characters as an owner at the schema level (a faction or place could plausibly own something later)... `owner_character_id` is all that's needed for the first slice." This is the exact same forward-compatible-placeholder shape `item_instance.owner_entity_id` already used, just graduated to its own generic table. Both FKs are `ON DELETE CASCADE` (unlike `being.owner_player_id`): the ownership *fact* is meaningless once either the owned entity or the owning character is gone, and since ownership is its own row (not a nullable column), cascading the row away is equivalent to "set null" would have been - there's no state left to null out.

### Reconciling `item_instance.owner_entity_id`

Now that `being` exists to actually own things, the placeholder is retired - but surgically, not by touching the REST layer built in [ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md):

1. Migration backfills `ownership` from every non-null `item_instance.owner_entity_id`, then drops the column from `item_instance`.
2. `v_item_instance`'s view definition changes from selecting `item_instance.owner_entity_id` directly to `LEFT JOIN ownership ON ownership.owned_entity_id = e.id`, exposing `ownership.owner_character_id AS owner_entity_id` - **same column name, same position, same type** in the view's own output.

Because the view's external shape is unchanged, `VItemInstance` (the mapped class), `ItemViewMixin`, `ItemInstanceOut`/`OwnedByResponse` (schemas), and `routers/item_instances.py`'s `/owned-by/{owner_entity_id}` route **need no code changes at all** - they only ever interact with `VItemInstance.owner_entity_id`, never the base `item_instance` table directly. The column name `owner_entity_id` stays accurate even though ownership is now backed by a `being` (a being's `entity_id` *is* an `entity.id`) - and keeping it stable is deliberately better API design than renaming a already-shipped REST field for a purely internal storage refactor.

## Consequences

- `ItemInstance` (the model) loses `owner_entity_id` and its `owner` relationship - ownership for item instances now flows entirely through `Ownership`, reached via `Entity`, not a column on `ItemInstance` itself.
- Existing item-instance tests (`test_item_instance.py`, `test_api_item_instances.py`) needed updating wherever they constructed `ItemInstance(..., owner_entity_id=...)` directly - those now insert an `Ownership` row instead; the REST-facing assertions are unchanged, since the view's output shape didn't change.
- `character_player`/`ownership` still have no REST endpoints - matching the vertical slice's own stated scope (data model first).
