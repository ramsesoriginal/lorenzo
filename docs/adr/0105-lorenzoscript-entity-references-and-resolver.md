# 0105 - LorenzoScript entity references, dates, and the resolver

Status: accepted

## Context

[RFC 0027](../rfcs/0027-lorenzoscript.md) stage 3 is where LorenzoScript meets Lorenzo: links and images that name entities by slug, `{{date}}`, and a reserved `{{cal}}`. The RFC's §3 decided the syntax and the visibility rule; §4 decided that rendering stays synchronous, with resolution done up front by the caller. This ADR decides the syntax tree additions, the resolver interface, what `references()` returns (stage 7's Python extractor must produce exactly the same), and how the spec's examples test all of it without a real API.

Numbered past 0101–0104, claimed by other branches' open PRs at the time of writing.

## Decision

### Entity references are links and images with a `ref`

An entity link is a `link` node with a `ref: { hint, slug }`, and an entity image is an `image` node with one. It isn't a new node type, so every existing path (nesting, attributes, `plainText`, "no links in links") applies unchanged. `hint` is `''` when absent.

- `[text](target)` and `![alt](target)` carry a `ref` when `target` matches `(hint/)?slug`, with hint `[a-z_]+` and slug `[A-Za-z0-9][A-Za-z0-9_-]*` (RFC §3). A URL with a scheme, or starting with `/`, `.`, `#`, or `?`, can't match. The slug is used exactly as written: it's an explicit key.
- `[[Target]]`, `[[Target|text]]`, and `[[hint/Target]]` are wikilinks. Their target is a *name*, so its slug is `slugify(name)`: the same function heading ids use (ADR 0102), so `[[Old Sword]]` finds `old-sword`. The link text is the alias, else the name without its hint. It's plain text: no markup inside `[[…]]`. A name with no slug (`[[日本]]`) isn't a wikilink and stays text, brackets included.

### The resolver

`render(doc, { resolve, locale })`. `resolve` holds optional, synchronous lookups over data the caller already fetched:

```ts
entity?: (ref) => { href: string; title?: string } | null
image?: (ref) => { src: string; title?: string } | null
calendar?: (expression: string) => string | null
```

- **Resolved.** An entity link renders as `<a class="ls-entity">`. Its title is the author's, else the resolver's (the entity's name, typically). An entity image renders as `<img class="ls-entity">`. `externalImages: false` doesn't apply, since the image isn't external.
- **Unresolved, or no resolver.** An entity link renders its text, and an entity image its alt text. It is deliberately indistinguishable from plain text: marking it would tell a player that the text links to *something* they aren't allowed to see (RFC §3). An editor wanting to flag broken links for the author does so from `references()` and its own lookups, not from the rendered HTML.
- **The resolver's URLs are checked too, as defence in depth.** Links may be relative (`/`, `?`, `#`) or `http(s)`. Images may be `https:`, `blob:` (what an app gets from fetching a picture with the viewer's token), or relative. Anything else counts as unresolved.

### Dates and calendar dates: the first inline directives

`{{name args}}` inside a paragraph is an inline directive, and the name is case-insensitive:

- `{{date YYYY-MM-DD}}`, a real calendar date, becomes a `date` node, rendered as `<time datetime>` in the viewer's `locale` (`Intl.DateTimeFormat`, `dateStyle: 'long'`, in UTC so a date never shifts by a time zone). An invalid date, or an unusable locale, falls back to the text as written, or to the runtime's own locale, respectively.
- `{{cal expression}}` becomes a `calendar` node, rendered as `<span class="ls-cal">`, with the resolver's text if `calendar` returns one, else the expression itself. What a calendar is stays out of scope, pending RFC 0026's time question.
- Any other name, or a directive without arguments, is text. `{{TOC}}` stays the one block directive.

### `references(doc)`

`references(doc)` returns every entity link, entity image, date, and calendar expression in the document, footnotes included. It's in order of first occurrence and de-duplicated, as `{kind: 'entity' | 'image', hint, slug}`, `{kind: 'date', date}`, or `{kind: 'calendar', expression}`. An app batch-resolves exactly these before rendering; stage 7 stores them.

`allBlocks()`, one depth-first walk, replaces stage 2's `headings()`, so ids, `{{TOC}}`, and `references()` can't disagree about what's in a document.

### Testing it without an API

SPEC.md's examples all render with a fixed `locale: 'en-GB'` and a small fixture resolver, both described in SPEC.md itself. Examples may add a third section, after another `.` line: the JSON that `references()` must return. That section is what stage 7's Python extractor is tested against.

## Not in scope

- The real resolver: stage 6 builds inventory-web's against stage 5's batch endpoint.
- Times of day, date ranges, or partial dates in `{{date}}`.
- Calendar semantics.
- Obsidian's `![[embed]]`.
- Flagging unresolved links in rendered output.

## Consequences

- A relative link like `[notes](page-2)` is now an entity reference. It renders as its text unless a slug `page-2` resolves, which matches RFC §3's "Lorenzo content has no relative URLs".
- Slugs from `[text](slug)` are case- and character-exact, while `[[Name]]` slugs are always lowercase and hyphenated. Stage 5 decides whether the API enforces one shape; if it does, the explicit form simply finds nothing for other shapes.
- Renaming a slug breaks the links that use it. `references()` is what stage 7 will use to find them.
- Stage 1 and 2 examples are unaffected: without a match in the fixture, everything renders as before.
