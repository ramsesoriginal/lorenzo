# 0492 - The repository commands show systems, templates and warnings

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C11 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Amends [ADR 0159](0159-lorenzo-repo-commands.md), [ADR 0169](0169-seed-list-and-repo-contents.md) (`repo contents`) and
[ADR 0174](0174-the-cli-shows-attachments.md); builds on [ADR 0453](0453-repositories-carry-systems-and-templates.md) and [ADR 0469](0469-updates-track-game-systems-and-templates.md).

## Context

A copy plan and a copy count systems and templates, list what they drop (grant rules and prerequisites among them), report `warnings`
for a merged stat whose unit or bounds differ, and take `strict_units`. Updates offer systems and templates as rows. A role and a
template can be name clashes. The CLI prints none of this beyond `--json`, and `repo contents` reports seed layers.

## Decision

- **`repo copy-plan` and `copy`** say a step's systems and templates with its other counts, list what is left out by kind with the
  reason, and print each warning as "`price`: here in cp, incoming in gp; merged, yours kept". `--strict-units` passes `strict_units`,
  which turns those merges into name clashes to answer.
- **Name clashes** of a role and a template are listed and answered like the others (`--on-collision`, `--choices`).
- **`repo updates`** lists system and template rows with the fields that changed (`name`, `root`; `name`, `system`, `kind`, `ancestor`,
  `slots`), a group's `system` change, and what is not applied and why.
- **`repo contents`** says what a repository holds: its systems (slug, name, root), templates, stat groups and stats by system and
  neutral, roles and who holds them, entries, features, grant rules, attachments, and what it is built on. The per-layer table goes.

## Consequences

- What a copy or an update does to a library's systems and templates is said before it happens, in words.
- `repo contents` describes a repository by what the API knows, not by a file shipped with the CLI.
