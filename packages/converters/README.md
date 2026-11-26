# lorenzo-converters

Simple converters from files players already have into Lorenzo's own documents: `sheet` into a
[LorenzoLedger](../../docs/guides/inventory-file-format.md), for `lorenzo import inventory`
([RFC 0035](../../docs/rfcs/0035-inventory-files-and-placeholder-items.md),
[ADR 0246](../../docs/adr/0246-lorenzo-converters-the-spreadsheet-converter.md)), and `donjon` into a
[calendar document](../../docs/guides/calendar-file-format.md), for `lorenzo import calendar`
([ADR 0311](../../docs/adr/0311-calendar-documents-import-and-app.md)). A converter reads a file and
writes a native document; it never talks to the API.

```bash
uv tool install "git+https://github.com/ramsesoriginal/lorenzo#subdirectory=packages/converters"

lorenzo-convert sheet inventory.xlsx --owner Mira -O mira.md
lorenzo import inventory mira.md --tenant my-library --dry-run
```

## `sheet`

An `.xlsx` with an **Items** table (name, count, weight of one, value, container, kind,
description) and, optionally, a **Container** table (name, place), or a `.csv` of the Items table.
Headers are found by name, in German or English (`Anzahl`/`Count`, `Gewicht`/`Weight`,
`gesch. Wert`/`Value`, `Container`, `Art`/`Kind`, `Beschreibung`/`Description`, `Ort`/`Place`).

- Containers come from the Container column, with names matched without case. A container that is
  also a row of Items is that row.
- A container named `holding`, `equipped`, `hands`, `in hand` or `worn` (or `--equipped NAME`, which adds one) is `## Equipped`; a row with no container is in `## Not carried`.
- A container whose place is not home (`--home`, or the most common place) is kept elsewhere:
  `place:` at the top of Not carried.
- Formulas are not read; an empty cell is left out. Kinds are copied as written.

Warnings go to standard error. Read the ledger before importing it.

## `donjon`

Saved exports from [donjon's fantasy calendar](https://donjon.bin.sh/fantasy/calendar/)
become a [native calendar document](../../docs/guides/calendar-file-format.md), separate from
LorenzoLedger. The converter reads files only and needs no credentials.

```bash
lorenzo-convert donjon calendar-3242.json calendar-3286.json \
  --name "Isles" --source-key isles --reference-year 3286 -O isles.calendar.json
```

The reference is an exported year, never today. The converter preserves that year's weekdays
and moon phases, then advances moons continuously. A moon anchor that disagrees with
continuous progression from the reference produces a warning, and the reference is kept. Weekday
anchors that disagree (two exports of the reference year, or another exported year against the
reference) are refused, as are inconsistent structures, conflicting note text, invalid dates and
duplicate dictionary names. Source segments preserve donjon's ordinary annual month/weekday behavior; choose
festival, leap and weekless rules explicitly in the native document. Unnamed segments/moons
get stable positional keys and display names. Fractional moon periods are retained.

Repeated notes are deduplicated, blank notes stay only in preserved source data, and other
notes default to ordinary Information. Choose classifications in the import choices file or
the document. `--unescape-html` decodes one layer of entities in authored text and retains the
original. Source values are kept in the document, including generator settings; those settings
do not become story events. Warnings go to stderr, JSON to stdout (or `-O`).

Git installation resolves the shared calendar contract from this repository's `main`, matching
the converter's normal installation source. Development uses its local uv path source.

## Developing

`mise run //packages/converters:test` and `:lint`; `mise run //packages/converters:dev -- sheet --help` runs the command. The ledgers the tests expect are in
`tests/golden/*.ledger` (not `.md`, which the Markdown linter would read as prose); `apps/cli` has a test that parses every one
with the importer's own parser.
Fixtures are made-up inventories, never a real player's.
