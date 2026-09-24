# @lorenzo/lorenzoscript

LorenzoScript is Lorenzo's Markdown dialect for description text: a zero-dependency parser and HTML renderer. The design is in [RFC 0027](../../docs/rfcs/0027-lorenzoscript.md) and [ADR 0100](../../docs/adr/0100-lorenzoscript-core-parser-and-renderer.md). What the syntax actually does is defined in [SPEC.md](SPEC.md), whose examples are also the test suite.

```ts
import { parse, render } from '@lorenzo/lorenzoscript';

element.innerHTML = render(parse(source));
```

`render`'s output is built only from the syntax tree, with every piece of text escaped, so assigning it to `innerHTML` is safe. Pass `{ externalImages: false }` to render images as their alt text.

The package ships TypeScript source (no build step), so consumers need a bundler that compiles it; every app in this repo already has one. Internal to this workspace, not published.

```bash
mise run //packages/lorenzoscript:test   # SPEC.md's examples, plus hostile-input checks
mise run //packages/lorenzoscript:lint   # Biome + tsc --noEmit
```

Adding syntax means adding its examples to `SPEC.md` first.
