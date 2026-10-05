# 0191 - The inventory file, format v1

Status: accepted, decided with the maintainer on 2026-10-05.

Slice 1 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md). Records the file format and nothing that reads it: the commands, the placeholder item and the screens are later slices, each its own ADR.

## Context

Players have inventories in spreadsheets and documents and want them in Lorenzo ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) Context). A format they can write now, and that tools can convert into later, has to be fixed before any importer exists, and then not move.

## Decision

The specification is the [guide](../guides/inventory-file-format.md); this records what was decided and why, and the guide is normative where the two ever differ.

- **Markdown list, with a JSON twin of the same model.** The list extends the pack-list grammar of [ADR 0145](0145-pack-contents-in-the-description.md): `- N x Name`, two spaces of indent per level meaning "in", a `[Label](reference)` link accepted. Fields follow the name after `|`. JSON carries the same fields for scripts and `export --json`.
- **Header and sections.** `format: lorenzo-inventory/1` and `owner:` (one per file), optional `library:`. Sections `## Equipped` and `## Not carried`, with the aliases the guide lists (`Holding` among them, which an existing spreadsheet uses for the hand). Any other heading is a reported problem; every other grouping is a container line.
- **Fields**: `ref` (an instance id, an item id or a slug), `item` (what an export writes), `weight` (pounds, per piece), `value` (free text), `kind` (a hint), `note`, `place`. All optional. Unknown fields are ignored with a warning, which is what lets a later version add fields without breaking a v1 reader.
- **Containers** are lines with indented lines under them, up to six levels. A container is one; a stack needs a container ([ADR 0140](0140-a-stack-when-an-item-instance-is-created.md)). A container kept elsewhere is a container under *Not carried* with a `place:`.
- **Matching order**: instance id, item id, slug, exact title, preprocessed title, then a placeholder; case-insensitive, trimmed. What is matched is what the caller may see.
- **Import creates; `--add` moves.** Create-only into an empty character; a line naming an instance id of the owner's own moves it. Nothing else is updated.
- **Weight, value, kind and place are kept as a note** on the instance, not as data, since they are for a person to read and no screen sorts by them yet.
- **Versioned and forward-tolerant.** A reader meeting a version it does not know says so and stops; later versions add and do not redefine.

## Not in scope

- Any code: no parser, no command. Slice 3 builds those against shared test cases.
- Converters, the placeholder item and its API, the screens: the rest of the RFC's slices.
- A schema file for the JSON form. It is small enough to be described in the guide; one is added if a tool wants it.

## Consequences

- Players and script authors can start now, against a page that will not move under them.
- The Markdown form stays a superset of the pack list, so one parser's idea of a line is not two.
- Putting weight and value in a note keeps them out of the schema until something needs to compute with them; a later slice can promote them without a format change, since they are already named fields.
