# 0526 - The entity parts package

Status: accepted and built, in three stacked pull requests (below), asked for by the maintainer after [ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md) ("The copies stay copies while each app moves; extraction follows"). It moves the page parts that `apps/beings` and `apps/inventory-web` both draw about one entry into `packages/entity-parts`, in three small pull requests.

## Context

Both apps were written to draw the same few things about an entry: a tag editor, a link name editor, a description written in a form, the form itself, the facts about an entry and a Fact's page, and the list of libraries. They were copied from one app to the other when the second needed them, which is what [adding a package](../guides/adding-a-package.md) says to do until there is a second consumer; there are two now, and the move of both into the web shell ([ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md)) is finished, so what each app still draws of its own is known.

Measured, the two apps carry about 1,170 lines each of the same parts, and they have drifted only in small, nameable ways:

| Part | Where the two copies differ |
| --- | --- |
| `TagEditor`, `DescriptionEditor` | Not at all (the Astro templates and `lib/tagEditor.ts` are byte for byte the same) |
| `SlugEditor`, `lib/slugs.ts` | Words: "slug" in Inventory, "link name" in Beings, and one error message |
| `InfoForm` | Beings passes an `extra` slot for a note's audience |
| `DescriptionEdit` | Inventory hands it an item and asks whether the item has a text of its own; Beings hands it a name and a boolean. The label is "Display title" or "Heading" |
| `Facts`, `FactPage` | "this item" or "this being"; Beings' Fact page links to "Where it appears" |
| `LibraryList` | Where each library links: `/board/` or `/beings/` |
| `lib/information.ts`, `lib/tagEditor.ts` | Not at all |

What they depend on is each app's own: its authenticated client (`lib/api.ts`, with the viewer's token), the function that draws LorenzoScript text with the app's own link resolution (`lib/descriptions.ts`), and how a protected picture is read (`blobUrl`). The parts themselves are plain DOM over an Astro template.

## Decision

- **One package, `packages/entity-parts`** (`@lorenzo/entity-parts`, TypeScript and Astro, source only, no build, like `app-shell` and `stat-values`). It holds the parts above, the Astro template of each, and the logic they share: the tag states and the writes of `lib/tagEditor.ts`, the link name's rules and writes of `lib/slugs.ts`, and the information reads and writes of `lib/information.ts`. It has no domain of its own and imports no app.
- **What an app brings is given once, not copied.** The package exports `createEntityParts(context)`, where the context is the app's `client`, a `renderer` (how LorenzoScript text is drawn), `blobUrl` (how a protected picture is read) and the words the app uses (`slug` or `link name`, `item` or `being`, where a library links). Each app has one small file, `lib/entityParts.ts`, which calls it and exports the parts bound to the app, as `lib/statValues.ts` binds `@lorenzo/stat-values`. The call sites in each app change their import, not their calls.
- **The Astro templates take the words as props** (`<SlugEditor label="Link name" />`), so the package owns the markup and the app owns the wording.
- **The two shapes of `DescriptionEdit` become one**: it takes `{ entityId, name, hasDescription }`, which is what Beings passed; Inventory computes `hasDescription` from the item (`hasOwnText`) where it calls it.
- **What stays in the apps**: `errorMessage` and `statLabel` (copied in these two apps) and `statusLine` and `template` (these two and the account hub). They are not about an entry, so they are not a reason for this package: a package of them would be the grab-bag [adding a package](../guides/adding-a-package.md) warns of. The package carries its own small private copies of what its parts need, under `src/internal`, until where those belong is settled in a decision of its own.
- **Three pull requests, each leaving both apps green**, stacked on the one before:
  1. The package and the parts that are the same in both: `TagEditor` and `DescriptionEditor`, with `createEntityParts` and its context.
  2. `SlugEditor`, `InfoForm` and `DescriptionEdit`, with the link name's rules and the information reads and writes.
  3. `Facts`, `FactPage` and `LibraryList`.

  Each removes the app's copies and runs the end-to-end specs of both apps.

## Consequences

- About 2,300 lines of copies in two apps become one set of parts, and a change to one of them is one change, tested in both apps.
- The apps' words stay theirs. A third app that wants the parts passes its own context.
- `errorMessage`, `statLabel`, `statusLine` and `template` stay copied until their own decision; this ADR does not settle where they go.
- A change to the package runs the end-to-end suites of both apps in CI ([ADR 0148](0148-dependency-aware-pr-ci.md)), as the apps list it as a `workspace:*` dependency.
