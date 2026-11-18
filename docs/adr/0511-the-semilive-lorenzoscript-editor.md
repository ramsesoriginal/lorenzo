# 0511 - The semilive LorenzoScript editor

Status: accepted, built as slice W3a of [ADR 0494](0494-writing-moves-into-the-web-shell.md).

## Context

[WR12](../design/web/writing/README.md#wr12-three-habits-proposed) asks for writing that looks like a document: paragraphs shown formatted, the one being written as its source, Enter for a new paragraph. The decision of 2026-11-18 was no editor engine and no new dependency, in our own code, as a package other apps can use where it fits.

## Decision

- **`@lorenzo/lorenzoscript-semilive-editor`**, a package beside `@lorenzo/lorenzoscript-editor`, with the same options (`EditorOptions`) and the same editor object (`Editor`: `replaceSelection`, `element`, `refresh`, `destroy`). An app changes an import.
- **The original text area stays the text.** It is hidden, holds the whole text, is written on every change and gets `input` and `change` events. Only the open block is a second text area, holding that block's source.
- **Blocks are the parser's** ([ADR 0509](0509-lorenzoscript-block-ranges.md)); **keys are the source editor's** ([ADR 0510](0510-lorenzoscript-editor-keys-as-a-pure-function.md)); rendering is the `render` option, per block, with the footnote definitions a block refers to.
- **Moving about:** a click opens a block with the caret near the clicked word; the arrows open the neighbour at the edge of the text; Enter at the end of an ordinary paragraph starts a new one, Shift+Enter is a new line in it, Backspace in an empty block removes it; Escape closes the open one.
- **Selection across paragraphs** snaps to whole paragraphs, copies their source, and typing over it does nothing.
- **Undo and redo** keep one history of whole texts, so they run across paragraphs.
- **Checked** in jsdom (opening, editing, moving, new paragraph, list continuation, undo across blocks) and by the Writing end-to-end test of the Layout menu.

## Consequences

- A click's caret is found by matching the clicked text to the source, which is close, not exact, for text with markup in it; the open block then shows the exact source.
- Text is re-read into blocks when a block is left, so typing a blank line inside a block makes two once it is closed.
- The package has a hidden second text area per open block; an app that styles `.editor-content` should also style `.ls-semilive-field`.
