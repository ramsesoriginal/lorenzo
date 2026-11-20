# 0510 - The LorenzoScript editor's keys as a pure function

Status: accepted, built for the semilive editor of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (slice W3a).

## Context

[ADR 0106](0106-lorenzoscript-editor-and-demo.md) made every edit of `@lorenzo/lorenzoscript-editor` a pure action over `{ text, start, end }`, exported and tested alone. The keyboard rules (Tab indents, Escape then Tab leaves, Enter continues a list, Ctrl or Cmd with a letter runs an action) lived inside the DOM layer. A second editor over the same text, `@lorenzo/lorenzoscript-semilive-editor`, would have to copy them.

## Decision

- **`keyAction(event, state, afterEscape)`** is exported from `@lorenzo/lorenzoscript-editor`: from a key (the fields of a `KeyboardEvent` that matter) and the state, it returns `{ handled: true, state }` or `{ handled: false }`. `SHORTCUTS` and a `KeyInput` type are exported with it.
- **`createEditor` uses it**, so there is one rule. Its behaviour does not change.
- The actions were already exported by [ADR 0106](0106-lorenzoscript-editor-and-demo.md); nothing is added there.

## Consequences

- The semilive editor gets the same keys and the same shortcuts as the source editor, and a new action or key is made once.
