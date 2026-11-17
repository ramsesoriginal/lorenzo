# 0485 - Commands for systems and the stat vocabulary

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C5 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Extends [ADR 0295](0295-cli-vocabulary-sheet-settings-and-reads.md).

## Context

`stat-group` and `stat-definition` have `list`, `create` and `edit` with display fields and hints. They have no system, role or bounds;
`--type dice` works only because the option uses the generated enum. Lists show a name and an id. There is no command for a system.

## Decision

- **`lorenzo system list|show|create|edit|delete`**: `create SLUG NAME [--root ENTRY]`, `edit SYSTEM [--name N] [--root E | --clear-root]`
  (a slug cannot change while a group uses it, and the CLI says so before asking), `delete` (refused by the API while a group, template
  or campaign uses it, and the CLI names them). `show` lists the system's groups, stats, templates and the campaigns that name it.
- **`stat-group`** gains `show` and `delete`, and `--system SLUG` / `--no-system` and `--role ROLE` / `--clear-role` on `create` and
  `edit`.
- **`stat-definition`** gains `show` and `delete`, `--role` / `--clear-role`, `--min` / `--max` / `--clear-min` / `--clear-max` (for
  `int` and `float`), and the `dice` type (no unit). A name that breaks its group's `<slug>_` prefix is refused before the request, with
  the name it would need.
- **Lists** are tables: a group's name, system, role, priority and number of stats; a stat's name, group, system, type, unit, role and
  bounds. `--system SLUG` keeps the neutral rows and that system's, `--neutral` only the neutral ones, `--group` one group; the filter is
  the CLI's until the API has one (an API issue).
- References are an id, a slug (a system) or an exact name ignoring case; an ambiguous name is refused with the candidates (ADR 0190).
- Every write is a plan of one row through the document planner ([ADR 0484](0484-the-library-document.md)) and the write contract
  ([ADR 0482](0482-one-write-contract-for-every-cli-command.md)).
- `tenant sheet-settings` gains `--controllers-award-features` / `--no-controllers-award-features` (ADR 0467).

## Consequences

- Every field the API has for a group, a stat and a system can be set from the command line, one row at a time or by document.
- A library's vocabulary reads as a table that says which system each row belongs to and which role it holds.

## As built (slice C5)

`system create` is a plan of one row through the planner. The stat group and stat writes call the API directly, because an edit
can clear a field and a document cannot say "none"; they run the planner's own checks first (the `<slug>_` prefix, a role only on
a row of no system, bounds only on a number, no unit on dice).
