# 0495 - The CLI's output and machine contract

Status: accepted (2026-11-17), decided with the maintainer, built (2026-11-18). Slice C2 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Generalises [ADR 0232](0232-inventory-import-any-being-replace-and-progress.md)'s progress bar and keeps [ADR 0156](0156-json-on-apply-and-pack-give.md)'s one
document on stdout.

_Originally numbered 0481; renumbered before merge - the Maps ADRs 0481, 0482, 0490 and 0491 reached `main` first, so the RFC 0057 block moved as a whole to 0495-0507. Same precedent as ADR 0050/0054/0068/0069/0087._

## Context

Two commands show progress (calendar import, inventory import), each with its own rich setup; the rest print a plan or a result at
the end, so `seed` waits about 6 s in silence. Errors are one red line on stderr even with `--json`, so a script gets an empty stdout
and prose to parse. Colour is the only signal in several places, and `NO_COLOR` is honoured only through rich's defaults.

## Decision

- **One console module**, `lorenzo_cli.console`, through which every command prints. It owns the two consoles (stdout for results,
  stderr for the rest), the table and tree styles, the status words and symbols, and progress.
- **Progress.** `console.waiting(text)` shows a spinner with elapsed time for a wait of unknown length; `console.counting(text, total)`
  shows a bar with "N of M" for a batch. Both draw on stderr, and only when stderr is a terminal and none of `NO_COLOR`, `--quiet`,
  `--no-progress` or `--json` applies; otherwise a waiting step prints one plain line to stderr, and `--quiet` prints nothing.
- **Status is words and symbols as well as colour**: `✓ done`, `+ create`, `~ change`, `- remove`, `⚠ warning`, `✗ refused`,
  `· note`. With `NO_COLOR` the symbols and words stay.
- **Global options** `--quiet` (results only; notices and progress go) and `--no-progress` (no animation). The "Using the official
  Lorenzo at ..." line of ADR 0164 stays under `--quiet`: it is about where a write goes.
- **`--json`**: every document is an object with `"format": 1` beside what it reports; a list is under a key, never the top level. With
  `--json` a failure prints one object `{"format": 1, "error": {"status", "code", "message", "details"}}` on stdout, the API's problem
  document when there is one, and exits 1. stderr may still carry a line for a person.
- **`lorenzo schema`** prints, as JSON Schema, the library document (ADR 0498) and the `--json` output of a named command, so a script
  or an agent needs no README.
- Text follows the identity's terminology (section 14): library, stat, formula, entry, check first; `tenant` stays in names (ADR 0194).

## Consequences

- Every command waits visibly, and a pipe or `--json` gets no animation and no stray bytes.
- A script reads one object on success and on failure; changing a `--json` shape raises its `format`.
- Each command's output goes through one place, so a style change is one change.
