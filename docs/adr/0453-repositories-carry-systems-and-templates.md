# 0453 - Repositories carry game systems and templates

Status: accepted, built (2026-11-12). Slice Y6, the last, of [RFC 0052](../rfcs/0052-game-systems-in-one-library.md). Builds on
[ADR 0448](0448-a-game-system-as-a-row.md) (a system), [ADR 0449](0449-roles-the-api-reads-a-stat-by-what-it-is-for.md) (roles, already in
the copy and the document), [ADR 0451](0451-templates-a-sheet-as-data.md) (templates), [ADR 0119](0119-copying-a-repository-into-a-tenant.md) (the
copy), [ADR 0214](0214-the-release-document.md) (the release document) and [ADR 0292](0292-discover-the-listing-and-the-storefront.md) (the listing).

## Context

A repository exists so a library can take a vocabulary and its content from someone else. With systems and templates a
vocabulary repository for one game system should bring that system, its groups, its stats and the sheets that show them, and
must not exclude another system a library already holds.

## Decision

- **A repository's systems and templates are content.** `Content` carries `systems` (slug, name, root entry), the `system` of each
  stat group and `templates` with their slots; the release document is format 42 with them, and a document of format 41 reads as
  none, every group neutral.
- **A copy joins a system by slug.** A system the library has keeps its name and root, and a group of the repository that
  belongs to it joins it; a system the library lacks is made, with its root pointing at the library's copy of the root entry
  (none when that entry was not copied). The registry puts `system` after `entity` (a root is an entry) and before the stat groups
  that belong to it.
- **A copy re-points a template.** Its group, stats and ancestor entry are the library's copies (or the library's own stats that
  the copy merged into); a stat the merge made one is listed once. A template is left out and reported in the step's `dropped`
  (kind `template`) when the library has one of its name, or when its ancestor entry, a group it shows or a stat it lists was not
  copied: a template that shows less than it says is a wrong one. A name that clashes has no choice to make, since two templates
  of one name do not merge.
- **Steps count them**: `systems` (made, not joined) and `templates` on each step of a plan and of a copy.
- **A purge takes the templates that show what it removes**: a template of the library that shows a purged group or stat, or is
  for a purged entry, goes with them (counted as `template` in `also_removed`), since its slots would point at nothing.
- **A merge that keeps the library's unit is said.** `copy-plan` and the copy answer `warnings`: each stat merged into the
  library's own whose unit or bounds differ from the repository's, with both. `strict_units: true` on the copy, or as a query
  parameter on `copy-plan`, takes `merge` out of the choices for such a stat (for a name clash and for a role), so the copy asks
  until each is resolved by renaming or leaving it out; a merge of equal scales is no warning. Unit conversion is not done.
- **A profile and Discover know the systems.** `repository_profile.systems` holds the slugs of the systems the stat groups of the
  current release belong to, written with the other listing facts; `systems` is on the profile and the listing item, and
  Discover's `system` filter and facet match the Owner's own label and these slugs, a repository once.

## Not in scope

**Updates.** The update engine tracks stat groups, stats and entries through copy links and snapshots (ADR 0121). A system or a
template is not tracked: a copy joins and copies once, and a later release that changes a system, a template or a group's system
is not offered as an update; a library that wants it copies afresh (`again`). Giving them links is a slice of its own.

## Design

`system` and `template` (with its slots) are copied tables in the registry, planned by `_Planner` before the groups and after the
entries, written by `write_rows` in registry order. `Content` holds them and `load_content` reads them; the planner needs no new
link table, since a system is found by its slug and a template by its name. The profile's `systems` is a column, filled in
`set_listing_facts`. The scale warnings are the planner's, from the scale (unit, minimum, maximum) it reads of every library
definition once.

## Validation and delivery

A test for each: the format 42 round trip and the format 41 reader; a copy that brings the system, its root, the group's system
and the template with its slots re-pointed (and the template read through the entry at once); a system the library has joined by
slug, keeping its name; a template of a taken name left out and said; a template whose group was skipped left out; a merge that
differs in unit and bounds reported; the same unit not reported; `strict_units` on the plan and the copy; a published release
listing its systems on the profile; Discover's filter and facet by label and slug. The existing registry, seed and purge tests
cover the order and the counts. The OpenAPI change is additions (`warnings`, `systems`, `templates`, `strict_units`); the CLI
models and `packages/api-client` are regenerated.

## Consequences

- A vocabulary repository for a game system brings its system, groups, stats and sheets, and two systems never exclude each other.
- A library that merges a stat of another unit is told, or asks to be.
- Systems and templates of a repository are as they were when copied until a library copies afresh; updating them is later work.
