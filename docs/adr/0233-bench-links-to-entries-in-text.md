# 0233 - Bench: links to entries in text

Status: accepted, decided with the maintainer on 2026-10-09. The first part of slice W-C of [RFC 0042](../rfcs/0042-bench-workbench-interface.md): entry links and hover previews in LorenzoScript text. Builds on [ADR 0224](0224-bench-description-and-notes.md) (descriptions and notes), [ADR 0105](0105-lorenzoscript-entity-references-and-resolver.md) (entity references and the resolver) and [ADR 0107](0107-entity-slugs-and-batch-resolve.md) (resolving link names in one request).

## Context

The preview of a description or note rendered LorenzoScript with no resolver, so `[[Old Sword]]` and `[text](ashfang)` showed as plain text: an author could not tell a link that works from one that does not.

## Decision

- **Link names are looked up and remembered.** The slugs a text names (`references()`) go to `GET .../entities/resolve` in batches of 100, and what comes back is kept for the page: a preview that follows the typing asks only about names it has not seen. A name nothing holds is believed for 30 seconds, then asked about again, since an entry may be made or named any moment. A failed lookup is not remembered, and the text shows as plain text until it works.
- **The preview shows at once what is already known, and what is not when it arrives**, unless the text has moved on; so typing never waits on the network and a link appears as the name is completed.
- **A resolved link leads to the entry in this workbench**: its target is a fragment (`#entry-<id>`) that Bench turns into opening the entry, not a page. Pressing a link does not take the focus from the text, and what was typed is written down before going there, so it is not lost.
- **Pointing at a link, or reaching it with the keyboard, shows a card**: the entry's name, what it is and the start of its description (plain text, cut at a word). It never takes the focus, does not redraw the page, goes away with the pointer, the focus or Escape, and there is one at a time. Reading the entry for it is quiet: it does not redraw the page, which would drop the very focus or pointer being followed.
- **A name nothing holds is said**, under the preview: "Nothing is called “lost-crown” yet, so that link stays as text." Names of entries made here and not sent yet say this until they are sent and looked up again.
- A text is written down when its field loses focus, as before, now after the focus has moved: drawing the page again puts the focus back where it was, which is not where the person went. A link now keeps the focus when the page is drawn again, as a field does.
- The sample server gives each entry the link name of its name, so this runs without an API.

## Not here

- **Pictures** (`[alt](slug)` images) and the **image picker**: they need an entry's picture from the API, and the picker needs pictures to choose from; their own slice.
- **A picker for entries** (typing `[[` and choosing), and toolbar buttons that insert links.
- Links in text outside the editors (there is none yet).

## Consequences

- An author sees which links work, can follow them, and can look at what they lead to without leaving the text.
- The page asks the API for link names as texts are opened or typed, in batches, with a memory; a page full of texts costs a few requests.
