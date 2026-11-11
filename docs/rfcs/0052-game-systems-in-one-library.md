# 0052 - Several game systems in one library: a system as a thing, with its own vocabulary, templates and root

Status: accepted (2026-11-11), decided with the maintainer, not built; slices Y1 to Y6, each its own ADR. It takes up what
[RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md) section 9 leaves as "a follow-up RFC" (resolving
through the system a campaign names), what [ADR 0037](../adr/0037-effective-stat-resolution.md) names as not built
(`game_system` as a modelled concept), the three sheet settings of
[ADR 0281](../adr/0281-sheet-settings-and-the-sheet-read.md) and [ADR 0296](../adr/0296-being-stat-group.md), and the
read-side view that [RFC 0041](0041-entity-kinds-and-author-freedom.md) section 10 keeps open after closing
[RFC 0018](0018-entity-template.md). It changes nothing decided in [RFC 0016](0016-stats-computed-values-and-crud-api.md)
or ADR 0037 and 0266.

## Purpose

Let one library hold the stats, prototypes, sheets and repositories of several game systems at once, without any of them
having to know of the others, and let a repository carry one system without excluding another.

A table may share one world between a d20 system, a narrative system, a card-driven system and a system that is mostly
candles and text. Lorenzo assumes none of them. Today that library works only by convention, and the convention has holes.

## Decided inputs

1. **System-agnostic.** Nothing in the model, a seed or a starter assumes a game. A repository must not exclude another
   system, and a library may hold any number of systems.
2. **A system is a row**, carried by stat groups, templates and repositories: a thing, not a convention.
3. **A campaign names one system.**
4. **Sheet templates are part of this RFC**, as the read-side view RFC 0041 section 10 allows; the sheet settings move
   into them, and what a definition would carry to hide or relabel itself is a template's choice.
5. **The API reads roles, not names**, as long as reads do not get slower.
6. **The shared repositories are system-neutral:** Core holds what every system can use; each system has its own
   vocabulary repository; the data of a system sits behind them.
7. **Unit conversion is left out** until a table asks for it.
8. **The prefix rule is enforced** on create and rename: a definition in a system starts with the system's slug and an
   underscore.
9. **A definition stays in one group.** A template lists a stat under several systems.
10. **The sheet settings live in templates,** not on the system row.
11. **Role-holders are neutral:** a system may not hold a role.
12. **A template's filter is the kind and the ancestor** of RFC 0018; the campaign picks the system. A template's
    `system_id` only names its system for that pick and is not part of the filter.
13. **The slot kinds** are `stats`, `information`, `held` and `tags`; a `features` slot is added by RFC 0054.
14. **Data model and API only.** No app, frontend or command-line change is part of this RFC, and every existing request and
    response keeps working as it does now (see Compatibility).

## What it is like today (tried against the API, 2026-11-10)

Findings, not proposals.

- **It composes by convention.** Stats under a system prefix, one stat group per system, a base prototype per system
  holding that system's defaults and formulas, and one creature entry with a prototype from each system: all three
  systems' stats resolved on one entry, every formula was evaluated on the entry that was read, provenance was right, and
  the bulk read returned them side by side.
- **A name is global.** A definition's name is unique in a library: a second `speed` or `hp` is refused with a 500
  (`unhandled-exception`, SQL in `detail`), not a 409. The names the API reads (`weight`, `height`, `price`, `rarity`,
  `hp`, `armor`, `size`, the capacity names, `binding`, `is_container`) and the group names it reads (`physical`,
  `economic`, `destroyable`, `damaging`, `tags`) cannot be renamed, so the first system to define one fixes its type,
  unit and group for every system.
- **A merge keeps the local unit.** Two repositories that both define `speed` as an `int` merge on copy, and the
  library keeps the first one's unit: a value in metres reads as feet.
- **The sheet knows one system.** `being_stat_group_id` and `weapon_stat_group_id` each take one id, the sheet read
  returns the same payload whichever group is set, and a stat row of the entity read carries no group, so a client joins
  to the definitions by name. Beings draws every group the being has values for, intermediate stats included. Two weapon
  tables in one library are not possible.
