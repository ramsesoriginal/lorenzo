# 0052 - Several game systems in one library: a system as a thing, with its own vocabulary, sheet and root

Status: proposed (2026-11-11), Decision open: the questions at the end are for the maintainer. It takes up what
[RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md) section 9 leaves as "a follow-up RFC" (resolving
through the system a campaign names), what [ADR 0037](../adr/0037-effective-stat-resolution.md) names as not built
(`game_system` as a modelled concept), and the three sheet settings of
[ADR 0281](../adr/0281-sheet-settings-and-the-sheet-read.md) and [ADR 0296](../adr/0296-being-stat-group.md). It changes
nothing decided in [RFC 0016](0016-stats-computed-values-and-crud-api.md) or ADR 0037 and 0266.

## Purpose

Let one library hold the stats, prototypes, sheets and repositories of several game systems at once, without any of them
having to know of the others, and let a repository carry one system without excluding another.

A table may share one world between a d20 system, a narrative system, a card-driven system and a system that is mostly
candles and text. Lorenzo assumes none of them. Today that library works only by convention, and the convention has holes.

## Decided inputs

1. **System-agnostic.** Nothing in the model, a seed or a starter assumes a game. A repository must not exclude another
   system, and a library may hold any number of systems.
2. **A system becomes a first-class thing**, carried by stat groups and repositories: a field, not a convention.
3. **The shared repositories are system-neutral:** Core holds names every system can use; each system has its own
   vocabulary repository; the item and character data of a system sits behind them.
4. **The sheet settings leave the tenant.** One being group, one weapon group and one ability type per library cannot
   serve two systems.
5. A campaign names its system (RFC 0033 section 9).

## What it is like today (tried against the API, 2026-11-10)

These are findings, not proposals.

- **It composes by convention.** Stats under a system prefix, one stat group per system, a base prototype per system
  holding that system's defaults and formulas, and one creature entry with a prototype from each system: all three
  systems' stats resolved on one entry, every formula was evaluated on the entry that was read, provenance was right, and
  the bulk read returned them side by side.
- **A name is global.** A definition's name is unique in a library: a second `speed` or `hp` is refused with a 500
  (`unhandled-exception`, SQL in `detail`), not a 409. The names the API reads (`weight`, `height`, `price`, `rarity`,
  `hp`, `armor`, `size`, the capacity names, `binding`, `is_container`) cannot be renamed, so the first system to define
  one fixes its type, unit and group for every system.
- **A merge keeps the local unit.** Two repositories that both define `speed` as an `int` merge on copy, and the
  library keeps the first one's unit: a value in metres reads as feet.
- **The sheet knows one system.** `being_stat_group_id` and `weapon_stat_group_id` each take one id, the sheet read
  returns the same payload whichever group is set, and a stat row of the entity read carries no group, so a client joins
  to the definitions by name. Beings draws every group the being has values for. Two weapon tables in one library are not
  possible.
- **`campaign.game_system` is free text.** Any string, including an empty one, is accepted and nothing reads it
  except a label; ADR 0024 and 0034 say it selects prototype variants, and no code does.
- **A campaign's own entry takes no stats**: its entry id is not exposed.
- **The seed already has a tag:** its `layer` (`core`, `dnd5e`) and the slug prefix of a layer (ADR 0143, 0168, 0181) are
  the nearest existing mechanism to a system.

## Hard invariants

- **Resolution does not change.** A system is a way to name, group and filter. Values still resolve over the whole
  prototype graph by distance, then group priority, then parent order (ADR 0037, 0266); a being with a prototype from
  each of three systems reads all of them.
- **Nothing is seeded and no system is special.** The platform ships no system, no system root and no neutral list of
  its own beyond the names the API reads.
- **A repository never excludes a system.** Copying a repository never removes, blocks or renames another system's
  content; a system's content is found by its slug.
- **Existing libraries keep working untouched.** Every definition and group that exists today is system-neutral.
- **A definition's system is as permanent as its group.** A definition's type and group cannot change
  (ADR 0014, 0390); its system follows its group.
- **Tenant isolation is by RLS** as ever (ADR 0002): a system is a tenant row with `tenant_id` and the same-tenant
  foreign keys (ADR 0117).

## Design (proposed)

### 1. A system is a row

