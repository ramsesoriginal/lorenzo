# RFC: Core domain data model (entity/component architecture)

Status: proposed — two open questions below need resolving before this can become an ADR

## Context

The domain (see [docs/domain](../domain)) needs: extensible attributes without a migration per new stat, shared reusable templates with per-instance overrides, several independent relationship types over the same objects (containment being the first), and — the hard part — different observers knowing different things about the same entity. A conventional one-table-per-concept schema (`item` with a fixed column list, etc.) can't grow into that without constant redesign. [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)'s RLS approach and [ADR 0010](../adr/0010-user-tenant-membership-model.md)'s tenant model exist, but nothing yet defines what the tenant-scoped tables actually *are*.

## Decision

### Core entity

`entity` is the universal table: anything that can exist, be referenced, contained, described, or related to something else is a row here — an item, an NPC, a place, a prototype like "Shovel," all the same underlying kind of thing. Concrete semantic tables (`item`, `npc`, `place`, ...) FK to `entity` and add only what actually makes that kind of thing distinct (class-table-inheritance pattern) — they don't duplicate anything the flexible core already provides.

### Prototypes and inheritance

A prototype isn't a separate kind of row — it's just an `entity` that happens to be referenced as a parent by another entity. "Shovel" is an ordinary entity that inherits from "Physical Object," "Tool," "Weapon," and "Crafting Supply"; "My Shovel" is an ordinary entity that inherits from both "Shovel" and "Cursed Item," overrides some inherited values, and adds instance-specific information. One join table (`entity_prototype(entity_id, prototype_id)`) covers both cases — an entity can have any number of rows here, giving multiple inheritance for free.

**Conflict resolution**, when two ancestors define the same stat differently: more specific wins — a value defined closer to the entity (fewer inheritance hops away) beats one defined further out, and an instance-level override always beats anything inherited. When two ancestors are equally specific (e.g. two prototypes inherited directly), the tie breaks on `stat_group.priority` — the value acquired through the higher-priority stat group wins. The exact resolution query (recursive walk over `entity_prototype`, ordered by hop-distance then priority) is an implementation detail for when this gets built, not something this RFC needs to pin down further.

**Cycles**: deliberately *not* prevented on `containment` (see below) — game worlds can be legitimately non-Euclidean (a room whose exit leads back into itself, recursive pocket dimensions), so traversal code needs to handle cycles gracefully rather than the schema forbidding them. Prototype inheritance is a different kind of relationship, though: resolving an entity's effective stats means walking the prototype graph to a fixed point, and a cycle there (a prototype indirectly inheriting from itself) has no sensible resolution — it would just infinite-loop. Unlike containment, this one probably *does* need cycle prevention (a recursive-CTE check on write, most likely). Flagging it here since it wasn't explicitly covered when containment's cycles were discussed, and the two shouldn't be assumed to follow the same rule by default.

### Stats

`stat_definition` describes a stat (weight, size, HP, value, ...), including a `value_type` discriminant. `stat_group` clusters related stats ("physical," "combat," "economic") and carries the `priority` column used for inheritance tie-breaking above. Entities and prototypes acquire stat groups (making their stats available to inherit/set). Actual values live in `entity_stat`, with the value itself split into typed columns (`value_int`, `value_text`, `value_float`, `value_bool`) selected by `stat_definition.value_type` — keeping real type-checking at the database level instead of a single untyped column that every read has to parse and every write has to trust.

### Information and knowledge

`information` holds individual pieces of information about an entity — a description, an image, a claim, a note, a document — each with its own metadata (type, source, author, validity, and basic provenance as a field, not a full subsystem yet). `knowledge` connects a knower (a character, group, or user) to a specific `information` row, so different observers can know different — and differently *true* — things about the same entity. See the open question below: this currently means authoring parallel versions of a fact, not filtering one canonical version.

### Containment and other relationships

`containment(child_entity_id, parent_entity_id)` is a plain, generic entity-to-entity relation covering an item in a backpack, a backpack on a character, a character in a room, all the same table. Deliberately cycle-tolerant, per above. Other orthogonal relationships (location, time, ownership, observation, belief) are additional tables of the same shape, added later without touching this core.

### Views

Concrete types get a maintained view (`v_item` alongside `item`) exposing the commonly-needed inherited/computed properties as if they were plain columns — weight, value, size, current location, visual description. This is the load-bearing mitigation for the flexible core being otherwise hard to query, and needs to stay a disciplined practice (every concrete type gets one, kept in sync) rather than an afterthought, or the core's flexibility becomes a readability tax instead of a convenience.

## Open questions

### 1. Knowledge/information model: authored truths vs. redaction

As specified, different knowers link to different `information` rows — meaning a GM who wants character A to believe a lie has to author a second, separate `information` row for it, not just restrict visibility of the true one. That's probably right for a tool aimed at GMs who want to hand-craft rumors and misinformation, not just hide stats — but it's a real authoring-burden tradeoff, and it's not decided yet whether *some* facts should instead be "one truth, redacted per audience" while others are "genuinely different truths per observer." Both might be needed; which is the default and how they coexist isn't resolved.

### 2. Tenancy split

Every table above needs to fit into [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)'s RLS model, and it's not obvious that everything here is tenant-scoped the same way. Prototypes like "Physical Object," "Tool," and "Weapon" look like they should be shared across tenants — genuinely global, or scoped to a shared "repository" (see [docs/domain/repositories.md](../domain/repositories.md)) rather than owned by one tenant — while an instance like "My Shovel" is clearly tenant-owned. If prototypes and instances share the same `entity` table, RLS can't just check `entity.tenant_id`; it needs a rule for rows that are legitimately visible across tenants. `stat_definition`/`stat_group` likely want the same treatment. This needs resolving before any of these tables get a real migration, since retrofitting RLS onto rows that were assumed single-tenant is much more painful than designing it in from the first migration.

## Scope for the first slice: items

`entity`, `item` + `v_item`, `stat_definition`, `stat_group`, `entity_stat`, `entity_prototype`, `information`, `knowledge`, `containment`. Explicitly deferred: location as its own richer system (beyond plain containment), time, ownership, observation, belief, and provenance as a full subsystem (beyond the metadata field already on `information`).

## Consequences

- New stats, new prototypes, and new relationship types are data changes (new rows), not schema migrations — but that shifts governance to "who can edit `stat_definition`/prototypes and how are those changes reviewed," which has no tooling story yet and doesn't need one until it's actually a problem.
- Querying/filtering directly against `entity_stat` (e.g. "all items heavier than 5kg") means either going through `v_item`-style views or writing pivot/self-join queries by hand; this is the standard EAV cost and is accepted, mitigated by the views staying disciplined.
- The two open questions above block writing real migrations for any of this — resolving them is the next step, not a detail to sort out while implementing.
