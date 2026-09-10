# RFC: Core domain data model (entity/component architecture)

Status: proposed — three open questions below need resolving before this can become an ADR

## Context

The domain (see [docs/domain](../domain)) needs: extensible attributes without a migration per new stat, shared reusable templates with per-instance overrides, several independent relationship types over the same objects (containment being the first), and — the hard part — different observers knowing different things about the same entity. A conventional one-table-per-concept schema (`item` with a fixed column list, etc.) can't grow into that without constant redesign. [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md)'s RLS approach and [ADR 0010](../adr/0010-user-tenant-membership-model.md)'s tenant model exist, but nothing yet defines what the tenant-scoped tables actually _are_.

## Decision

### Core entity

`entity` is the universal table: anything that can exist, be referenced, contained, described, or related to something else is a row here — an item, a being, a place, a prototype like "Shovel," all the same underlying kind of thing. Concrete semantic tables (`item`, `being`, `place`, ...) FK to `entity` and add only what actually makes that kind of thing distinct (class-table-inheritance pattern) — they don't duplicate anything the flexible core already provides. `being` covers anything sentient/agentive — a player character, an NPC, a monster — as one table; whether a being is player-controlled is a derived fact (does it have an owning player, see [RFC 0002](0002-campaign-player-character-model.md)), not a stored type. Splitting PC/NPC into their own concrete tables is deferred until something needs a column neither can share.

An entity isn't limited to one concrete table: nothing stops the same `entity_id` from having rows in both `item` and `being` at once — a sentient sword, or a summoned creature that's also tracked as inventory, per [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md)'s explicit "beings can be items, and items can act like beings." Ownership (see [RFC 0002](0002-campaign-player-character-model.md)) references the entity generically rather than assuming it's item-typed, for the same reason.

### Prototypes and inheritance

A prototype isn't a separate kind of row — it's just an `entity` that happens to be referenced as a parent by another entity. "Shovel" is an ordinary entity that inherits from "Physical Object," "Tool," "Weapon," and "Crafting Supply"; "My Shovel" is an ordinary entity that inherits from both "Shovel" and "Cursed Item," overrides some inherited values, and adds instance-specific information. One join table (`entity_prototype(entity_id, prototype_id)`) covers both cases — an entity can have any number of rows here, giving multiple inheritance for free.

**Conflict resolution**, when two ancestors define the same stat differently: more specific wins — a value defined closer to the entity (fewer inheritance hops away) beats one defined further out, and an instance-level override always beats anything inherited. When two ancestors are equally specific (e.g. two prototypes inherited directly), the tie breaks on `stat_group.priority` — the value acquired through the higher-priority stat group wins. The exact resolution query (recursive walk over `entity_prototype`, ordered by hop-distance then priority) is an implementation detail for when this gets built, not something this RFC needs to pin down further.

**Cycles**: deliberately _not_ prevented on `containment` (see below) — game worlds can be legitimately non-Euclidean (a room whose exit leads back into itself, recursive pocket dimensions), so traversal code needs to handle cycles gracefully rather than the schema forbidding them. Prototype inheritance is a different kind of relationship, though: resolving an entity's effective stats means walking the prototype graph to a fixed point, and a cycle there (a prototype indirectly inheriting from itself) has no sensible resolution — it would just infinite-loop. Unlike containment, this one probably _does_ need cycle prevention (a recursive-CTE check on write, most likely). Flagging it here since it wasn't explicitly covered when containment's cycles were discussed, and the two shouldn't be assumed to follow the same rule by default.

### Stats

`stat_definition` describes a stat (weight, size, HP, value, ...), including a `value_type` discriminant. `stat_group` clusters related stats ("physical," "combat," "economic") and carries the `priority` column used for inheritance tie-breaking above. Entities and prototypes acquire stat groups (making their stats available to inherit/set). Actual values live in `entity_stat`, with the value itself split into typed columns (`value_int`, `value_text`, `value_float`, `value_bool`) selected by `stat_definition.value_type` — keeping real type-checking at the database level instead of a single untyped column that every read has to parse and every write has to trust. Not yet handled: which game system a stat/stat group belongs to — see the open question below.

### Information and knowledge

`information` is the metadata container for a single piece of information about an entity — its narrative type (a rumor, an official record, a GM note, ...), source, author, validity, and basic provenance as a field, not a full subsystem yet. The actual content is one or more `payload`s attached to it (a description, an image, a claim, a note, a document, each individually typed) — so one `information` row can bundle two images and a paragraph of text, or three alternate texts, or just a single note, with the shared metadata (who said this, how reliable it is) applying to the whole bundle rather than to each payload separately.

`knowledge` connects a **knower** to a specific `information` row, so different observers can know different — and differently _true_ — things about the same entity. A knower is one of: a single character (`knower_entity_id`, referencing a `being`), a group of characters (`knower_entity_id` again — a group is a bare `entity` with no dedicated concrete table yet, membership via `group_member(group_entity_id, character_entity_id)`), or a player (`knower_player_id`, see [RFC 0002](0002-campaign-player-character-model.md) — deliberately the campaign-scoped `player`, not the global `User`, since knowledge is always relative to a specific campaign). Exactly one of `knower_entity_id`/`knower_player_id` is set per row. The fourth case, "known to everyone," doesn't use `knowledge` at all: `information.is_public` (boolean) bypasses the knower lookup entirely — GM-only information is just the default (`is_public = false`, no `knowledge` rows), not a separate flag.

