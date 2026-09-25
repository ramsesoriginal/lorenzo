# 0106 - LorenzoScript editor: `packages/lorenzoscript-editor` and a static demo

Status: accepted

## Context

[RFC 0027](../rfcs/0027-lorenzoscript.md) stage 4 is the editor: a `<textarea>` with a configurable toolbar that inserts LorenzoScript, a live preview, and a static demo page that works before any API exists. The RFC fixed the broad shape in §4:

- source text only, no WYSIWYG
- toolbar actions are pure functions of text and selection
- insertion keeps the browser's native undo

This ADR decides the rest: the API, which keys do what, where the styling lives, and how the demo is built.

## Decision

### Package

`packages/lorenzoscript-editor` (`@lorenzo/lorenzoscript-editor`) ships TypeScript source like its sibling ([ADR 0100](0100-lorenzoscript-core-parser-and-renderer.md)). It has one dependency, `@lorenzo/lorenzoscript`. esbuild is a dev dependency, used only to bundle the demo; it's already in the workspace through Astro/Vite.

### Actions are pure

`src/actions.ts` holds every edit as `(state: { text, start, end }) => state`: wrapping, line prefixes, blocks, list continuation, indentation. vitest tests them with a compact notation: `he[llo]` is a selection and `he|llo` a cursor. The toolbar is a list of action names (plus `'|'` for a divider), so an app can show a subset, reorder them, or leave some out.

- **Inline:** `bold`, `italic`, `strike`, `sub`, `sup`, `code`, `math`, `link`, `entity` (`[[…]]`), `image`, `date` (today's `{{date}}`). Wrapping an already-wrapped selection unwraps it.
- **Lines:** `heading` (cycles `#` → `##` → `###` → none), `quote`, `bullets`, `numbers`, `tasks`. A line's existing list marker is replaced rather than stacked, and applying the same one again removes it.
- **Blocks:** `codeblock`, `table`, `rule`, `toc`, `footnote`. `footnote` inserts the next free `[^n]` at the cursor and its definition at the end.

### The DOM layer is thin

`createEditor({ textarea, toolbar?, layout?, render?, delay? })` enhances an existing `<textarea>`. It wraps it with a toolbar and a preview pane, moves nothing out of its form, and changes nothing about its name or value, so the page works as a plain textarea without JavaScript.

- **Edits.** An action's result is applied as the smallest changed range, through `execCommand('insertText')`, so native undo and redo keep working. Where that isn't supported, the fallback sets the value directly and fires an `input` event: the same result, without native undo.
- **Keys.**
  - `Mod-B`, `Mod-I`, and `Mod-K` for bold, italic, and link.
  - Enter continues a list, task list, or quote, and ends it on an empty item.
  - Tab and Shift-Tab indent and outdent by 4 spaces, the RFC's list-continuation width.
  - **Escape, then Tab, leaves the editor.** Taking over Tab would otherwise trap keyboard users inside the textarea.
- **Preview.** `layout` is `'split'` (side by side, stacked when the editor itself is narrow, by container query rather than viewport) or `'tabs'` (Write/Preview). The preview re-renders on a short debounce. `render` defaults to `render(parse(source))`. An app passes its own (possibly `async`) function to prefetch `references()` and supply a resolver; a slower, older result never overwrites a newer one.

### Styling belongs to the brand

[ADR 0098](0098-branding-css-app-and-package.md) made `apps/brand` the one shared stylesheet, and `.editor-toolbar`/`.editor-content` already live there. It gains:

- `.ls-editor`: the panes and the two layouts.
- `.ls-content`: styles for rendered LorenzoScript wherever it's shown, not only in the preview. That covers tables, quotes, code, task lists, `{{TOC}}`, footnotes, abbreviations, `ls-entity`, `ls-cal`, and display math.

The editor package ships no CSS. The brand's icon sprite has no formatting icons, so toolbar buttons are text glyphs (`B`, `I`, `S`, …), each with an accessible name and its shortcut in the title.

### A demo that opens from disk

`demo/index.html` links `apps/brand`'s stylesheets directly and loads `demo/demo.js`, an IIFE bundle of `demo/demo.ts`. Browsers block ES modules over `file://`, so the bundle is what makes double-clicking the file work. The bundle is `.gitignore`d and built by `mise run //packages/lorenzoscript-editor:build`, the same "generated, run build first" precedent as `packages/brand`. The demo's fake resolver knows a few entities, one with a picture served as a `blob:` URL, the way a real app would serve a token-fetched picture.

## Not in scope

- Slug autocomplete, syntax highlighting inside the textarea, scroll sync, and drag-and-drop uploads.
- Tests of the DOM layer: the pure actions are tested, the DOM wiring is checked by hand in the demo, and browser end-to-end tests arrive with stage 6's real consumer (Playwright, as `apps/account-hub` already uses).

## Consequences

- Any app gets the editor by wrapping a textarea it already has, and gets consistent rendered-text styling from the brand whether or not it uses the editor.
- `apps/brand` changes, so its release version moves; `packages/brand` picks the new styles up on its next build.
- Relying on `execCommand` means relying on a deprecated API for undo. Every current browser supports it for textareas, and the fallback keeps editing working where it's gone, only without native undo for toolbar edits.
