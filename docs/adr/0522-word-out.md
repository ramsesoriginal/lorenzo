# 0522 - Word out

Status: accepted, the second format of C3 in [ADR 0494](0494-writing-moves-into-the-web-shell.md), after [ADR 0521](0521-markdown-in-and-out.md).

## Context

Writers who share a manuscript with an editor or a publisher are asked for a Word file. Writing exported a LorenzoScript ZIP, a printable PDF and, with ADR 0521, Markdown.

## Decision

- **The Export dialog gets "Download Word"**, enabled once the saved writing is previewed, giving a `.docx`. It is made in the browser from the same parts as the Markdown export (ADR 0521), so the order, the numbers and the selected passages are those of the printable export.
- **From the syntax tree, not from HTML:** each text is parsed with LorenzoScript's own parser, so nothing depends on a page being rendered. The outline's headings are Word's Heading 1 to 6; a heading inside a text sits below the heading of its Chapter.
- **What Word gets:** paragraphs, bold, italic, strike-through, sub- and superscript, inline code and code blocks (Courier New), quotes (the Quote style), bullet and numbered lists as real Word lists (numbered lists keep their starting number, and nest), task items as ☐ and ☒, rules, tables with borders, real footnotes, hyperlinks for web and mail addresses, and pictures in their own size (PNG, JPEG, GIF and WebP) scaled to the page width.
- **What it does not carry:** a link to an entry of the library has no address outside the library, so its words stay as plain text; maths is written as its TeX in italics; the generated contents list is not exported; a picture of a format Word does not read is replaced by a line saying so.
- **The zip library** is `fflate` (MIT, no dependencies), added to Writing only.

## Consequences

- No API change.
- The file was checked with python-docx, pandoc and LibreOffice (which converts it to PDF); the unit tests check its parts and the e2e checks the download.
- The converter lives under `apps/writing/src/lib/formats/` and becomes a package when a second app needs it.