- **`campaign.game_system` is free text.** Any string, including an empty one, is accepted and nothing reads it
  except a label; ADR 0024 and 0034 say it selects prototype variants, and no code does.
- **A campaign's own entry takes no stats**: its entry id is not exposed.
- **The seed already has a tag:** its `layer` (`core`, `dnd5e`) and the slug prefix of a layer (ADR 0143, 0168, 0181) are
  the nearest existing mechanism to a system.

## Hard invariants

- **Resolution does not change.** A system is a way to name, group and show. Values still resolve over the whole
  prototype graph by distance, then group priority, then parent order (ADR 0037, 0266); a being with a prototype from
  each of three systems reads all of them.
- **Nothing is seeded and no system is special.** The platform ships no system and no system root.
- **A repository never excludes a system.** Copying a repository never removes, blocks or renames another system's
  content; a system is found by its slug.
- **Existing libraries keep working untouched.** Every group, definition and sheet that exists today stays as it is:
  neutral, and drawn as before when no template applies.
- **A definition belongs to one group and keeps it** (ADR 0014, 0390); its system is its group's, and as permanent.
- **A template only reads.** What it shows is what the caller may read, by the rules each source already has.
- **Tenant isolation is by RLS** as ever (ADR 0002): every new table has `tenant_id` and same-tenant foreign keys
  (ADR 0117), and a line in the copyable-table registry (ADR 0218).

## Design (proposed)

### 1. A system is a row

`system(id, tenant_id, slug, name, root_entry_id null)`, `UNIQUE (tenant_id, slug)`. The slug is a short lowercase word
used as the name prefix and in repositories; it does not change once a stat group uses it. The name may be edited. The
root entry is the system root of ADR 0181, optional.

A library has no systems until someone makes one. Neutral content has no system.

### 2. Stat groups carry a system; definitions follow

`stat_group.system_id`, nullable (neutral); a definition's system is its group's. A definition stays in one group: the
group is the unit of the tie-break priority an entry has acquired (ADR 0037), and a definition in two groups would have
two priorities and, if the groups belonged to two systems, two systems. A stat that a sheet shows under several systems
is listed by the templates of each, not put in several groups (section 4).

**Names stay unique per library**, so entity reads, bulk reads and formulas keep working by name. Instead of scoping
names, a definition in a system must start with the system's slug and an underscore (`ds_stamina`); the check runs on
create and rename. Two systems then cannot collide by construction, and a duplicate is a 409, not a 500. Neutral
definitions take any name. Labels shown to a person come from the template (section 4), so the prefix does not reach a
sheet.

### 3. Roles, not names, for what the API reads

A definition may carry a `role` and a group a `role`, each from a closed list kept in the API: for definitions `weight`,
`height`, `price`, `rarity`, `hp`, `armor`, `size`, `carry_capacity`, `containment_capacity`, `max_item_size`, `binding`,
`is_container`; for groups `physical`, `economic`, `destroyable`, `damaging`, `tags`. `UNIQUE (tenant_id, role)` where the
role is set; a new assignment of a role must fit the types that role accepts today (a `weight` a number, a `binding` an
`enum` with its reserved values; `rarity` a number, a `text` or an `enum`, since the named field reads a number and the hover
card shows the text).

The capacity checks, `binding`, the named fields of an item read, the named stat lists and the hover cards read the role
where they read the name today. The migration gives the role to **every** existing definition and group with the name,
whatever its type, so each read answers as it does now (the named `rarity` field of an item stays `null` for an `enum`, and
the hover card still shows it); only a later assignment is checked against the types. A role-holder is neutral, so one system's choice no longer binds the name: the holder may be
renamed, and a system's own `ds_weight` is an ordinary stat.

**Cost.** The lookup becomes `role = ...` on a partial unique index of the same shape as the `(tenant_id, name)` index it
replaces, in the views and in `capacity.py` and `link_previews.py`: no extra join. The statement-count tests
([ADR 0285](../adr/0285-api-reads-that-cost-what-they-read.md)) and the bulk-read timings gate the slice, as they gated it before.

