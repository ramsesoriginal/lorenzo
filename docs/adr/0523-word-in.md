# 0523 - Word in

Status: accepted, the third format of C3 in [ADR 0494](0494-writing-moves-into-the-web-shell.md), after [ADR 0521](0521-markdown-in-and-out.md) and [ADR 0522](0522-word-out.md).

## Context

A writer arriving from Word has a manuscript in `.docx`. Pasting from Word already works (the editor's paste), but a whole file, with its chapters, is a different job, and Markdown import (ADR 0521) cannot read it.

## Decision

- **The shelf's import takes `.docx` as well as Markdown and text**, from the same two menu items (files, or a folder) and by the same rule: one file becomes a Chapter, several become a Book with a Chapter each, in name order.
- **Read in the browser, from the file's own XML**, with a small reader (no page, no server): `fflate` unzips it, `word/document.xml` is read in order. A Word file's own `Title` and `Heading 1` to `6` styles become the title and `#` headings (the first level-1 heading names the Chapter and leaves the text, as for Markdown); paragraphs become paragraphs; bold, italic, strike-through, super- and subscript and a monospace font become `**`, `*`, `~~`, `^`, `~` and code; hyperlinks become `[text](address)`; bulleted and numbered lists (read from the file's numbering definitions, with their nesting) become `-` and `1.` lists; the Quote style becomes `>`; Code styles become a fenced block; tables become pipe tables; footnotes become `[^n]` with their definitions. Runs Word splits for editing are merged first, so a bold phrase is one bold span.
- **Plain text is made plain**: the characters LorenzoScript reads as syntax are escaped (`*`, `_`, `[`, `<`, `{` and the rest), so a Word sentence with an asterisk stays a sentence. `[[Name]]` and `[[Name|alias]]` typed in the Word text are kept as links and counted for the link review, as with Markdown.
- **What is not read, and said so**: pictures (the shelf says how many were left out), comments, tracked deletions (the text that was deleted is not imported, an insertion is), headers and footers, text boxes and the page layout. A file that is not a Word file is refused in words.

## Consequences

- No API change; the Chapters are made with the operations of ADR 0521.
- A Word file written by this app (ADR 0522) imports back with its headings, text, lists, tables and footnotes, except that links to library entries come back as plain words.
- Checked with a file made by python-docx and with files this app writes.
