# @lorenzo/lorenzoscript

LorenzoScript is Lorenzo's Markdown dialect for description text: a zero-dependency parser and HTML renderer. The design is in [RFC 0027](../../docs/rfcs/0027-lorenzoscript.md), [ADR 0100](../../docs/adr/0100-lorenzoscript-core-parser-and-renderer.md) (core), [ADR 0102](../../docs/adr/0102-lorenzoscript-standard-extensions.md) (tables, footnotes, attributes, class blocks, math, …) and [ADR 0105](../../docs/adr/0105-lorenzoscript-entity-references-and-resolver.md) (entity links, dates, the resolver). What the syntax actually does is defined in [SPEC.md](SPEC.md), whose examples are also the test suite.

```ts
import { parse, references, render } from '@lorenzo/lorenzoscript';

const doc = parse(source);
// Everything to look up first: entity links and images by slug, dates, calendar dates.
const refs = references(doc);
const found = await lookUp(refs); // one batched request, as the viewer
element.innerHTML = render(doc, {
  locale: viewer.locales,
  resolve: {
    entity: ({ hint, slug }) => found.link(hint, slug), // { href, title } or null
    image: ({ slug }) => found.picture(slug), // { src } (e.g. a blob: URL) or null
  },
});
```

Without a resolver, entity references render as their plain text. Unresolved ones do too, so a reader can't tell a missing entity from one they may not see.

`render`'s output is built only from the syntax tree, with every piece of text escaped, so assigning it to `innerHTML` is safe. The resolver's URLs are checked as well. Pass `{ externalImages: false }` to render ordinary (non-entity) images as their alt text.

For styling, the renderer's own classes all start with `ls-`:

- `ls-entity`: resolved entity links and images
- `ls-cal`: calendar dates
- `ls-task`: task-list items
- `ls-toc`: the `{{TOC}}` nav
- `ls-footnotes`, `ls-fnref`, `ls-backref`: footnotes
- `ls-math`: TeX shown as code because it's outside the supported subset

Author ids are rendered as `ls-<id>`. Author classes (`{.class}`, `{{.class …}}`) are rendered as written.

`slugify` is exported too: it's the rule `[[Name]]` and heading ids use, for anything that needs to suggest a slug from a name.

The package ships TypeScript source (no build step), so consumers need a bundler that compiles it; every app in this repo already has one. Internal to this workspace, not published.

```bash
mise run //packages/lorenzoscript:test   # SPEC.md's examples, plus hostile-input checks
mise run //packages/lorenzoscript:lint   # Biome + tsc --noEmit
```

Adding syntax means adding its examples to `SPEC.md` first.
