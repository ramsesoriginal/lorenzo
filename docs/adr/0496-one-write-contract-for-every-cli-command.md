# 0496 - One write contract for every CLI command

Status: accepted (2026-11-17), decided with the maintainer, built (2026-11-18). Slice C2 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Generalises [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md)'s non-interactive contract to every writing command.

_Originally numbered 0482; renumbered before merge - the Maps ADRs 0481, 0482, 0490 and 0491 reached `main` first, so the RFC 0057 block moved as a whole to 0495-0507. Same precedent as ADR 0050/0054/0068/0069/0087._

## Context

Writing commands disagree: `seed` asks at a terminal, `repo copy` writes unless `--dry-run`, `apply` needs `--yes`, `tenant delete`
asks for the slug, and `stat-group create` writes at once. A script cannot assume one rule, and a person cannot either.

## Decision

Every command that writes follows one rule:

1. It works out what it would do and shows it (on stdout as a plan, or in `--json` as the plan document).
2. At a terminal it asks once, default no. `--yes` skips the question.
3. `--dry-run` never writes: where the API has a dry run it uses it (copy, updates, grants apply), elsewhere it stops after the plan.
4. With no terminal and no `--yes` it writes nothing and exits 2, saying so on stderr. `--json` never asks, so it needs `--yes` to write.
5. Exit codes: 0 done or nothing to do; 2 something to do or decide that was not done; 1 refused or failed.
6. A deletion that cannot be undone (`tenant delete`) still asks for the slug at a terminal; `--yes` skips that too.

A single create or edit (`stat-group create`) shows one line of what it will write and follows the same rule; at a terminal the
question is the default-yes form only where the plan is that one row, so an edit stays one keystroke.

What was written before a failure stays written, and the output says what was and was not; running the command again finds what was
made, by slug or name. ADR 0164's line is printed once, before the plan, when the official Lorenzo is the default.

## Consequences

- `lorenzo X --dry-run` and `lorenzo X` without `--yes` in a script are both safe, and both exit 2 when there is something to do.
- `repo copy` and `repo updates --apply` no longer write without `--yes` in a script; the README and the end-to-end tests say so.
- A command added later follows the rule by using the shared helper, not by its own flags.
