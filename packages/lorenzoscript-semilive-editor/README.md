# @lorenzo/lorenzoscript-semilive-editor

A second editor for LorenzoScript, beside [`@lorenzo/lorenzoscript-editor`](../lorenzoscript-editor): the same editor object (`replaceSelection`, `element`, `refresh`, `destroy`) and a part of its options, so an app that passes only those changes an import and nothing else. The options it reads are `textarea`, `toolbar`, `render` and `reviewEntitySelection`. `layout`, `delay`, `pasteFromWord`, `findReplace`, `completeNames` and `highlight` are accepted by the type and ignored; [ADR 0512](../../docs/adr/0512-lorenzoscript-editor-paste-and-find.md), [ADR 0514](../../docs/adr/0514-lorenzoscript-editor-name-completion.md) and [ADR 0516](../../docs/adr/0516-lorenzoscript-editor-quiet-highlighting.md) say the semilive editor does not have those features yet. The design is [ADR 0494](../../docs/adr/0494-writing-moves-into-the-web-shell.md) (slice W3a) and [ADR 0511](../../docs/adr/0511-the-semilive-lorenzoscript-editor.md).

```ts
import { createEditor } from '@lorenzo/lorenzoscript-semilive-editor'; // was '@lorenzo/lorenzoscript-editor'

const editor = createEditor({ textarea, toolbar: ['bold', 'italic', 'heading', 'bullets', '|', 'undo'] });
```

What it does differently: the text is shown as paragraphs, headings, lists, tables and code blocks, formatted. The one you click, or arrow or tab into, becomes a text area holding its source, with the caret where you clicked. Enter at the end of an ordinary paragraph starts a new one, Shift+Enter is a new line in the same one, Escape closes the open one, and the arrows leave it at its edges. A selection across paragraphs snaps to whole paragraphs, copies their source, and typing over it does nothing. Undo and redo run across paragraphs.

The original `<textarea>` stays the one place the text lives: it is hidden, holds the whole text, and gets `input` and `change` events, so an app that reads `textarea.value` is unchanged. The keys are the source editor's own (`keyAction`), the blocks are the parser's own (`blockRanges`), and the formatted paragraphs come from the same `render` option.

Styling: the package ships no CSS. The brand's `.ls-editor` and `.ls-content` apply; an app can style `.ls-semilive-blocks`, `.ls-block`, `.ls-block-open`, `.ls-block[data-selected]` and the open paragraph's text area, `.ls-semilive-field` ([ADR 0511](../../docs/adr/0511-the-semilive-lorenzoscript-editor.md)).

```sh
mise run //packages/lorenzoscript-semilive-editor:test
mise run //packages/lorenzoscript-semilive-editor:build   # the demo
```
