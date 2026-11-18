# 0509 - LorenzoScript block ranges

Status: accepted, built for the semilive editor of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (slice W3a).

## Context

The parser turns a source into a tree and keeps no positions. An editor that shows each paragraph, list or table of a text formatted, and only the clicked one as source, has to know which lines of the source each top-level block covers. Doing it by splitting on blank lines is wrong: a fenced code block, a list with loose items and a table can hold blank lines, and a footnote definition is no block at all.

## Decision

- **`blockRanges(source)`** is added to `@lorenzo/lorenzoscript`. It returns, for each top-level block, `{ type, start, end }`: the block's type, its first line (from 0) and one past its last, in the lines of the source after CRLF is read as LF. A footnote or abbreviation definition, which `parse` records on the document and not as a block, is a range of type `definition`. Blank lines belong to no range.
- **It uses the parser's own block rules**, the same functions in the same order, so it cannot disagree with `parse` about where a block ends. The test holds the count of its non-definition ranges to `parse(source).children.length`.
- **Additive.** `parse`, its tree and its output do not change, and no existing test changes.

## Consequences

- A second consumer of the block rules exists; a new block rule needs nothing extra, since the ranges are taken from the rule's own result.
- Positions inside a block (for a caret) are not given; the editor holds a clicked block's source in its own text area.
