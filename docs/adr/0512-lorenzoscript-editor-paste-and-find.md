# 0512 - Paste from Word, and find and replace, in the LorenzoScript editor

Status: accepted, built as the small editor helpers of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (WR12, B1 and B2). `[[` completion and quiet highlighting (B3, B4) are not built.

## Context

An author used to Word, Google Docs or LibreOffice pastes formatted text and expects its headings, emphasis and lists to arrive, and expects Ctrl+H. In a plain text area the paste brings the words and loses the rest, or none of it if the program puts only HTML on the clipboard.

## Decision

- **`pasteFromWord`**, an option of `createEditor`, off by default: when the clipboard holds HTML with structure or emphasis, it is converted to LorenzoScript (`htmlToScript`, exported and tested) and inserted through the same `apply` as every other edit, so the browser's undo still works. Headings, bold and italic (also as Word's and Google Docs' span styles), strike-through, code, links with an http(s) or mailto address, lists, numbered lists and quotations survive; styles, classes, fonts and office markup are dropped; any other link keeps its words only. Plain HTML with no structure is left to the browser.
- **`findReplace`**, an option, off by default: Ctrl or Cmd with H opens a bar with Find, Replace with, Next, Replace, Replace all, Close and a count. The matching and replacing are pure (`findAll`, `replaceMatches`, exported and tested); the bar is a small piece of DOM.
- **Opt-in, so every app that uses the editor is unchanged.** Writing turns both on.

## Consequences

- The semilive editor does not have them yet: its blocks are text areas of their own, and find and replace over the whole text needs a different bar. Paste could be shared the same way; both are to be done when the semilive editor is used in more places.
- `[[` completion needs a lookup of entities, which the editor package has no client for; it stays in the apps' hands (the `entity` tool) until it is designed.
