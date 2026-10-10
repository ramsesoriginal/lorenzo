# 0243 - `lorenzo-converters`: a package of simple converters, and the spreadsheet one

Status: accepted, decided with the maintainer on 2026-10-10.

Slice 6 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) ("Converters: where they live is decided when the first one is"). The first converter, [`lorenzo-beyond`](https://github.com/ramsesoriginal/lorenzo-beyond), is a tool of its own for a source with a live API. This ADR is for the other kind: small, mostly one-off conversions of files players already have. Builds on [ADR 0191](0191-inventory-file-format-v1.md) and [ADR 0226](0226-lorenzoledger.md) (the format is the contract).

## Context

Players keep their inventory in a spreadsheet, a LaTeX list, a text file. The format exists so that none of those has to be read by the CLI ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md): "Reading each source directly in the CLI. Many parsers to keep, each guessing"), but until a converter exists each player is writing the ledger by hand. Most of these sources are used by one table, or one person, and do not merit a repository, a name on PyPI and a release process each.

The first real one is a spreadsheet of two Excel tables, **Items** (name, count, weight of one, estimated value as free text, container, kind, description) and **Container** (name, where it is kept), in German headers, with containers that are also item rows, names that differ only by case, and typos in kinds.

## Decision

### One package for the simple ones

`packages/converters` (Python, `lorenzo-converters`, command **`lorenzo-convert`**), installed from the repository like the CLI (`uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=packages/converters"`). One subcommand per source; the first is `sheet`. A converter reads a file and writes a ledger, and never talks to the API: the output goes to `lorenzo inventory import` like any hand-written ledger, with its `--dry-run`. It is not the CLI's, so the CLI does not grow a parser per source. A source with a live API, or enough weight to want its own release (D&D Beyond), stays a project of its own.

### `lorenzo-convert sheet FILE --owner NAME`

Reads an `.xlsx` (the Items table, and the Container table if there is one) or a `.csv` (Items only), and writes the ledger to standard output or `-o FILE`.

- **Columns are found by their headers**, compared without case, in German or English (`Anzahl`/`Count`, `Gewicht`/`Weight`, `gesch. Wert`/`Value`, `Container`, `Art`/`Kind`, `Beschreibung`/`Description`, and `Ort`/`Place` on the Container table). A required column that is missing stops with the headers that were found. Everything the format has a place for is kept: name, count, weight (of one), value (as written), kind (as written, typos included: it is only a hint), and the description as `note:`, or as a `>` block when it has several lines.
- **Containers are built from the Container column.** Names are matched without case or surrounding space, so `backpack` and `Backpack` are one bag. A container that is also a row of the Items table is that row (its own count, weight, value, and where *it* is); one that is not gets a line of its own, and a name only used as a container is made, with a warning. Nesting follows the column. A loop is cut at the first repeat, with a warning.
- **`holding` is Equipped** (or the name given with `--equipped`; the format's other names for it work too): what is in it is at the top of `## Equipped`. A row with no container is in `## Not carried`.
- **Places.** A container whose place on the Container table is not **home** is kept elsewhere: it goes at the top of `## Not carried` with `place:`. Home is `--home PLACE`; without it, the most common place is taken as home, and the output says so.
- **Formulas are not read.** A weight or total that is a formula, or a cell that is empty, is left out of the line, with no guess; the total weight column is never used, since Lorenzo works it out.
- **A stack at the top level.** The format wants a stack inside something ([ADR 0191](0191-inventory-file-format-v1.md)), and a sheet often has `3 x Dagger` in the hand. Up to ten, it is written as that many lines, and the warning says so; more is left as it is, with a warning to put it in a container, since a container is not invented. A container with a count above one is warned about too: the importer wants it written once for each.
- **What the importer limits** (1024 lines, six levels, a thousand of one thing, [ADR 0191](0191-inventory-file-format-v1.md)) is checked, and a file over them is warned about before it is imported rather than refused by the importer.
- Warnings go to standard error; the exit code is 0 if a ledger was written.

### Tested with made-up data, held to the CLI's parser

The fixtures are invented inventories with the sheet's quirks (a nested bag, a bag spelled two ways, a container kept elsewhere, a formula, a missing weight, a multi-line description), never a real player's rows. The ledgers the tests expect are kept as files in the package (`tests/golden/`), and `apps/cli` has a test that parses every one of them with its own parser, so a converter cannot write what the importer reads differently ([ADR 0242](0242-inventory-names-the-spelling-table-shared.md) does the same with its table). `.github/ci-graph.toml` makes `apps/cli` depend on the package for that reason.

## Not in scope

- **LaTeX lists and other sources.** Each is a subcommand when someone has one; the first (CSV and Excel) shows the shape.
- **Matching to the library's items.** The importer does that ([ADR 0193](0193-lorenzo-inventory-import-and-export.md), with the spelling table of [ADR 0242](0242-inventory-names-the-spelling-table-shared.md)); a converter only writes what the source says.
- **Reading values and weights as numbers or in other units.** The ledger's `value` is free text, and weight is taken as pounds, as the sheet had it.
- **A web upload** for converting a file: this is a command-line tool.

## Consequences

- A player with a spreadsheet gets a ledger in one command, reviews it as text, and imports it with `--dry-run` first.
- A new simple source is a subcommand and a golden file, not a repository.
- The package pulls in `openpyxl` and is installed on its own, so the CLI stays free of spreadsheet code.
