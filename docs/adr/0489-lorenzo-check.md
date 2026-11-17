# 0489 - `lorenzo check`

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C9 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
The client of [RFC 0055](../rfcs/0055-vocabulary-check.md) that RFC 0055 left to its own work; builds on [ADR 0458](0458-the-vocabulary-check-route-and-its-first-findings.md)
to [ADR 0461](0461-warnings-on-the-writes-of-a-stat-and-of-a-formula.md).

## Context

`GET /tenants/{t}/vocabulary-check` returns findings with a code, a severity, an entry, a stat, a message and details, filtered by code,
entry, parent (recursive), kind and stat; `tie` needs an entry. Library findings come on the first page with no entry filter, and the
totals count entries, not findings. Writes answer with findings when asked (`?warnings=true`). The check refuses nothing.

## Decision

- **`lorenzo check -t LIBRARY`** reads every page and prints the findings grouped by entry (library findings first), each as its
  severity's symbol and word, its code and the API's message, then a count by severity: "3 warnings, 1 note in 2 entries."
- **Filters**: `--code` (repeated), `--entry`, `--parent` (with `--recursive`, the default, or `--direct`), `--kind`, `--stat`, and
  `--severity warning|info` (the CLI's filter until the API has one).
- **Exit codes for a script and CI**: `--fail-on warning` exits 1 when a warning is found, `--fail-on info` when anything is; without it
  the check exits 0 whatever it finds. `--json` prints the findings and the counts.
- **Only when asked.** `apply`, `import mpmb apply` and `repo copy` do not run it; when they wrote something they end with one line
  naming `lorenzo check -t LIBRARY`. `--warnings` on `formula set`, `stat-definition` writes of a value and tag writes passes
  `?warnings=true` and prints what comes back the same way.
- Severity is said in words: the API's `warning` is "warning", `info` is "note".

## Consequences

- A library's author can run the check after any change, and CI can gate a repository on it, without the API refusing anything.
- A fresh library is not met with a page of findings it did not ask for.