See the open question below: supporting multiple knowers at all currently means authoring parallel versions of a fact, not filtering one canonical version.

### Containment and other relationships

`containment(child_entity_id, parent_entity_id)` is a plain, generic entity-to-entity relation covering an item in a backpack, a backpack on a character, a character in a room, all the same table. Deliberately cycle-tolerant, per above. Other orthogonal relationships are additional tables of the same shape, added without touching this core — `ownership` (see [RFC 0002](0002-campaign-player-character-model.md)) is the first; location, time, observation, and belief remain undesigned.

### Views

Concrete types get a maintained view (`v_item` alongside `item`) exposing the commonly-needed inherited/computed properties as if they were plain columns — weight, value, size, current location, visual description. This is the load-bearing mitigation for the flexible core being otherwise hard to query, and needs to stay a disciplined practice (every concrete type gets one, kept in sync) rather than an afterthought, or the core's flexibility becomes a readability tax instead of a convenience.

## Open questions

### 1. Knowledge/information model: authored truths vs. redaction

**Resolved for what gets built**: [ADR 0028](../adr/0028-knowledge-and-group-membership.md) builds `knowledge`/`group_member`/`information.is_public` exactly as specified below — the "authored truths" mechanism, not a redaction mechanism. What's still open is unchanged by that ADR: whether _some_ facts should instead be "one truth, redacted per audience," whether that's the default or authored-truths is, and how the two would coexist — none of that is decided, it's just not what ADR 0028 builds. Also still deferred: the temporal/event richness [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md) asks for ("who learned what, and as of when") — ADR 0028's `knowledge` is a static knower-to-information link only.

_Who_ can be a knower is settled (character, group, player, or everyone via `is_public` — see above). What's still open is _how_ multiple knowers relate to the same fact: as specified, different knowers link to different `information` rows — meaning a GM who wants character A to believe a lie has to author a second, separate `information` row for it, not just restrict visibility of the true one. That's probably right for a tool aimed at GMs who want to hand-craft rumors and misinformation, not just hide stats — but it's a real authoring-burden tradeoff, and it's not decided yet whether _some_ facts should instead be "one truth, redacted per audience" while others are "genuinely different truths per observer." Both might be needed; which is the default and how they coexist isn't resolved.

### 2. Tenancy split

Resolved in part: every table in this RFC and in [RFC 0002](0002-campaign-player-character-model.md) gets a `tenant_id` column and an RLS policy, no exceptions — confirmed, so this no longer blocks writing the first slice's migrations. What's still open is narrower: prototypes like "Physical Object," "Tool," and "Weapon" sourced from a shared "repository" (see [docs/domain/repositories.md](../domain/repositories.md)) need to be usable by many tenants without actually living inside any one of them — a plain `entity.tenant_id` can't represent that. The likely shape is that repository content lives in its own, separately-authored tables outside the tenant-scoped graph entirely, and a tenant/campaign references or copies from it rather than repository rows needing a tenant exception — but that's not designed, and isn't needed until repositories themselves are (out of scope for the items slice, which uses neither).

### 3. Multi-game-system stats

The same conceptual item needs different mechanical stats depending on which ruleset it's being used in — a sword's D&D stat block (Armor Class bonus, damage die, weight in pounds) and its Blades in the Dark stat block (load, tier, a quality rating) share almost no mechanical structure, even though they share the same name, flavor text, and image. `stat_definition`/`stat_group` as specified have no notion of which game system they belong to, and it's not decided whether _every_ stat should be scoped to exactly one system, or whether some (the physical/narrative ones — weight, size, a description) are system-agnostic while others (HP, Armor Class, a stress track) are system-specific.

One promising direction, not decided: this might not need a new scoping column at all, and could instead reuse the prototype mechanism already designed above — a system-agnostic "Sword" prototype carries the shared information and payloads, and separate "Sword (D&D 5e)" / "Sword (Blades in the Dark)" prototypes each inherit from it and add their own system-specific stat groups, with a campaign's instances inheriting from whichever variant matches its ruleset. That would make "which system is this for" a property of _which prototype you inherited from_, not a column on every stat. Worth exploring before assuming a `game_system_id` column is the right fix.

## Scope for the first slice: items

`entity`, `item` + `v_item`, `stat_definition`, `stat_group`, `entity_stat`, `entity_prototype`, `information`, `knowledge`, `containment`. (Ownership moved to [RFC 0002](0002-campaign-player-character-model.md), which needed it for character-owned items and included it in its own first-slice scope.) Explicitly deferred: location as its own richer system (beyond plain containment), time, observation, belief, and provenance as a full subsystem (beyond the metadata field already on `information`).

## Consequences

- New stats, new prototypes, and new relationship types are data changes (new rows), not schema migrations — but that shifts governance to "who can edit `stat_definition`/prototypes and how are those changes reviewed," which has no tooling story yet and doesn't need one until it's actually a problem.
- Querying/filtering directly against `entity_stat` (e.g. "all items heavier than 5kg") means either going through `v_item`-style views or writing pivot/self-join queries by hand; this is the standard EAV cost and is accepted, mitigated by the views staying disciplined.
- None of the three open questions above block writing the items slice's migrations — tenancy is resolved for every table the slice actually uses, and both remaining questions (redaction mode, multi-game-system stats) only matter once knowledge conflicts or a second game system actually show up.
