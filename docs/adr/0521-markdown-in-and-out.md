# 0521 - Markdown in and out

Status: accepted, the first of the three formats of C3 in [ADR 0494](0494-writing-moves-into-the-web-shell.md) (the others are Word out, ADR 0522, and Word in, ADR 0523), built because the maintainer asked for it. [RFC 0047](../rfcs/0047-lorenzo-writing.md) and [WR12](../design/web/writing/README.md) say each format is its own ADR.

## Context

Writing exported a LorenzoScript ZIP and a printable PDF, and imported nothing. LorenzoScript is a Markdown dialect, so a Markdown file is the nearest thing to a common currency with Obsidian and other writing tools.

## Decision

- **Markdown out**: the Export dialog gets "Download Markdown", enabled once the saved writing is previewed, like the other downloads. It is made in the browser from the same saved snapshot and the same walk as the printable export, so the order, the numbers and the selected passages are the same. Headings of the outline are `#` to `######`; each text goes out as its LorenzoScript source; each picture as a `data:` image, so the one file holds everything. The footnote labels of different texts are made distinct (`[^t1-a]`, `[^t2-a]`), as the printable export does with its ids. A generated contents list and the numbers' own formatting beyond the label are not exported.
- **Markdown in**: the shelf's "Start something else" menu gets "Import Markdown files" and "Import a folder of Markdown files" (a vault). `.md`, `.markdown` and `.txt` are read; the rest are named as left out. A file's name for its Chapter is its first `# heading` (then dropped from the text), else a `title:` in its front matter (the front matter is dropped), else its file name. One file becomes one Chapter; several become a new Book, named for the folder or "Imported writing", with a Chapter for each file in name order (numbers compared as numbers).
- **Links**: `[[links]]` are kept as written. The shelf says how many there are, and they are reviewed in the editor with the link review that already exists, not matched silently.
- **What is not read**: images and attachments of a vault, nested folders as nested Chapters, callouts and tags (they stay as text), and files over the API's size limits (the API's own message is shown).

## Consequences

- No API change: the import uses the Chapter, Book, manuscript and composition operations that exist; the export is client-side.
- The converters live under `apps/writing/src/lib/formats/` and become a package when a second app needs them.