### 4. Templates: a system's sheets as data

RFC 0018 asked for "an ordered, curated projection over an entity's information and stats". RFC 0041 section 10 closed it
until a case that parents cannot cover appears. The case is here: a sheet has to say which of a being's stat groups and
notes it shows, in what order, under which labels, and a library with several systems needs one such view per system.

`template(id, tenant_id, name, system_id null, required_kind null, required_ancestor_entry_id null)`, with the single-row
filter of RFC 0018: an entry matches when it has the kind and the ancestor, the ancestor being any entry on its prototype
walk (ADR 0037's walk, asked for membership). A system's top-level template names the system's root as ancestor.

`template_slot(id, template_id, tenant_id, position, kind, ...)`, `UNIQUE (template_id, position)`. A slot is one of:

| Slot kind | Shows |
| --- | --- |
| `stats` | an ordered list of stat definitions, or a stat group, with a label for each and a list of definitions to leave out |
| `information` | notes of an information type |
| `held` | the things the entry holds, as a table: a column for each stat of a list or a group; each row carries the thing, its quantity and the typed value of each cell (a `bool` stays a `bool`), in the order the slot names (by name, or by prototype and then name) |
| `tags` | the `bool` stats that are true |

A label, a hidden stat and the order are the slot's, not the definition's; the intermediate stats of a formula chain are
simply not listed.

**Reading.** `GET /tenants/{t}/entities/{e}/templates/{id}` assembles the view for the entry, as an ordered array with the
resolved values, labels and units. `GET .../matching-templates` lists the templates whose filter matches, and a campaign
that names a system picks that system's template for the entry's kind. Nothing is chosen automatically when two match
(RFC 0018's reasoning stands). Each slot is filtered by the rules of the thing it reads: notes through the information
visibility check, held things through the reach of ADR 0040, stat values as the entity read is; a slot the caller may not
read is omitted, never silently filled.

**Authoring** is the vocabulary's tier (any member). Writing values through a template stays out, as in RFC 0018. A
template, its slots and the filter are content a repository can hold: the group and definition ids in a slot are
re-pointed on copy as a formula's inputs are.

**The sheet settings** (`being_stat_group_id`, `weapon_stat_group_id`, the ability type) become slots: the being group a
`stats` slot, the weapon group the columns of a `held` slot, the ability type an `information` slot. A library with no
template keeps drawing from the tenant's own settings as today.

### 5. The stat row says where it comes from

The entity read, the bulk read and the explanation add `stat_definition_id`, `group_id` and `system` (slug) to each stat
row. Adding fields breaks no client. A `system` filter on the entity read and the bulk read returns neutral stats and that
system's; without it, everything, as today.

### 6. A campaign names one system

`campaign.system_id`, nullable, next to the free text, which stays the display name until a library clears it. A campaign is
a table's use of one system; a library's entries are not tied to one.

### 7. Repositories carry systems

A system row is content: it is copied, merged by slug when the library already has one, and updated, with its templates. A
repository's profile lists its systems, taken from its groups, and Discover gains the system as a facet, so "a vocabulary
for system X" is found. A repository that holds only neutral content has none.

- Copying a repository whose group belongs to a system the library already has joins that system, by slug; the library's
  own name and root stay.
- A role is a collision kind of its own: two definitions with one role merge (same type) or one is skipped.
- Merging two definitions of one name whose units or bounds differ still merges, and keeps the library's own, as today;
  the copy plan and the copy's response gain a `warnings` list that names each such merge, and a request may send
  `strict_units: true` to have the copy refuse until each is resolved. A unit is then never reread without being told.
- A repository may hold several systems, such as a bundle that relates two.

## Compatibility

This RFC changes the data model and the API, and only those: no app, client or command-line change is part of it. Every
existing request keeps its path, its body, its response and its status, with these exceptions, each a fix or a relaxation:

- A duplicate group or definition name on create answers 409 (`stat-group-name-taken`, `stat-definition-name-taken`) instead
  of 500, the answers `PATCH` rename already gives.
- A definition that holds a role can be renamed, which `PATCH` refuses today (409 `stat-name-reserved`).
- A copy that merges definitions of different units now reports it in `warnings`.

Everything else is an addition with a default that leaves behaviour as it is: new tables and nullable columns, new fields on
responses, a `system` query value and a `strict_units` flag that are off unless sent, new endpoints. A library with no
system and no template reads and writes as it does now, and the sheet draws from the tenant's own settings. A group takes a
system only when its definitions already carry the prefix, so existing groups stay neutral unless their definitions are
renamed first.

## Delivery

Each slice is its own ADR.

1. **Y1.** The `system` table, `stat_group.system_id`, the prefix check, a 409 on a duplicate group or definition name,
   and the extra fields on stat rows.
2. **Y2.** Roles: the column, the backfill, the reads that use it, the collision kind.
3. **Y3.** The `system` filter on the entity and bulk reads.
4. **Y4.** Templates: tables, authoring, the read and matching endpoints, the registry lines.
5. **Y5.** `campaign.system_id`; the sheet read and the sheet settings through templates.
6. **Y6.** Repositories: copy, update and release carry systems, templates and roles; the profile and Discover facet; the
   unit warnings on merge.

## Not in scope

- **Apps and the command line.** Pickers, panes, drawing a template, and mapping the seed's `layer` onto systems are the
  apps' and the CLI's own work.
- **Unit conversion and display units**: left out for now.
- **Features** (a character feature, a spell, a feat, an upgrade, with grants and choices): RFC 0054, which uses a
  template's slots and a system.
- **Formula kinds** (min, max, select, product, ratio, aggregation over what an entry holds): RFC 0053.
- Writing values through a template; nested templates; an OR in a template's filter (RFC 0018's list).
- Resolving an item in a library's catalog, which has no campaign, through a system (RFC 0033 section 9): the `system`
  filter gives a read the system; the catalog's choice is left to its client.

## Suggested future work

Not part of this RFC, and not decided; the CLI's own work, once the slices above exist:

- `lorenzo seed --layer` already sorts a vocabulary into core and a system. It could create the system row and give the
  layer's groups and templates to it, and `unseed --layer` could remove what the system holds, as
  [ADR 0168](../adr/0168-lorenzo-unseed.md) does for a layer.
- Starter vocabularies and templates for a system, shipped as a public vocabulary-only repository.

## Open questions

None.

## Alternatives considered

- **Scope names per system** (`hp` in two systems). Clean for authors, but every read is keyed by name and a formula, a bulk
  read and a hover card would need the system to mean one stat. Rejected for the prefix rule, which gives the same result
  with no change to a read's shape.
- **Separate libraries per system.** Works today and keeps vocabularies apart, but entries cannot be shared, which is what a
  shared world is.
- **A convention only.** The guide "Modelling a game system" states one (prefix every stat of a system). It cannot give the
  sheet settings, the campaign or the repository a system, and a duplicate still collides.
- **A stat in several groups.** Gives the sheet what a template gives it, but breaks the tie-break (two priorities for one
  stat) and the rule that a definition's system is its group's.
- **Hide and label on the definition.** A definition is shared by every sheet that shows it; what it is called and whether it
  is shown are a view's choice.
- **Per-system resolution** (a system changes what an entry's value resolves to). Rejected: resolution stays as it is
  (invariant above), and a system narrows what is shown.
- **Sheet settings on the system row.** One weapon group per system cannot give a vehicle and a character of one system
  different tables; a template per kind can.

## Consequences

- A library with one system, or none, behaves as today. A library with several gets no collision and one sheet per system.
- Stat rows grow three fields; a client that keyed on name keeps working. A client that wants a sheet reads the template.
- The prefix rule makes a slug permanent, so a system's rename is a name change only.
- The names the API reads become roles: a reserved name can be renamed, and a library's own `weight` need not be the one the
  API reads.
- Three tenant columns become template slots, with the tenant's own as the fallback.
- A repository that includes or shows a source carries that source's systems and templates with it; ADR 0431 and 0437
  apply as they do.
