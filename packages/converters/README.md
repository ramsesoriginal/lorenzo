# lorenzo-converters

Simple converters from files players already have into a
[LorenzoLedger](../../docs/guides/inventory-file-format.md), for `lorenzo inventory import`
([RFC 0035](../../docs/rfcs/0035-inventory-files-and-placeholder-items.md),
[ADR 0243](../../docs/adr/0243-lorenzo-converters-the-spreadsheet-converter.md)). A converter reads a
file and writes a ledger; it never talks to the API.

```bash
uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=packages/converters"

lorenzo-convert sheet inventory.xlsx --owner Mira -O mira.md
lorenzo inventory import mira.md --tenant my-library --dry-run
```

## `sheet`

An `.xlsx` with an **Items** table (name, count, weight of one, value, container, kind,
description) and, optionally, a **Container** table (name, place), or a `.csv` of the Items table.
Headers are found by name, in German or English (`Anzahl`/`Count`, `Gewicht`/`Weight`,
`gesch. Wert`/`Value`, `Container`, `Art`/`Kind`, `Beschreibung`/`Description`, `Ort`/`Place`).

- Containers come from the Container column, with names matched without case. A container that is
  also a row of Items is that row.
- `holding` (or `--equipped NAME`) is `## Equipped`; a row with no container is in `## Not carried`.
- A container whose place is not home (`--home`, or the most common place) is kept elsewhere:
  `place:` at the top of Not carried.
- Formulas are not read; an empty cell is left out. Kinds are copied as written.

Warnings go to standard error. Read the ledger before importing it.

## Developing

`mise run //packages/converters:test` and `:lint`. The ledgers the tests expect are in
`tests/golden/`; `apps/cli` has a test that parses every one with the importer's own parser.
Fixtures are made-up inventories, never a real player's.
