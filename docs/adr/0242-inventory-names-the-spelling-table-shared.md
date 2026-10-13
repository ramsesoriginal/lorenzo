# 0242 - The spelling table, shared: `packages/inventory-names`

Status: accepted, decided with the maintainer on 2026-10-10.

Follows [ADR 0193](0193-lorenzo-inventory-import-and-export.md) (the table of other spellings the importer tries) and [ADR 0241](0241-inventory-web-the-unsorted-view.md) (the Unsorted view, which left it out). Builds on [ADR 0122](0122-api-client-package.md) for the pattern of one source with a drift check.

## Context

`lorenzo inventory import` tries a name written another way when it matches no item: a table of whole names (`"armbrustbolzen"` and the titles it may be called) and of words, with a bracket, a length and a plural taken off first. The table is data, grows as GMs find gaps, and is what keeps "Seil" from becoming an unsorted item. The Unsorted view faces the same names after the fact and ranks catalog titles only by how alike the letters are, so "Seil" does not suggest "Rope, hempen (50 feet)".

Two programs, in two languages, should read one table. The CLI is installed with `uv tool install …#subdirectory=apps/cli`, so it can only ship what is inside `apps/cli`: it cannot depend on a path under `packages/`.

## Decision

### A package of data, with a small reader for each language

`packages/inventory-names` holds:

- **`preprocess.toml`**, the table, moved here as the one place it is edited, with its comments.
- **`vectors.json`**, a list of names and the alternatives each must give, in order: the contract between the two readers.
- **A TypeScript reader** (`alternatives(name, table)`, `parseTable`, `builtinTable`): the same steps as `lorenzo_cli/inventory/preprocess.py`, about sixty lines, with the TOML read at build time.

The Python reader stays in `apps/cli`.

### The CLI keeps a copy, and CI says when it is stale

`apps/cli/src/lorenzo_cli/inventory/preprocess.toml` stays where it is, so the installed tool still carries its table. It is now a copy: `mise run //apps/cli:sync-names` writes it from the package, and a CLI test fails if the two differ. This is the pattern of the generated API client ([ADR 0122](0122-api-client-package.md)): one source, a committed copy, and a check, not a second place to edit. `.github/ci-graph.toml` makes `apps/cli` depend on the package, so a change to the table runs the CLI's tests.

### Both readers run the same vectors

The TypeScript tests and a CLI test both read `vectors.json`, so a change to either algorithm or to the table that makes them disagree fails on the side that moved.

### In the Unsorted view

A group's name is expanded through the table; a catalog title that equals one of the alternatives (compared as [ADR 0241](0241-inventory-web-the-unsorted-view.md) compares names) ranks as an exact match, ahead of the fuzzy ones. Nothing else changes: the GM still picks.

## Not in scope

- **A user's own table** (`--preprocess FILE`) stays a CLI option. The view uses the built-in table.
- **Anything the table does not say.** Nothing is guessed, in either tool.
- **The table in the library as content**, so that a library naming things otherwise could carry its own, is a larger design and would be its own RFC.

## Consequences

- A gap found at the table, in the CLI or in the Unsorted view, is fixed in one file, once, and both tools get it.
- The algorithm exists twice, 60 lines each, held together by shared test vectors rather than by sharing code.
- Editing the table means copying it to the CLI (`sync-names`) before committing; forgetting is caught by a test, not by a user.
