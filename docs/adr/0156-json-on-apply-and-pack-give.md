# 0156 - `--json` on `apply` and `pack give`

Status: accepted

Follow-up to [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) and [ADR 0150](0150-lorenzo-pack-give-on-the-api.md). Part of the set decided together on 2026-10-03 ([ADR 0153](0153-lorenzo-version.md)).

## Context

[RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) R6 made the importer scriptable: `plan` emits deterministic JSON and `apply --yes` never prompts. But only the front half is machine-readable. `plan --json`, `seed --json` and `tenant show --json` print JSON; `apply` and `pack give`, the two commands that actually write, print a sentence and a tree. A script that ran `apply` had to parse prose, or run `plan --json` first and trust that `apply` then did the same.

## Decision

`--json` on both, with one rule for what it means: **stdout carries exactly one JSON document and nothing else.** Everything meant for a person goes to stderr, where `apply`'s progress lines and the review-queue notice already go.

### `pack give --json`

Prints the API's answer ([ADR 0149](0149-giving-a-pack-from-the-api.md)'s `PackGivenOut`) as it came: what was made, as a tree. `--dry-run` prints the same shape for what would be made. The "Gave 7 item(s)." line is dropped.

### `apply --json`

```json
{
  "plan": { "...": "exactly what `plan --json` prints" },
  "applied": { "created": 3, "completed": 0, "reparented": 0, "categories": 1, "definitions": 0 },
  "failures": [],
  "unresolved": false
}
```

- **`plan`** is `plan --json`'s document, so a script reads one shape for both.
- **`applied`** is `null` when nothing was written: nothing was pending, the plan had problems, or the write wasn't allowed (below).
- **`failures`** lists what failed during the write, as `apply` already reports it on stderr.
- **`unresolved`** is true when the plan held something back for review, as the exit code already says.
- **Exit codes don't change:** 0 done, 1 something unresolved or failed.

### It never asks

`--json` is for a script, and a confirmation prompt would write into the document it is meant to keep clean. So with `--json`, `apply` writes only when `--yes` is given, exactly as it does when nothing can be asked. Without `--yes`, and with something pending, it prints the document with `applied: null`, says on stderr to run again with `--yes`, and exits 1. That makes `apply --json` without `--yes` a `plan --json` that also exits 1, which is the same failure a non-interactive `apply` already gives.

## Not in scope

- **`--json` on `login`, `logout` and `inspect`.** `inspect` has its own `--json` already, and the other two have nothing to report.
- **Streaming progress as JSON lines.** Progress stays human text on stderr.

## Consequences

- A script can create, apply and give without parsing prose, and chain on `unresolved` and `failures`.
- `apply`'s document and `plan`'s share one shape, so a change to the plan's JSON changes both. That is deliberate.
