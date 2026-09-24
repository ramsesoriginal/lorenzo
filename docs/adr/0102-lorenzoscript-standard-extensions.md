# 0102 - LorenzoScript standard extensions

Status: accepted

## Context

[RFC 0027](../rfcs/0027-lorenzoscript.md) stage 2 adds the extensions table of its §2 to the core built in [ADR 0100](0100-lorenzoscript-core-parser-and-renderer.md): deletion, sub/superscript, tables, footnotes, abbreviations, attributes, class blocks, `{{TOC}}`, and math. The RFC fixed the syntax. This ADR decides how each fits into the existing parser and renderer, and what exactly the math subset is.

Numbered past ADR 0101, which the parallel description-editing work claimed first ([PR #212](https://github.com/ramsesoriginal/lorenzo/pull/212)).

## Decision

### Delimiter rows, not new code

`~` and `^` join `*` and `_` in the inline pass's per-character table, as ADR 0100 intended. They pair only with a run of the *same* length: `~sub~`, `~~del~~`, and `^sup^`. A run of three or more is text. Like `*`, they work inside words, so `H~2~O` and `2^10^` work, while flanking rules keep `~5 to ~10` literal. They render as `<sub>`, `<del>`, and `<sup>`.

### Definitions are document data, not blocks

Footnote definitions (`[^label]: text`, continued by lines indented 4, like a list item) and abbreviation definitions (`*[HTML]: …`) are collected while parsing into `Document.footnotes` and `Document.abbreviations`. They don't appear in the flow. The first definition of a label or term wins. Footnote labels match case-insensitively with whitespace collapsed, as CommonMark link labels do.

A reference `[^label]` always parses as a `footnote` node, and the renderer decides what it becomes. Definitions usually come after their references, so the parser can't know yet whether a label exists. This is the same "parse the syntax, resolve at render" split stage 3 uses for entity links.

- Footnotes are numbered by first reference, including references made inside other footnotes. They're listed at the end in a `<section class="ls-footnotes">`, each with a back-link. A reference to an undefined label renders as its literal text.
- Abbreviations wrap whole-word, case-sensitive occurrences in `text` nodes (never in code) in `<abbr title>`, longest term first.

### Attributes

`{#id .class}` is one token list, shared by every place that takes one, including `{{ }}` class blocks:

- after a heading's text
- after a fenced code block's language (on the `<pre>`; the language class stays on `<code>`)
- directly after an inline element (span, link, image, code span, math)

Inline, the scanner emits a pending attribute node. After emphasis is resolved, it attaches to the element right before it, or becomes its literal text. That's the only way `*text*{.x}` can work, since the `<em>` doesn't exist until then.

`Attrs` is `{ id, classes }`, an optional field on the nodes that take it. Adding optional fields keeps ADR 0100's promise never to repurpose existing node shapes.

Every heading now gets an id: its explicit one, else a slug of its text (NFKD, diacritics stripped, lowercase, runs of anything but `a-z0-9` become `-`), de-duplicated with `-2`, `-3`. This slugify is the one stage 3 uses for `[[wikilinks]]`, so it's defined once. That changes every heading in stage 1's examples, which is deliberate: `[see](#notes)` needs somewhere to land.

### `{{ }}`

- **A line that is only `{{` plus an attribute list opens a class block**, closed by a line that is only `}}`. It nests and can contain any block, and renders as `<div>`. There's no fence awareness: a `}}` line inside a code block inside a class block closes the block.
- **`{{.note text}}` inside a paragraph is an inline span.** Its openers use a second stack beside the link bracket stack, sharing the same closing code, so neither can recurse, and closing either drops openers left open inside it.
- **`{{TOC}}`, case-insensitive, on its own line is a block directive.** It renders a nested list of every heading in the document, linking to their ids, as `<nav class="ls-toc">`. An unknown `{{name …}}` is text.

### Tables

GitHub's syntax. A header row and a delimiter row (which must contain `|`) with the same number of cells start a table, even directly under a paragraph line, which then ends. Rows run to a blank line or the next block. They're padded or cut to the header's width. `\|` is a literal pipe. Alignment renders as `align="…"`, as GitHub's does: that needs no CSS and survives a strict `style-src` CSP, unlike inline `style`.

### Math: a TeX subset rendered to MathML Core

Syntax:

- `$…$` is inline math. Like Pandoc's, it can't start or end with a space, or be followed by a digit, so `$5 and $10` stays text.
- `$$…$$` inside a paragraph is display math.
- A line that is only `$$` opens a math block that runs to the next such line, and `$$…$$` alone on a line is a one-line block. The block form exists so an equation line starting with `-` or `+` can't be read as a list.

Rendering: `src/math.ts` turns the TeX into MathML Core, which current browsers draw natively. There's no KaTeX or MathJax. The supported subset is:

- letters (`<mi>`), numbers (`<mn>`), and the ASCII operators, with `-` becoming a real minus
- `^`, `_`, and primes, where a script takes one token or a `{group}`, so `x^10` is x¹0 as in TeX
- `\frac`, `\binom`, `\sqrt` and `\sqrt[n]`
- `\left…\right`, with `.` for "no delimiter"
- Greek letters (uppercase upright, `\var…` variants), relations, arrows, set and logic symbols, dots, and delimiters (`\langle`, `\lfloor`, …)
- big operators: `\sum`, `\prod`, `\bigcup`, … take limits under and over; the `\int` family takes scripts
- function names (`\sin`, `\log`, …), with `\lim`, `\max`, `\min`, `\sup`, `\inf`, … taking limits
- accents (`\hat`, `\bar`, `\vec`, `\dot`, `\ddot`, `\tilde`, `\overline`)
- spacing (`\,` `\:` `\;` `\!` `\quad` `\qquad` `~`), `\text{…}` and `\operatorname{…}`
- escaped `\{ \} \| \$ \% \# \& \_`

Anything else throws inside the converter: `\\`, `&`, `\begin`, fonts, sizes, unknown commands, unbalanced braces, and nesting past `MAX_NESTING`. The whole formula then renders as `<code class="ls-math">` holding its TeX. It fails loudly and readably, never half-rendered. Everything emitted is escaped, and no MathML attribute takes an author value.

## Not in scope

- Entity links, `{{date}}`, `{{cal}}`, and any inline directive (stage 3).
- Matrices and aligned environments; toggling task checkboxes.
- Homebrewery page and column layout beyond class blocks.
- Fence awareness for `}}` inside a class block.

## Consequences

- Heading ids change every heading's HTML, and give in-document links and `{{TOC}}` stable targets. An explicit `{#id}` can still collide with a generated footnote id (`ls-fn-1`) if an author writes `{#fn-1}`; that's rare and harmless, so it isn't guarded.
- `Document` gains `footnotes` and `abbreviations`. Stage 7's Python extractor reads references, not these, and can ignore them.
- Math covers what people write in campaign notes (dice probabilities, damage formulas, fractions, sums), not full LaTeX. The fallback to code makes the boundary visible instead of wrong.
- The renderer now keeps per-render state (footnote numbering, the abbreviation pattern). It's still one synchronous function of the document.
