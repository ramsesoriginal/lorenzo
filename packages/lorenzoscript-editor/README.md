# @lorenzo/lorenzoscript-editor

A `<textarea>` editor for [LorenzoScript](../lorenzoscript): a configurable toolbar that inserts the syntax, keyboard helpers, and a live preview. There's no WYSIWYG: you edit the source text. The design is in [RFC 0027](../../docs/rfcs/0027-lorenzoscript.md) and [ADR 0106](../../docs/adr/0106-lorenzoscript-editor-and-demo.md).

```ts
import { createEditor } from '@lorenzo/lorenzoscript-editor';

const editor = createEditor({
  textarea: document.querySelector('textarea[name="description"]')!,
  layout: 'split', // or 'tabs'
  toolbar: ['bold', 'italic', '|', 'link', 'entity'], // default: DEFAULT_TOOLBAR
  render: async (source) => { /* parse, fetch references(), render with a resolver */ },
});
```

It enhances the textarea in place, keeping its form, name, and value, so the page still works as a plain textarea without JavaScript. `editor.destroy()` puts it back.

- **Toolbar.** Action names from `ACTIONS`: `bold`, `italic`, `strike`, `sub`, `sup`, `code`, `math`, `link`, `entity`, `image`, `date`, `heading`, `quote`, `bullets`, `numbers`, `tasks`, `codeblock`, `table`, `rule`, `toc`, `footnote`, plus `undo`, `redo`, and `'|'` for a divider. Edits go through the browser's own undo.
- **Keys.** Ctrl/⌘+B, I, and K for bold, italic, and link. Enter continues a list, task list, or quote, and ends it on an empty item. Tab and Shift-Tab indent and outdent by 4 spaces. **Escape, then Tab, moves on to the next field.**
- **Preview.** Without `render`, the preview is LorenzoScript with no resolver, so entity links show as plain text. Pass your own `render`, possibly async, to look up `references()` first. An older result never replaces a newer one.

Styling lives in `apps/brand` (`.ls-editor`, and `.ls-content` for rendered text anywhere); this package ships no CSS. The actions in `ACTIONS` are pure `(text, selection)` functions, exported for reuse and tested on their own.

## Demo

```bash
mise run //packages/lorenzoscript-editor:build   # bundles demo/demo.js
```

Then open `demo/index.html`, straight from disk: it uses a pre-built script because browsers block ES modules over `file://`. It shows the editor over an in-memory stand-in for Lorenzo, with a list of what the text refers to. `mise run //packages/lorenzoscript-editor:dev` rebuilds the bundle on every change.

```bash
mise run //packages/lorenzoscript-editor:test   # the actions
mise run //packages/lorenzoscript-editor:lint   # Biome + tsc --noEmit
```
