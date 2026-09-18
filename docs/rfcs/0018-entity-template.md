# RFC: `entity_template` — a curated, ordered composite of information and stats

Status: proposed

## Context

Everything built or proposed so far answers "what is this entity" (`entity_prototype`, [ADR 0015](../adr/0015-entity-prototype.md)), "what does it narratively carry" ([RFC 0015](0015-information-metadata-shape.md)'s `information`/`payload`), and "what does it mechanically carry, directly or computed" ([RFC 0016](0016-stats-computed-values-and-crud-api.md)). Nothing yet answers a fourth, genuinely different question: **which specific combination of those, in what order, constitutes "a D&D 5e character sheet" vs. "a full magical-weapon description" vs. "a Blades in the Dark hideout" vs. "a chapter in a book"** — a client today has to already know which information types and stat groups it cares about and hardcode that shape itself. This RFC adds that shape as data: a small number of new tables (`entity_template` and friends) let a tenant define a named, ordered projection over an entity's information/stats, and a new endpoint reads it back assembled.

This is explicitly a first step toward game systems as a modeled concept, not the whole of it — see Not in Scope for what it deliberately doesn't attempt yet.

## Decision

### `entity_template` — the definition, tenant-scoped

`entity_template(id, tenant_id, name, ...)`, `UNIQUE(tenant_id, name)`, matching every other named-thing convention in this schema.

### The filter — a single row, two optional, ANDed dimensions, not a general predicate system

`entity_template_filter(template_id, tenant_id, required_kind, required_prototype_entity_id)` — both columns nullable, both apply together when set:

- **`required_kind`** (nullable enum: `item`/`being`/`place`) — matches on the entity's concrete kind, i.e. which class-table-inheritance extension row it has.
- **`required_prototype_entity_id`** (nullable FK to `entity.id`) — matches if that entity appears anywhere in the target's own `entity_prototype` ancestry, reusing the exact ancestor-walk already built for stat resolution ([ADR 0037](../adr/0037-effective-stat-resolution.md)), not a new traversal mechanism.

Deliberately **one row, not a list of arbitrary criteria, and no OR-groups** ("applies to A or B"): every real example from this RFC's own motivation (a D&D 5e character sheet, a kill-team operator) wants "this concrete kind, and descends from this one prototype" — a single template per distinct shape, not a template trying to cover several unrelated ancestries at once. This is the same curated-over-general instinct that decided [RFC 0016](0016-stats-computed-values-and-crud-api.md)'s computed-stat mechanism — kept consistent here rather than building a small boolean-expression system for a need none of the motivating examples actually have.

### `entity_template_slot` — the ordered body

`entity_template_slot(id, template_id, tenant_id, order, information_type, stat_group_id)`, `UNIQUE(template_id, order)`, `CHECK(num_nonnulls(information_type, stat_group_id) = 1)` — the same "exactly one of N nullable columns" idiom `entity_stat`/`knowledge` already establish, not a new pattern.

**`information_type` is a plain text column, not a foreign key to `information_type`** ([RFC 0015](0015-information-metadata-shape.md)'s catalog table) — worth flagging explicitly, since it's an easy trap: that catalog deliberately holds only the small, fixed, technical subset (`description`, `main_picture`); every real slot a template author actually wants (`note`, `spell_effects`, `backstory`, anything GM-invented) has no catalog row by design. A slot references `information.type` the same free-text way `information` itself does, not through the catalog.

`stat_group_id` is a plain FK to `stat_group.id` — no equivalent gap, since every `stat_group` already has a real row.

### Reading: explicit request, not auto-resolution — plus a discovery endpoint

`GET /tenants/{tenant_id}/entities/{entity_id}/templates/{template_id}` — the caller names the template; the endpoint validates the entity actually matches its filter (rejecting rather than guessing if it doesn't) and returns the assembled result. Deliberately **not** "find the one template that applies" — the moment two templates could both match the same entity, auto-resolution needs an invented tie-break with no principled answer, the same reasoning this project's stat-resolution work already went through once.

`GET /tenants/{tenant_id}/entities/{entity_id}/matching-templates` — lists every template whose filter actually matches this entity, for a client that wants to offer a picker rather than already knowing which template it wants.

The assembled response is a genuinely **ordered array**, not a JSON object relying on key-insertion-order as an implicit contract — one entry per slot, each carrying its own order, its kind (`information`/`stat_group`), and the resolved content (an `Information`'s title/content for an information slot; that group's own resolved stat bundle, reusing [RFC 0016](0016-stats-computed-values-and-crud-api.md)'s per-field direct/computed/inherited/empty shape, for a stat-group slot).

### Template-definition CRUD is in scope now; writing *values* through a template is not

Two different things, worth keeping clearly separate: **authoring a template** (which slots exist, in what order, what the filter is) needs to work from day one, or nothing above is buildable at all — `POST /tenants/{tenant_id}/templates` (creates the template + filter row atomically, mirroring `create_information`'s existing atomic-multi-table precedent), `PATCH`/`DELETE` on the template itself, `POST`/`PATCH`/`DELETE` on its slots. Reordering slots reuses whatever shape [RFC 0015](0015-information-metadata-shape.md)'s own deferred reorder endpoint eventually settles on, rather than re-deciding the same "unique-order-among-siblings" problem independently here.

**Writing entity *values* through the composite template shape — a merge-patch against the assembled JSON that routes each field to the correct underlying `Information` or stat write — is explicitly deferred.** This is real, non-trivial orchestration (coordinating two structurally different sub-resource kinds under one atomic patch), and it isn't needed to get value from this RFC: every field a template would expose is already directly writable through [RFC 0015](0015-information-metadata-shape.md)'s `Information` endpoints and [RFC 0016](0016-stats-computed-values-and-crud-api.md)'s stat bundle today — a world gets populated piece by piece through those, same as now, while the template layer starts out read-only.

## Not in scope

- **Composite writes through a template** (see above) — the read side stands alone and is worth building first.
- **OR-groups / multiple filter criteria per template** — one concrete-kind-and-ancestry pair per template, per the curated-not-general reasoning above; revisit only if a real case needs it.
- **Nested templates** (a slot referencing another template, e.g. a "book chapter" template embedding a per-character sub-template) — a natural-looking extension, not scoped here.
- **Cross-tenant, reusable "game system" templates.** This is the one genuinely deferred here on purpose, not an oversight: a template that could serve every tenant running the same game system needs its `stat_group` references to also be shareable across tenants, and `stat_group` is `UNIQUE(tenant_id, name)` — strictly per-tenant today. That's not a new gap this RFC is inventing; it's [RFC 0001](0001-core-domain-data-model.md)'s own still-open "repository" question (referenced in [docs/domain](../domain/entities-knowledge-and-visibility.md) as "the same underlying repository... used across systems") — solving it is a real future step, once basic, tenant-scoped, game-system-agnostic templates are actually working, not a prerequisite for this RFC.

## Consequences

- `entity_template_filter`'s prototype-ancestry check reuses [ADR 0037](../adr/0037-effective-stat-resolution.md)'s ancestor walk conceptually, but needs its own query against it (checking *membership*, not resolving a value) — a related, not identical, use of that mechanism.
- Templates stay tenant-scoped, meaning **no template is portable across tenants today** — every tenant running the "same" game system currently has to redefine its own templates and stat groups independently, a real, named limitation until the repository question above gets solved.
- The read endpoint's assembled shape depends on both [RFC 0015](0015-information-metadata-shape.md) and [RFC 0016](0016-stats-computed-values-and-crud-api.md) already existing — this RFC is not independently buildable ahead of either.
- `entity_template_slot.information_type` being a plain string, not a catalog FK, means nothing stops a template from referencing an `information.type` value that doesn't exist on any entity yet — that slot just resolves empty, the same "acquired but unset" shape [RFC 0016](0016-stats-computed-values-and-crud-api.md)'s unified stat bundle already handles for stats.
