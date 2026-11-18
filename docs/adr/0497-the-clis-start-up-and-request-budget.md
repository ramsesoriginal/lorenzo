# 0497 - The CLI's start-up and request budget

Status: accepted (2026-11-17), decided with the maintainer, built (2026-11-18). Slices C1 (start-up) and C5 (requests) of
[RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).

_Originally numbered 0483; renumbered before merge - the Maps ADRs 0481, 0482, 0490 and 0491 reached `main` first, so the RFC 0057 block moved as a whole to 0495-0507. Same precedent as ADR 0050/0054/0068/0069/0087._

## Context

Measured on 2026-11-16 in an ext4 clone, warm, median of 15: `lorenzo --version` 469 ms, `--help` 492 ms, a completion 468 ms,
`import lorenzo_cli.main` 438 ms with 521 modules, of which the generated `client/models.py` is 174 ms (`client/ops.py` imports every
model at its top), `httpx` 49 ms and the calendar engine 40 ms; mini-racer loads for every command. `main.py` is 2,441 lines and
imports the importer, inventory, seed, calendar and evaluation code at its top. Requests run one after another: `seed` makes 165 in
about 6 s, `apply` of 14 items 84, and every command spends two on finding the tenant.

## Decision

- **Command groups load when named.** The root is a click group with lazy subcommands: `main.py` names each group and the module it
  lives in, and imports it only when it is run or its help is shown. `--version` and completion import neither a group nor the client.
- **Models load on use.** An operation names its models by name; `client/ops.py` resolves them from `client/models.py` the first time
  the operation is called, so a command pays for the models only when it talks to the API.
- **`main.py` is split** by command group, one module each; the shared runtime, client and error reporting live in their own modules.
- **Budget, warm**: `--version`, `--help` and a completion under 150 ms; a command that makes one request under 250 ms plus the
  network. A test imports the root and fails if a module of a command group, the generated models, the calendar engine or
  mini-racer is loaded; it reports the time, which CI keeps as a record but does not fail on.
- **A cache for one run.** The stat groups, stat definitions, systems and the tenant are read once per run and kept; a write updates
  the cache. The tenant is found by one request where a slug is given (`GET /tenants?slug=` when the API has it, the list otherwise).
- **Bounded concurrency.** A plan's writes are ordered by what they depend on (system, group, stat, entry, parents, formulas,
  templates, features and rules); within one level up to four run at once. Output and `--json` list them in the plan's order, whatever
  order they finished in. A failure stops the levels after it; what was written stays, as ADR 0496 says.
- Where the API already does a batch (the bulk effective-stat read, repository copy, grants apply) the CLI makes that one request.

## Consequences

- A typo, `--help` or a Tab press is answered at once; heavy code loads for the command that needs it.
- Applying a large document is quicker but still one request per row; a bulk write is an API issue (RFC 0057).
- A new command group is one line in the root and a module of its own; the start-up test catches an import at the top that leaks.
