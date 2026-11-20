# @lorenzo/lorenzoscript-semilive-editor

A second editor for LorenzoScript, beside [`@lorenzo/lorenzoscript-editor`](../lorenzoscript-editor): the same options and the same editor object, so an app changes an import and nothing else. The design is [ADR 0494](../../docs/adr/0494-writing-moves-into-the-web-shell.md) (slice W3a) and [ADR 0511](../../docs/adr/0511-the-semilive-lorenzoscript-editor.md).

```ts
import { createEditor } from '@lorenzo/lorenzoscript-semilive-editor'; // was '@lorenzo/lorenzoscript-editor'

const editor = createEditor({ textarea, toolbar: ['bold', 'italic', 'heading', 'bullets', '|', 'undo'] });
```

What it does differently: the text is shown as paragraphs, headings, lists, tables and code blocks, formatted. The one you click, or arrow or tab into, becomes a text area holding its source, with the caret where you clicked. Enter at the end of an ordinary paragraph starts a new one, Shift+Enter is a new line in the same one, Escape closes the open one, and the arrows leave it at its edges. A selection across paragraphs snaps to whole paragraphs, copies their source, and typing over it does nothing. Undo and redo run across paragraphs.

The original `<textarea>` stays the one place the text lives: it is hidden, holds the whole text, and gets `input` and `change` events, so an app that reads `textarea.value` is unchanged. The keys are the source editor's own (`keyAction`), the blocks are the parser's own (`blockRanges`), and the preview is the same `render` option.

Styling: the package ships no CSS. The brand's `.ls-editor` and `.ls-content` apply; an app can style `.ls-semilive-blocks`, `.ls-block`, `.ls-block-open` and `.ls-block[data-selected]`.

```sh
mise run //packages/lorenzoscript-semilive-editor:test
mise run //packages/lorenzoscript-semilive-editor:build   # the demo
```
