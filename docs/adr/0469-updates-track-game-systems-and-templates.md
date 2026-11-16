# 0469 - Updates track game systems and templates

Status: accepted, built (2026-11-16). Slice G3, the last, of the follow-ups tracked in #1229. Takes up what
[ADR 0453](0453-repositories-carry-systems-and-templates.md) left out ("Updates... Giving them links is a slice of its own") and
[RFC 0052](../rfcs/0052-game-systems-in-one-library.md) section 7. Builds on [ADR 0121](0121-repository-updates-and-re-sync.md) (the
update engine), [ADR 0119](0119-copying-a-repository-into-a-tenant.md) (copy links) and [ADR 0214](0214-the-release-document.md).

## Context

The update engine compares three versions of each copied row (the snapshot taken at the copy, the repository's row now, the
library's copy now) through the copy links of the entries, stat groups and stat definitions. A game system and a template had no
links, so a later release that renamed a system, changed a template's slots or moved a group to another system was not offered; a
library that wanted it copied afresh.

## Decision

- **Two more copy links**, `repository_copy_link_system` and `repository_copy_link_template`, with the columns of the others (the
  library's id, the origin id, a snapshot, and for a system a `mode`). A copy writes one for each system and template it brings:
  a system it made is `copied`, one the library already had (joined by slug) is `merged` and is never offered for update, as a
  merged stat group is not. A template left out (its name taken, or a group or stat it shows not copied) has no link.
- **What a snapshot records.** A system: its name and its root entry by origin. A template: its name, the slug of its system, its
  kind, its ancestor entry by origin, and its slots in order, each with its kind, label, information type, held order, its group,
  its stats with their labels and its exclusions by origin. A stat group's snapshot gains the slug of its system when it has one
  (left out when it has none, so a group of no system is as it was); the release digest hashes it without, so no release looks
  edited.
- **What an update offers**, as for the other rows: the fields upstream changed since the base (`name` and `root` of a system; `name`,
  `system`, `kind`, `ancestor` and `slots` of a template; `system` of a stat group), each clean while the library's copy still has the
  base, a conflict once it changed too, named in `keep_local` or `take_upstream`; a row the repository no longer has as `removed`
  (a `detach` drops its link and keeps the row); a row it added as `added`, which an `add` copies as a first copy would.
- **How it is applied.** A system's name and root are written (a root that was not copied here is not applied, and said). A template's
  fields are written, its slots replaced as one field with every group and stat re-pointed to the library's copy (a slot that shows
  what was not copied is not applied, and said), its name checked against the library's. A group's `system` is found by slug in the
  library; a slug the library lacks is not applied, and said.
- **What an `add` asks.** A system whose slug the library has is joined, with nothing to choose, and linked `merged`. A template whose name
  the library has is a collision with `rename` and `skip`, answered in the `add`'s resolution (the first copy still leaves it out and
  says so, as ADR 0453 does); `skip` leaves it offered.
- **Order.** Additions are made systems, groups, stats, entries, templates; changes are applied after the additions.
- **The release document is format 49**: its `links` have `system` and `template` (empty in a document of format 48 or older). The copy
  links of a repository now say which of its systems and templates are its own, so the release of a repository that copied another
  holds only its own, as it already does for its groups and stats; a repository that includes another (ADR 0431) takes them as its
  own with the rest.
- **No digest state.** A system and a template are not among the rows a release hashes, so `state` is null on them (the other rows
  say whether the repository's row is what its latest release saw).
- **Copies made before this** have no links for them: the repository's system and templates are offered as additions, the system
  joined by slug and the templates as collisions with the library's own, to skip or rename. Nothing changes until they are asked for.

## Design

`Links` has `system` and `template`; `load_links` reads them; `system_snapshot` and `template_snapshot` sit with `stat_group_snapshot`.
The planner links what it makes and honours `only` for both kinds, so an update's `add` is a copy of those rows; `_plan_templates`
takes the filter and, in an update, asks instead of leaving a template out. `_Applier` has `_system` and `_template`, and `_stat_group`
handles `system`. The registry has the two link tables after the rows they point to, and the derived lists follow it.

## Validation and delivery

Tests: a copy links both (modes, snapshots, the contributions list); a name and root change of a system and a name, ancestor and slot
change of a template offered clean and applied, with no state; a conflict named, a group following its system into one added in the
same call, and a link written for what was added; a template added upstream with a taken name asked about, renamed and skipped, and
one removed detached; a copy without links offered what it has, the system joined `merged`, the template skipped; the registry lists.
The OpenAPI change is `system` and `template` as values of a row's `kind` and `template` of a collision's (responses that grew,
accepted in `openapi-breaking-accepted.txt`); the CLI models and `packages/api-client` are regenerated.

## Not in scope

Merging a template (two of one name do not merge), updating the roles or the kinds a template shows, a digest of systems and templates
(a release's breaking notes name none of them), and libraries counting how many hold a copy of a system or a template.

## Consequences

- A release that renames a system, changes a template or moves a group to another system reaches the libraries that copied it, as a
  change to a stat group does.
- A library keeps its own system and its own template of a name; an update never makes two.
- A library that copied before this sees the repository's system and templates once, as additions, and answers them.
