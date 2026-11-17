# 0484 - The library document: `lorenzo plan`, `apply` and `export`

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C5 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md),
grown by C6 (formulas), C7 (templates) and C8 (features and grant rules). Replaces the seed file of
[ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) and [ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md).

## Context

A system is many rows that refer to one another: a system, its groups and stats, entries with parents and values, formulas on
entries, templates, features and the rules that grant them. Made one command at a time it is long and hard to review; the seed could
describe only groups, stats, categories, two formula kinds and attachments. The API has no bulk write and no export of a system.

## Decision

- **One TOML document** describes a system or the neutral vocabulary. Top level: `format = 1`, `name` (how other documents require
  it), `requires` (names of documents whose rows it refers to), and an optional `[system]`. Tables:
  - `[system]` `slug`, `name`, `root` (an entry's slug);
  - `[[group]]` `name`, `system` (true for the document's system), `role`, `priority`, `mandatory`, `position`;
  - `[[stat]]` `name`, `group`, `type` (`int`, `float`, `text`, `bool`, `enum`, `dice`), `values` (an enum's), `unit`, `role`, `min`,
    `max`, `max_hint`, `min_hint`, `resolved_hint`, `adjustable_in_play`, `pin`, `signed`, `position`;
  - `[[entry]]` `slug`, `name`, `kinds`, `parents`, `public`, `stats`, `tags`, `description`, and for a feature `repeatable`,
    `starts_inactive` and `prerequisites`;
  - `[[formula]]` `on` (an entry), `stat`, `kind` and the fields of that kind, with stats named by name ([ADR 0486](0486-formulas-from-the-command-line.md));
  - `[[template]]` with `[[template.slot]]` ([ADR 0487](0487-templates-campaigns-and-beings-from-the-command-line.md));
  - `[[grant_rule]]` with `conditions` ([ADR 0488](0488-features-and-grants-from-the-command-line.md));
  - `[[attach]]` `entry`, `parent`: a parent added to an entry another document owns (ADR 0172).
- **Identity.** A system by slug, a group and a stat by name, an entry by slug, a formula by entry and stat, a template by name, a
  grant rule by its entry and label, prerequisites as a feature's whole list. Every entry the document names has a slug.
- **`lorenzo plan FILE -t LIBRARY`** reads the library and lists what applying would create (`+`), change (`~`) and, with `--prune`,
  remove (`-`), and what it cannot do (a stat's type or group differs, which the API does not change; a name the prefix rule refuses;
  a role held by another stat). Exit 0 nothing to do, 2 changes pending, 1 something it cannot do.
- **`lorenzo apply`** writes the plan under [ADR 0482](0482-one-write-contract-for-every-cli-command.md) in the order of
  [ADR 0483](0483-the-clis-start-up-and-request-budget.md). A field the document names is set to the document's value; a field it does
  not name is left as the library has it. **It never deletes.** `--prune` removes the rows of the document's system (or, for a document
  without one, the rows it made, by name and slug) that the document no longer names, after showing them and the number of libraries
  that copied each (ADR 0386).
- **`lorenzo export SYSTEM | --neutral -t LIBRARY [-o FILE]`** writes a document: for a system, its row, its groups and their stats,
  the entries under its root, the formulas, grant rules and prerequisites on those entries and its templates; for `--neutral`, the
  groups of no system, their stats and the entries outside every system's root that carry their values. `requires` names the documents
  the export refers to that it does not contain. Applying an export to an empty library and exporting again gives the same document.
- **`--starter NAME`** stands for a document that ships with the CLI ([ADR 0491](0491-starters-replace-the-seed.md)); `lorenzo starter
  list|show NAME` lists and prints them and needs no login.
- **Validation before the API.** The document is checked against its JSON Schema (`lorenzo schema document`) and the API's rules the
  CLI can know (the slug pattern, the `<slug>_` prefix, formula limits, a role's type) before any request.
- **The command groups are edits over this planner**: `stat-group create X` is a plan of one row, so a command and a document never
  disagree on what a row means.

## Not in scope

Formula notation (RFC 0016), unit conversion, documents in another format, a merge of two documents into one.

## Consequences

- A system is a file to read, review, keep in a repository's history and apply again; editors validate it from the schema.
- The planner is the one place that knows how a row is found and written.
- Applying is additive by default, so a document applied to a library with its own additions keeps them.
