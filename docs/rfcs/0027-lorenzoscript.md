# RFC: LorenzoScript — a Markdown dialect, renderer, and editor for information text

Status: accepted — decided with the maintainer on 2026-09-24; each stage below lands in its own ADR

## Context

`payload_description.content` is plain `TEXT`, and [ADR 0017](../adr/0017-information-and-payloads.md) left its "rich text" format as an undecided convention. Nothing in this repo parses or renders Markdown today: `apps/inventory-web`'s item page shows descriptions with `textContent`, and `apps/account-hub`'s campaign description, notification body, and profile bio are bare `<textarea>`s.

Information text is where Lorenzo's domain gets dense: lore that names other entities ("Ashfang was forged in [[Emberdeep]]"), dates, stat notes, GM secrets. A plain textarea can't link to an entity, and a generic Markdown library can't either — it doesn't know what an entity, a slug, or a viewer's visibility is. The wanted experience sits between three existing tools: GitHub's Markdown editor (toolbar, Write/Preview), Obsidian (wikilinks between notes, backlinks), and Homebrewery (`{{ }}` blocks with classes). Live preview, no WYSIWYG. As few external libraries as possible.

[RFC 0015](0015-information-metadata-shape.md) (decision 5, sub-slice 2) already proposes `entity_slug`, one tenant-unique slug per entity, generalizing `item_instance.slug` ([ADR 0043](../adr/0043-item-instance-slug.md)). That is the natural key for links written by hand.

## Decision

### 1. LorenzoScript is the content convention for description payloads

LorenzoScript is a CommonMark-based dialect. It becomes the convention ADR 0017 left open for `payload_description.content`; no schema change, no format column. Existing plain-text content stays valid LorenzoScript, though a line that happens to start with `#` or `-` will now render as a heading or list.

### 2. Syntax

Core (CommonMark, with the deviations listed below):