`system(id, tenant_id, slug, name, root_entry_id null)`, `UNIQUE (tenant_id, slug)`. The slug is a short lowercase word
used as the name prefix and in repositories; it does not change once a stat group uses it. The name may be edited. The
root entry is the system root of ADR 0181 (the entry the system's top-level prototypes descend from), optional.

A library has no systems until someone makes one. Neutral content has no system.

### 2. Stat groups carry a system; definitions follow

`stat_group.system_id`, nullable (neutral). A definition's system is its group's. A group can be given a system when
it has none and no definition in it is read by the API by name.

**Names stay unique per library**, so entity reads, bulk reads and formulas keep working by name. Instead of scoping
names, a definition in a system must carry the system's slug and an underscore as its prefix (`ds_stamina`); the check
runs on create and rename. Two systems therefore cannot collide by construction, and a duplicate is a 409.

The names the API reads belong to the neutral scope: a definition with one of those names cannot be created in a system
(Question 6 asks whether the API should read roles instead of names).

### 3. The stat row says where it comes from

The entity read, the bulk read and the explanation add `stat_definition_id`, `group_id` and `system` (slug) to each stat
row. Adding fields breaks no client. A `system` filter on the entity read and the bulk read returns neutral stats and
that system's; without it, everything, as today.

### 4. Sheet settings per system

`being_stat_group_id`, `weapon_stat_group_id` and the ability type move to the system row; the tenant's own values stay
as the neutral default. The sheet read takes the system (a query value; the campaign's system when the request carries a
campaign) and returns that system's settings and groups. A weapons table draws the weapon group of the system in view,
so two systems have two weapon tables.

### 5. A campaign names a system

`campaign.system_id`, nullable, next to the free text, which stays as the display name until a library clears it. A campaign
is a table's use of a system; a library's entries are not tied to one. (Question 4: one system or several.)

### 6. Repositories carry systems

A system row is content: it is copied, merged by slug when the library already has one, and updated. A repository's
profile lists its systems, taken from its groups, and Discover gains the system as a facet, so "a vocabulary for system X"
is found. A repository that holds only neutral content has none.

- Copying a repository whose group belongs to a system the library already has joins that system, by slug; the library's
  own name and root stay.
- Merging two neutral definitions of one name asks for a choice when their units or bounds differ (the check ADR 0119
  lacks today), so a unit is never silently reread.
- A repository may hold several systems, such as a bundle that relates two.

### 7. The seed's layer becomes the system

`lorenzo seed --layer` already sorts a vocabulary into core and a system; it creates the system row and gives the
layer's groups to it. `unseed --layer` removes what the system holds, as ADR 0168 does for a layer.

### What a person sees

A library with one system sees what it sees today. A library with several has a system picker on its sheets and in the
Bench vocabulary pane; a campaign's sheets open on its system; the vocabulary reads "neutral" and one heading per system.

## Delivery

Each slice is its own ADR, and the work is not started until the questions below are answered.

1. **Y1.** The `system` table, `stat_group.system_id`, the prefix check, a 409 on a duplicate group or definition
   name, and the extra fields on stat rows.
2. **Y2.** The `system` filter on the entity and bulk reads; Beings and Bench group by it.
3. **Y3.** Sheet settings on the system; the sheet read takes a system; `campaign.system_id`.
4. **Y4.** Repositories: copy, update and release carry systems; the profile and Discover facet; the unit check on merge.
5. **Y5.** The seed layers create systems; the starter vocabularies (a guide) use them.

## Not in scope

Each of these uses a system and is its own RFC if taken up.

- **Sheet templates** ([RFC 0018](0018-entity-template.md), closed by [RFC 0041](0041-entity-kinds-and-author-freedom.md)
  section 10 until a read-side view is asked for): an ordered view of the stat groups and notes a sheet shows. A system
  is what a template would be filtered by, and a template's slots are where "hide" and "label" belong, as a view's
  choice rather than a definition's.
- **Unit conversion and display units.** Today a unit is one string per definition and nothing converts.
- **A feature kind.** A character feature, a spell, a feat, an upgrade, with the system field and a granted-by link.
- Resolving an item through the system a campaign names in a library's catalog, which has no campaign (RFC 0033 section 9):
  the system filter of slice Y2 gives a read the system; the catalog's choice is left to its client.
- Formula kinds, display fields on a definition, and starter vocabularies are separate work.

## Open questions

1. **Row or word.** A `system` row (settings, a root, a facet) or only a slug on groups and repositories.
2. **The prefix rule.** Enforced on create and rename, or a convention with a lint.
3. **Where the system lives.** On the group only, or on the definition as well (the definition cannot change group, so the
   second adds nothing but a faster filter).
4. **A campaign's systems.** One, or several (a table that plays a narrative game inside a d20 campaign).
5. **Where the sheet settings live.** On the system row, or on the system's root entry.
6. **Names or roles.** The API reads `weight`, `hp` and the rest by name, which is why they cannot be renamed and why
   one system's choice binds all. It could read a role (`weight`, `carry_capacity`, ...) attached to a definition
   instead, with the current names backfilled; names would then be free and a unit per role would be explicit. That amends
   ADR 0390 and the hover-card and capacity reads.
7. **The neutral names in Core.** A first draft exists and is to be revised once the earlier questions are answered.

## Alternatives considered

- **Scope names per system** (`hp` in two systems). Clean for authors, but every read is keyed by name today and a
  formula, a bulk read and a hover card would need the system to mean one stat. Rejected for the prefix rule, which gives
  the same result with no change to a read's shape.
- **Separate libraries per system.** Works today and keeps vocabularies apart, but entries cannot be shared, which is what
  a shared world is.
- **A convention only.** The guide "Modelling a game system" states one (prefix every stat of a system). It cannot
  give the sheet settings, the campaign or the repository a system, and a duplicate still collides.
- **Per-system resolution** (a system changes what an entry's value resolves to). Rejected: resolution stays as it is
  (invariant above), and a system narrows what is shown.

## Consequences

- A library with one system, or none, behaves as today. A library with several gets no collision and one sheet per
  system.
- Stat rows grow three fields; a client that keyed on name keeps working.
- The prefix rule makes a slug permanent, which makes a system's rename a name change only.
- Three tenant columns become per-system, with the tenant's own as the neutral default.
- A repository that includes or shows a source carries that source's systems with it; ADR 0431 and 0437 apply as they do.
