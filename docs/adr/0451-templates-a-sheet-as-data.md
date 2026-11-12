# 0451 - Templates: what a sheet shows, as data

Status: accepted, built (2026-11-12). Slice Y4 of [RFC 0052](../rfcs/0052-game-systems-in-one-library.md). Builds on
[ADR 0448](0448-a-game-system-as-a-row.md) (a system), [ADR 0450](0450-the-system-filter-on-the-stat-reads.md) (the `system`
filter), [ADR 0281](0281-sheet-settings-and-the-sheet-read.md) (the sheet read), [ADR 0037](0037-effective-stat-resolution.md)
(the prototype walk) and [ADR 0040](0040-item-instance-read-visibility.md) (what a caller reaches). It takes up what
[RFC 0018](../rfcs/0018-entity-template.md) proposed and [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) closed until a
case parents cannot cover appeared: a library with several game systems needs one view per system. A template reads and never
writes, and resolution does not change.

## Context

A sheet has to say which of an entry's stat groups and notes it shows, in what order and under which names. Today that is two
settings of the library (`being_stat_group_id`, `weapon_stat_group_id`) and the ability type, which hold one choice for the whole
library. A definition cannot carry the choice either: it stays in one group (ADR 0448), and a stat that two systems show is the
templates' business, not the definition's.

## Decision

- **A template** is `template(id, tenant_id, name, system_id, required_kind, required_ancestor_entry_id)`: a name unique in the
  library, an optional game system, and a filter of two optional parts applied together: the entry has the kind
  (`required_kind`, one of the entry kinds) and has the ancestor on its prototype walk (`required_ancestor_entry_id`, an entry
  strictly above it, as ADR 0037's walk reaches). `system_id` names the system for a campaign that picks templates by system and is
  not part of the filter. A template whose ancestor entry is deleted goes with it, since without it the filter would match every
  entry.
- **Slots** are the body: `template_slot(position, kind, label, ...)`, unique by `(template, position)`, of four kinds:
  `stats` (a stat group, with `exclude` for stats of it to leave out, or an ordered list of stats with a label each), `information`
  (the entry's notes of an information type), `held` (the things the entry holds directly, a column for each stat of a group or
  list, in `name` order or `prototype` order, the name of the thing's prototype first) and `tags` (the `bool` stats that are
  true, of a group or of any). A label, a hidden stat and the order are the slot's, not the definition's. The lists and the
  exclusions are `template_slot_stat` and `template_slot_exclusion`.
- **Authoring** is the vocabulary's tier, as the systems' (ADR 0448): any member who may author it makes and edits a template, a
  participant reads, an administrator deletes. `POST /tenants/{t}/templates`, `GET` (a page, by name, with `system`: the templates
  of no system and of that one), `GET /{id}`, `PUT /{id}` and `DELETE /{id}`. A `PUT` replaces the whole template, its slots
  included; a name another template has is a 409, and a system, ancestor entry, stat group or stat that is not the library's, a
  slot that does not fit its kind, a stat listed twice or an exclusion outside the slot's group is a 422.
- **A template is not deleted from under what it names**: a stat group or a stat a slot shows or lists is a 409 (`still in use:
  1 template slot(s) ...`), as is a system a template belongs to.
- **Reading.** `GET /tenants/{t}/entities/{e}/matching-templates` lists the templates whose filter matches the entry, by name,
  with `system` as above, and `GET /tenants/{t}/entities/{e}/templates/{id}` assembles the view: an ordered array, one element
  per slot, with the resolved values, labels and units. A template that is not for the entry is a 409
  (`template-does-not-match`): the API does not pick another, and nothing is chosen when two match.
- **What the caller may read is all it gets.** Stat values are the entry's own read's (formulas evaluated, inherited values with
  their source); notes go through the information visibility check; held things through ADR 0040's reach, as the datasheet's
  weapons do. A thing, note or stat the caller may not read is not in the answer, and nothing is filled in its place.
- **The sheet settings are not touched.** A library with no template draws from them as ever; Y5 reads them through templates.

## Design

Four tenant tables, each with `tenant_id`, composite same-tenant keys (ADR 0117), `FORCE ROW LEVEL SECURITY` and the
`repository_read` policy, as repository content (ADR 0118). Their lines in the copyable-table registry say "not copied yet"
(Y6): a copy writes no template until then. A slot goes with its template and its lists with the slot; the keys to a stat group, a
stat and a system do not clear anything (the routes refuse the delete first). The view is built from what the entry read already
loads (`_stats_out`) plus the held query of the sheet, so a template costs a statement for its definitions, one for each
information slot and two for each held slot, never one for a stat.

## Validation and delivery

A test for each: the routes (make, read, list with a system, replace, delete), a slot that does not fit its kind (eleven shapes), what
must resolve (another library's system, group and system, a ghost, a stat twice, an exclusion outside its group, a duplicate name),
the filter by kind and ancestor and system (and the ancestor being strictly above), the view of every kind of slot, the held order,
an entry the template is not for, a note the caller may not read, the deletes that are refused, the ancestor that takes the
template along, and another library's templates. The OpenAPI change is five routes and two read routes under entries; the CLI models
and `packages/api-client` are regenerated.

## Consequences

- A library with two systems shows an entry for each of them without a client that knows either, and a stat that two systems show
  is listed by both templates.
- A template is content a repository can hold; Y6 carries it, re-pointing the group, stat and entry ids as a formula's inputs are.
- Writing a value through a template stays out, as in RFC 0018: every field is already writable where it lives.
