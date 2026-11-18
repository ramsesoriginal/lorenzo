# 0516 - Quiet highlighting in the LorenzoScript editor

Status: accepted, built as B4 of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (WR12).

## Context

A source with `**`, `#`, `[[` and backticks is easier to read when the markers recede. A text area cannot colour part of its text, and an editor engine was ruled out.

## Decision

- **`highlight`**, an option of `createEditor`, off by default. The text area is wrapped, and a layer of the same text sits behind it with the same font, padding, borders and wrapping (copied from the text area's computed style, again when it is resized) and the same scroll. The text area's own text is made see-through, its caret kept, so one text is seen and the typing is unchanged.
- **Colour only.** The markers (headings' `#`, list and task markers, quote marks, emphasis and strike marks) are one class, code and fences, entity references and links others; an app colours them. Never size or weight, so the text under the layer keeps its exact place.
- **`highlightSource(text)`** is pure, exported and tested: it escapes everything, wraps only markers, returns the same characters, reads a line in one pass and holds a code fence together.
- **Writing turns it on** and colours the classes with brand tokens.

## Consequences

- The layer duplicates the text for assistive technology unless hidden: it is `aria-hidden`, and the text area stays the only control.
- The semilive editor's open block is a plain text area and has none of this yet.
