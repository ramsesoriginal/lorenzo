# 0252 - LorenzoScript: a stat in a text, `{weight}`

Status: accepted

## Context

The Bench prototype shows "A sword weighs 1.5 kg" with the value as a chip that can be stepped with − and +. The prototype wrote it as `{weight}`, hard-wired to three stats, which no RFC or spec had. LorenzoScript's attributes are only `{#id .class}`, so a braced word that starts with a letter cannot be mistaken for one. The maintainer chose the form and its details (2026-10-10).

## Decision

- **`{name}` is a stat of the entry the text belongs to.** `name` is the slug of the stat's name, lowercased and hyphenated (`{weight}`, `{hit-points}`), and starts with a letter, so `{#id}`, `{.class}` and `a{3}` are never one. It is an inline node `{type: 'stat', name}` that can take trailing attributes like any other (`{weight}{.big}`). Same-named stats in two groups: the first wins.
- **It resolves like `my/`:** the renderer asks `resolve.stat(name)`, which answers with the text to show and a title (and optional classes), from the entry the text belongs to. A name nothing resolves, or an entry with no value for it, renders **as written**, so an author notices. The package knows nothing of Lorenzo's stats.
- **It is not a reference.** Nothing about it is stored, `references()` never returns one, `content_reference` is unchanged, and the API's extractor needs only to read it as the same token (its Python parser now does, so emphasis and nesting come out as in TypeScript). A new `statNames(doc)` lists the names a text uses, once each, for a caller that must fetch values first.
- **`SPEC.md` has the examples,** which both parsers run: the TypeScript ones render them against a fixture stat, the Python ones check that no references come out.
- **Bench draws a chip** (a pill; dashed when the value is only inherited) with the entry's value, and a number stat shows − and + on hover or focus: whole numbers step by 1, decimals by 0.1; tags, choices and text do not step. A step is an ordinary `stat.set` command on the entry the text is about, so it is undone with Undo and waits offline. The value follows changes that have not been sent yet.
- **inventory-web** shows the value as plain text, read from the entry's detail (once per entry, kept 30 seconds like `my/`). Anywhere nothing resolves it, the text keeps `{weight}`.

## Consequences

- A stat named like a word in prose (`{weight}` typed on purpose to mean the word) is read as the stat; escape the brace (`\{weight}`) for the word.
- Units are not part of a value: write them in the text (`{weight} kg`).
