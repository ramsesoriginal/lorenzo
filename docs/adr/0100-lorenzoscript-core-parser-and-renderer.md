# 0100 - LorenzoScript core: `packages/lorenzoscript` parser and renderer

Status: accepted

## Context

[RFC 0027](../rfcs/0027-lorenzoscript.md) defines LorenzoScript and splits it into seven stages. This ADR decides stage 1: the package itself, its syntax tree, and the core syntax (the RFC's §2 core table), with the security rules of §5 and the shared test files of §6. Extensions, entity references, and the editor come in later stages and extend what this one builds.

It is the repo's first package with real code and tests. `packages/brand` ([ADR 0098](0098-branding-css-app-and-package.md)) only copies files, and CI's `discover` job only looks for `apps/*/mise.toml`, so a package's tests would never run in CI today.

## Decision

### Package

- `packages/lorenzoscript`, published in the workspace as `@lorenzo/lorenzoscript`: `private`, versioned by release-please like `packages/brand`.
- No runtime dependencies. Dev dependencies are the ones the apps already use: TypeScript, Biome 2, vitest.
- **No build step.** `exports` points straight at `src/index.ts`. Every consumer in this repo already compiles TypeScript (Astro/Vite, vitest, tsup), and stage 4's demo bundles with esbuild. Shipping source keeps the package to what it actually is.
- `mise.toml` has the usual `install`/`dev`/`lint`/`format`/`test` tasks, and no `build`: there's nothing to emit, and `lint` already runs `tsc --noEmit` after Biome.
- CI's `discover` finds `packages/*/mise.toml` too, so `packages/brand` also joins the matrix; its tasks are already no-op echoes. pre-commit gains Biome and `tsc` hooks for the package, matching `apps/loot-bot`'s.

### API

```ts
parse(source: string): Document   // syntax tree, plain data
render(doc: Document, options?: RenderOptions): string   // HTML
```

`RenderOptions` has one field for now: `externalImages` (default `true`). When set to `false`, every image renders as its alt text. Stage 3 adds `resolve`.

The syntax tree is a discriminated union: block nodes `paragraph`, `heading`, `blockquote`, `list` (holding `item`s with a `checked` flag for task items), `code`, `rule`; inline nodes `text`, `codespan`, `em`, `strong`, `i`, `b`, `link`, `image`, `break`. Later stages add node types. They don't change existing ones.

### Parsing

- **Two passes: blocks, then inlines.** Before parsing, line endings are normalized, leading tabs are expanded to 4-column stops, and NUL becomes U+FFFD.
- **Containers are parsed by collecting their lines, stripping the container's marker or indent, and recursing.** A blockquote collects its `>` lines, and a list item collects the lines indented to its content column. This is simpler than CommonMark's single-pass container stack.
- **Lazy continuation.** An unmarked, unindented line still belongs to the quote or item it's in if the line before it was paragraph text, judged with its nested quote and list markers set aside. That's tracked line by line as a container collects its lines. The first implementation re-parsed the collected lines to ask whether they ended in a paragraph, and that turned out to be exponential in nesting depth: five nested quotes with a thousand lazy lines never finished.
- **Nesting limit.** Blocks and inline elements each nest at most 32 deep (`MAX_NESTING`), and anything deeper stays text, like markdown-it's `maxNesting`. Every consumer of the tree recurses, and text is written by one user and rendered in another's browser, so a hostile description must not be able to exhaust the stack. Before the limit, 5,000 nested `>` did. Container depth is counted during the block pass; inline depth is recorded per node as spans are built.
- **List items and indentation.** An item's content column is where its text starts (2 after `-` and a space, 3 after `1.` and a space), capped at 4. So both the RFC's "indent by 4" and the CommonMark-usual 2/3 continue an item.
- **Loose and tight lists.** A list is loose if a blank line separates two of its items, or two blocks directly inside one item; tight lists drop `<p>`. The recursion reports this per level, so a blank line inside a nested list doesn't loosen its parent.
- **Block rules are an ordered internal table**, so later stages can add tables, footnotes, `{{ }}` blocks and `$$` math next to these without restructuring. It isn't a public plugin API.
- **Inline emphasis** uses CommonMark's delimiter-run algorithm, including its flanking rules, its rule of 3, and its "openers bottom" so a closer never rescans openers already known not to fit. Output is built as a stack, so a match only ever cuts its tail: linear time. (Splicing matches into the middle of an array, the first version, took minutes on a megabyte of `*a*a*a`.) What each run length produces (`*` → `em`/`strong`, `_` → `i`/`b`) is kept in a per-character table, so stage 2's `~` and `^` are new rows, not new code.
- **Inline links** use a bracket stack, and links can't contain links.
- **Code spans** follow CommonMark (matching backtick runs, one space trimmed from each end). So do autolinks: `<scheme:…>`, and `<a@b.c>` becoming `mailto:`.

### Rendering

HTML5 output (`<br>`, `<hr>`) with every piece of text and every attribute escaped. The URL rules from RFC 0027 §5 are enforced here and nowhere else:

- Links are only for `http`, `https`, `mailto`, or `#fragment`, and a fragment is rewritten to the `ls-` id prefix.
- Images are only for `https`.
- Anything else renders its text content, not a link.

Code block languages are kept only if they match `[\w+#.-]+`, as `class="language-…"`. Task items render a disabled checkbox inside `<li class="ls-task">`.

### The spec is the test suite

RFC 0027 §6 originally named separate `spec/**/<case>.md`/`.html` files. Instead, `packages/lorenzoscript/SPEC.md` embeds its examples the way CommonMark's own `spec.txt` does: a fenced block with info string `example`, where source and expected HTML are separated by a line containing a single `.`. Stage 3 adds a third section for expected references. `␠` stands for a trailing space and `⇥` for a tab, so the repo's trailing-whitespace hook can't silently change an example. (Stage 1 used CommonMark's `→` for tabs, until stage 2's math rendered `\to` as a real `→`; no example had used it for a tab.) One vitest file runs every example. Stage 7's Python extractor reads the same file. The documentation and the tests can't drift, because they are the same file.

## Not in scope

Everything in RFC 0027's extensions table, entity references, the resolver, and the editor: stages 2–4. Plus the CommonMark deviations the RFC already lists (raw HTML, setext headings, reference links, entity references).

## Consequences

- One source of truth for LorenzoScript's behaviour, readable as documentation and executed as tests.
- Consumers must compile TypeScript. Every current one does; a plain-JS consumer would need a build step added then.
- The collect-and-recurse block parser rescans a nested container's lines once per nesting level. With the nesting limit, that's at most 32 passes.
- Hostile input is covered by tests next to the example runner: 5,000-deep quotes and emphasis, and lazy lines in nested quotes. A regression there fails or visibly hangs CI rather than a reader's browser tab.
- Lazy continuation judged from the previous line alone misses rare CommonMark corners (a paragraph continuation line indented 4 or more, inside a quote, followed by a lazy line). SPEC.md lists this as a deviation.
- CI now tests packages as well as apps. `packages/brand` joins the matrix with its no-op tasks.