| Element | Syntax |
| --- | --- |
| Headings 1–6 | `#` … `######` (ATX only) |
| Paragraph | blank line |
| Line break | two or more trailing spaces, or a trailing `\` |
| Emphasis (semantic) | `*em*` → `<em>`, `**strong**` → `<strong>` |
| Emphasis (stylistic) | `_i_` → `<i>`, `__b__` → `<b>`; styled separately by themes. Not inside words, so `snake_case` stays literal |
| Blockquote | `>`, nested, containing any other block |
| Lists | `1.` ordered; `-` or `*` unordered; content indented 4 spaces continues the item |
| Task list | `- [ ]` / `- [x]` → a disabled checkbox |
| Code | `` `code` ``; blocks fenced with ```` ``` ```` or `~~~`, or indented 4 spaces |
| Horizontal rule | `---`, `***` |
| Link, image | `[text](url "title")`, `![alt](url "title")`, `<https://…>` |
| Escape | `\` before any ASCII punctuation |

Extensions:

| Element | Syntax |
| --- | --- |
| Deletion | `~~del~~` |
| Subscript, superscript | `~sub~`, `^sup^` |
| Table | GitHub syntax, with `:---:` alignment |
| Footnote | `[^label]` and `[^label]: text`, numbered by first reference, listed at the end |
| Abbreviation | a line `*[HTML]: Hyper Text Markup Language`; whole-word occurrences become `<abbr title>` |
| Math | `$…$` inline, `$$…$$` block — a documented TeX subset rendered to native MathML |
| Attributes | `{#id .class}` after a heading, a fenced code block's info string, an inline element, or an image. No `key=value`, no `style` |
| Class block | `{{.monster .frame` on its own line … `}}` on its own line → `<div>`; nestable. Inline `{{.note text}}` → `<span>` |
| Directives | `{{TOC}}`, `{{date 2026-09-24}}`, `{{cal …}}` |
| Entity link | `[[Ashfang]]`, `[[Ashfang\|shown text]]`, `[[being/Ashfang]]`, `[text](ashfang)`, `[text](item_instance/ashfang "title")` |
| Entity image | `![alt](ashfang)` → that entity's main picture |

`{{ }}` is one extension point with one rule: if the first token starts with `.` or `#`, it's an attribute list (the same tokenizer as `{#id .class}`) and the rest is content. Otherwise the first token is a directive name. An unknown directive renders as literal text, so future directives never collide with class names.

- `{{TOC}}` lists every heading in the document, nested by level. Headings get automatic ids from their text, de-duplicated.
- `{{date 2026-09-24}}` is always ISO `YYYY-MM-DD` in the source, so it's unambiguous. It renders as `<time datetime>`, formatted in the viewer's locale with `Intl.DateTimeFormat`.
- `{{cal …}}` is an in-game calendar date. The syntax is reserved and parsed, keeping its raw arguments, but it renders unresolved: what a calendar is depends on how time works in the world model, which [RFC 0026](0026-world-model-axes-and-address.md) leaves explicitly open. It gets its own RFC.

Deliberate deviations from CommonMark, each to keep the parser small or the output safe: no raw HTML (it renders as text), no setext headings (`text` over `---` is a paragraph and a rule), no reference-style links (`[text][ref]`), no HTML entity references (`&copy;` stays literal), and `_`/`__` map to `<i>`/`<b>` rather than duplicating `*`/`**`.

### 3. Entity references

- **Targets.** In `[text](target)` and `![alt](target)`, a target with no URL scheme and no leading `/`, `.`, `#`, or `?` that matches `(hint/)?slug` is an entity reference. `slug` is `[A-Za-z0-9][A-Za-z0-9_-]*`, and `hint` is `[a-z_]+`.
- **Wikilinks.** `[[Target]]` slugifies its target: NFKD, strip diacritics, lowercase, runs of anything other than `a-z0-9` become one `-`, then trim the ends. So `[[Old Sword]]` → `old-sword`. The shared test files define this rule for every implementation.
- **The hint is a view hint, not a namespace.** Slugs are unique per tenant across all entities, so `item_instance/ashfang` and `being/ashfang` name the same entity — a sentient sword is both. The hint says which view to open and lets the app warn when the entity isn't one of those. The parser accepts any hint; which hints mean anything is up to the resolver, so the package doesn't hard-code Lorenzo's entity kinds.
- **Visibility.** Resolution always runs with the viewer's own credentials. An entity the viewer can't see resolves exactly like one that doesn't exist: the link text renders as plain text. A GM's public text linking a secret NPC must not reveal that the NPC exists.
- **Anything else** is an ordinary URL, subject to the security rules in §5. Lorenzo content therefore has no relative URLs.

### 4. Architecture: one parser, several consumers

Two zero-runtime-dependency TypeScript packages:

- **`packages/lorenzoscript`** (`@lorenzo/lorenzoscript`)
  - `parse(source) → Document`: two passes, blocks then inline, producing a plain-data syntax tree.
  - `references(doc) → Reference[]`: every entity link, entity image, date, and calendar reference.
  - `render(doc, options) → string`: an HTML string.
  - No DOM dependency, so it runs in the browser, in Node, and at build time.
- **`packages/lorenzoscript-editor`** (`@lorenzo/lorenzoscript-editor`): a `<textarea>` with a configurable toolbar and a live preview (split view or Write/Preview tabs), styled by `@lorenzo/brand`'s `.editor-toolbar`/`.editor-content`. It edits source text only; there is no WYSIWYG.
  - A toolbar or keyboard action is a pure function `(text, selectionStart, selectionEnd) → same`, testable without a browser.
  - The DOM layer applies the result with `execCommand('insertText')`, so native undo keeps working, falling back to `setRangeText`.
  - Also: Enter continues a list, Tab indents 4 spaces, and the preview re-renders on a short debounce.

Rendering stays synchronous. Resolution is a separate step the caller runs first: `references(doc)`, then one batched lookup, then `render(doc, { resolve })`. `resolve` holds synchronous lookups (`entity`, `image`, `calendar`) over the pre-fetched results. Without a resolver, the package renders standalone: entity links become plain text or placeholders.

One syntax tree also leaves room for other renderers later — Discord Markdown for `apps/loot-bot`, plain text for notifications — without a second parser.

Dev tooling only: TypeScript, vitest, biome, and esbuild, which is already in the workspace through Astro, to build the demo bundle.

### 5. Security: safe HTML by construction

- HTML is only ever built from the syntax tree, and every piece of text is escaped. Raw HTML is never passed through, so the output is safe to assign to `innerHTML`.
- Link URLs are allowed only for `http`, `https`, `mailto`, and in-document `#fragment`. Image URLs only for `https`. Anything else renders as plain text.
- Author ids are restricted to `[A-Za-z][\w-]*` and always rendered with an `ls-` prefix. `{#intro}` becomes `id="ls-intro"`, and `#intro` links are rewritten to match, so content can't collide with or target the host page's own ids. Author classes use the same character set, unprefixed so themes can style them. The renderer's own classes all use `ls-`.
- External `https` images are allowed, and that is a real privacy tradeoff: the image host sees every viewer's IP. Apps can turn external images off with a render option.

### 6. One spec, shared test files

`packages/lorenzoscript/SPEC.md` is the detailed, living definition of the syntax. `packages/lorenzoscript/spec/**/<case>.md` files, each paired with the expected `.html`, test the renderer. From stage 3 on, a `.refs.json` file with the expected references is added too. Every implementation must pass them. That includes stage 7's Python extractor, which exists because `apps/api` is Python and must extract references itself rather than trusting a client.

The parser follows CommonMark's architecture: block structure, then inlines, with its delimiter algorithm for emphasis. It doesn't chase full CommonMark compliance; the shared test files, not the CommonMark spec, define what LorenzoScript does.

### 7. API additions

- **Slugs:** RFC 0015 decision 5 (its sub-slice 2) is accepted as written: `entity_slug`, `GET .../entities/by-slug/{slug}`, `PUT`/`DELETE .../entities/{id}/slug`, and `item_instance.slug` moved onto it.
- **Batch resolve:** added on top, `GET /tenants/{tenant_id}/entities/resolve?slug=a&slug=b`, repeatable and capped. It returns `[{slug, entity_id, name, kinds}]` for only the entities the caller could read via `GET /entities/{id}`; missing and invisible slugs are simply absent. Rendering one document should cost one request, not one full `EntityDetailOut` per link.
- **Connections (stage 7):** a derived `content_reference` table (payload → target, kind, raw target), written when a description is written, plus a "what links here" read. Unresolved targets are kept, like a wiki's red links, so they can resolve once the slug exists. Backlink reads must respect the *source* information's visibility, because a backlink from GM-only text reveals a secret. The exact shape is decided in that stage's ADR. This is distinct from RFC 0015's `payload_entity`, which is an explicitly authored reference rather than one derived from text.

### Stages, smallest first

Each stage is one PR into `feat/lorenzoscript` and gets its own ADR.

1. **Core parser and renderer** in `packages/lorenzoscript`: every row of the core table in §2, the security rules, and the shared test files.
2. **Standard extensions:** deletion, sub/superscript, tables, footnotes, abbreviations, attributes, class blocks, `{{TOC}}`, math.
3. **Lorenzo extensions:** entity links and images, `{{date}}`, `{{cal}}` (reserved), `references()`, the resolver interface, slugify.
4. **`packages/lorenzoscript-editor`**, plus a static demo page that opens from disk (`file://`, with a pre-bundled script since browsers block ES modules there) and uses a fake in-memory resolver. No API needed.
5. **apps/api slugs:** `entity_slug` and the batch resolve (§7).
6. **apps/inventory-web:** the editor on the item description, with a Lorenzo resolver built on the typed API client, entity images fetched with the viewer's token and shown through blob URLs, and dates in the locale from `/me`. Blocked on an endpoint that edits description text, which is being prepared separately (RFC 0015's payload write surface).
7. **Connections and backlinks:** `content_reference` and its read (§7).

## Not in scope

- WYSIWYG editing, and any rendering beyond HTML (Discord, plain text) — possible later consumers of the same tree.
- In-game calendar semantics — reserved syntax only, pending its own RFC after RFC 0026's time question.
- Homebrewery's page, column, and theme layout beyond `{{ }}` class blocks.
- Slug autocomplete in the editor, toggling task-list checkboxes from the rendered view, and incremental re-parsing.
- Cross-tenant references, e.g. into a repository ([RFC 0024](0024-repositories.md)).

## Consequences

- Existing plain-text descriptions render as LorenzoScript from the day an app adopts the renderer. Mostly this changes nothing; lines starting with Markdown markers change appearance.
- `apps/api` needs a second, narrower parser in Python (stage 7), kept honest only by the shared test files. That is the price of extracting references server-side instead of trusting clients.
- Slugs become load-bearing for content. Renaming or clearing one breaks every text that links to it until stage 7's reference table can find and flag them.
- Every app that renders LorenzoScript gets the same safe-by-construction output, and one place to fix a rendering bug.
- Math is limited to the documented subset. Anything outside it shows as code rather than pulling in KaTeX or MathJax.
