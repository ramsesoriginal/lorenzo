# 0019 - Item, item instances, and the v_item/v_item_instance views

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) scopes the first slice as `entity`, `item` + `v_item`, `stat_definition`, `stat_group`, `entity_stat`, `entity_prototype`, `information`, `knowledge`, `containment` - every piece except `item`/`v_item` itself and `knowledge` (RFC 0001's own open question, not this sub-slice's to resolve) is already built (ADRs 0012-0017). This sub-slice is the first *concrete type*: "Concrete types get a maintained view (`v_item` alongside `item`) exposing the commonly-needed inherited/computed properties as if they were plain columns."

Two concrete tables, both class-table-inheritance extensions of `entity` (same `entity_id` PK+FK shape as `payload`'s four extensions - [ADR 0017](0017-information-and-payloads.md)):

- **`item`** - a bare marker: this entity is a base item type ("Shovel," "Tool"), no columns beyond `entity_id`/`tenant_id`. Everything else about it (stats, information) already exists through the generic mechanisms.
- **`item_instance`** - a specific, ownable item ("My Shovel"). Its entity must have at least one direct prototype ([ADR 0015](0015-entity-prototype.md)) that is itself item-typed - RFC 0001's own example almost exactly ("'My Shovel' is an ordinary entity that inherits from... 'Shovel'"). Also carries `owner_entity_id`, referencing a character - which doesn't exist yet (RFC 0002's `character`/`player`, not built on this branch). Referencing `entity.id` generically for now, the same way RFC 0002 itself references ownership targets generically rather than assuming a concrete type; revisit once `character` actually exists (a dedicated FK, or keeping the generic reference if "anything can own an item" turns out to be wanted - not decided).

## Decision

### item

`item(entity_id, tenant_id)`. `entity_id` PK+FK to `entity.id`, `ON DELETE CASCADE`. No other columns.

### item_instance

`item_instance(entity_id, owner_entity_id, tenant_id)`. `entity_id` PK+FK to `entity.id`, `ON DELETE CASCADE` (same as every other concrete extension). `owner_entity_id` FK to `entity.id`, **nullable, `ON DELETE SET NULL`** - a deliberate exception to ADR 0018's "cascade everything" rule: an owning character being deleted shouldn't delete the item along with them, just leave it ownerless. Not enforced anywhere: that the referenced entity is actually a `being`/character (can't be - `being` doesn't exist yet) or that the instance's own entity actually has an item-typed direct prototype - the same kind of accepted, unenforced invariant as `entity_stat_group`'s tenant agreement ([ADR 0014](0014-stats.md)). A trigger could check the latter (direct `entity_prototype` rows whose `prototype_id` has a matching `item` row), but nothing asked for that enforcement yet.

### v_item and v_item_instance

**Revised after initial acceptance**: the first version of this ADR had one view covering both tables, reasoning that RFC 0001 only ever names one view for "the items concept" and the requested fields applied equally to either. Pushed back on directly: a single merged view gives no way to tell "find all base items" (a catalog/authoring query) from "find all item instances" (e.g. what a character owns) without joining `item`/`item_instance` back in anyway - which defeats the point of having a view at all. Two views instead, one per concrete table, matching RFC 0001's actual "concrete types get a maintained view" framing applied to each concrete type in turn.

Both share the same plain-column shape, each a `LEFT JOIN` (an item/instance missing a given stat or its description just gets `NULL`, not excluded):

- `entity_id`, `tenant_id`
- `description_id`, `title` - from the entity's `information` row where `type = 'description'`
- `weight`, `height`, `price`, `rarity`, `hp`, `armor` - `entity_stat.value_int` for the stat definitions of those names
- `is_magical`, `is_cursed` - `entity_stat.value_bool` similarly
- `container_entity_id` - `containment.parent_entity_id` where this entity is the child

`v_item_instance` additionally exposes `owner_entity_id` directly (from `item_instance` itself) - the one column that's genuinely specific to instances, and exactly what "find what this character owns" needs.

Each named-stat join resolves through `entity_stat.stat_definition_id` to a specific `stat_definition` row already tied to one tenant - filtering that joined row by `name` doesn't need an extra tenant check, since there's no independent lookup of "some `stat_definition` named X" involved, just a property check on the row a real FK already points to.

**`WITH (security_invoker = true)`** on both: Postgres views run with the view owner's privileges by default, not the querying role's - a view created by the same superuser role every migration already runs as ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)/[0012](0012-entity-table.md)) would otherwise silently ignore RLS entirely once that superuser gap is eventually fixed, in a way that's easy to forget specifically because views aren't the first place anyone looks for an RLS regression. Setting this now costs nothing today (the superuser gap means it's moot either way, currently) and means each view is correct by construction once that gap closes, rather than needing a second, separate fix remembered later. Confirmed empirically that `security_invoker` has a second, easy-to-miss consequence: the querying role needs its own `SELECT` grant on every underlying table the view touches (`entity`, `item`/`item_instance`, `information`, `containment`, `entity_stat`, `stat_definition`), not just the view itself - granting only the view failed with "permission denied for table information" until every table its joins reference was granted too.

**Excluded from autogenerate**: both views are hand-written (`op.execute("CREATE VIEW ...")`), not `op.create_table()` - Alembic has no native "view" construct, and a plain declarative `Table` for either in application metadata would make autogenerate think a real table is missing. `migrations/env.py` gets an `include_object` filter skipping both by name.

### VItem/VItemInstance (the mapped classes) also load richer, list-shaped data

Beyond each view's plain scalar columns, `VItem`/`VItemInstance` share an `ItemViewMixin` providing a `viewonly=True` relationship straight to the real `Entity` (same `entity_id`) plus Python properties navigating `Entity`'s own already-existing relationships to build the requested `(x, y)` tuple lists - not new `relationship()`s with their own multi-hop join conditions. The mixin holds everything identical between the two (the properties below, and the type hint `entity` needs); each concrete class still declares its own `entity_id`/columns and its own `entity` relationship, since the join condition differs per view (`VItem.entity_id == Entity.id` through `item`'s population vs. the same through `item_instance`'s).

- `descriptions: list[tuple[content, locale]]` and `pictures: list[tuple[data, file_type]]` - every `PayloadDescription`/`PayloadPicture` reachable from the entity's `type = 'description'` `Information` row(s), through `Payload`.
- `physical_stats`/`economic_stats`/`destroyable_stats`/`damaging_stats: list[tuple[name, value_int]]` and `tags: list[tuple[name, value_bool]]` - every `EntityStat` whose `StatDefinition` belongs to a `StatGroup` of that name.

Reusing `Entity.information`/`Information.payloads`/`Payload.description`/`.picture` and `Entity.stats`/`EntityStat.stat_definition`/`StatDefinition.stat_group` (all already built, tested relationships) is simpler and less risky than hand-rolling a 3-table-deep `secondary=` join condition for each - the tradeoff is that these seven properties need their backing relationships eager-loaded by the caller (e.g. `selectinload` chains) to avoid triggering a lazy load in this project's async setup, which - as found repeatedly this session - fails outright rather than transparently working. Not hidden behind automatic eager-loading by default: how much of an entity's stat/information graph loading a `VItem`/`VItemInstance` should pull in isn't decided, and guessing wrong either direction (always-eager on a rarely-used property, or silently N+1 on a hot path) is worse than being explicit about it in the docstring for now.

## Consequences

- `stat_group`/`stat_definition` names these views depend on ("weight", "physical", "tags", ...) are ordinary tenant-authored rows, not schema - a tenant that never created a stat named "weight" just gets `NULL` there, and a tenant using "physical" for something unrelated to RFC 0001's intent gets whatever rows actually match. These views encode an assumption about vocabulary, not a constraint that enforces it.
- Same RLS caveat as every table so far, and now also both views specifically: `security_invoker = true` is real and tested groundwork, but moot until the superuser gap it's aimed at is actually fixed.
- Same known, unsolved limitation as every extension/join table so far: nothing enforces `item_instance`'s "must have an item-typed direct prototype" invariant, or that `owner_entity_id`'s target is actually being-shaped (impossible to check today - `being` doesn't exist).
- Querying `VItem`/`VItemInstance` and getting fully-populated `descriptions`/`pictures`/`*_stats`/`tags` requires the caller to eager-load the right chain first; accessing them without doing so either returns empty results (if `Entity` itself wasn't loaded) or raises rather than lazy-loading transparently, matching every other async lazy-load pitfall found this session.
- `ItemViewMixin` is deliberately not itself a mapped class (no `Base`, no table) - a plain Python mixin holding only properties and a type hint, combined with each concrete view class's own real columns/relationship. Confirmed this doesn't confuse SQLAlchemy's declarative scanning (the mixin's bare `entity: Entity` annotation, not wrapped in `Mapped[...]`, is correctly ignored rather than treated as something to map).
