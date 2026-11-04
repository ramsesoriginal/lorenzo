# 0389 - The shared review element, in `packages/repo-ui`

Status: proposed, with slice S5 of [RFC 0036](../rfcs/0036-repository-tooling.md) for the maintainer's review, tracked in #984. Extracts the field block of [ADR 0203](0203-shelf-the-update-inbox.md) (the update inbox) and the values of [ADR 0254](0254-bench-status-bar-and-conflict-review.md) (Bench's conflict review) into one element. Part of the v1.0 row "Publish, subscribe, update screens"; B5 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) builds on it.

## Context

Two screens draw the same thing twice, each its own way. The hub's update inbox draws a row's changed fields (a label, what it was, what the repository has now and, where the library changed it too, what the library has) and asks, for a conflict, whether to keep the library's value or take the update. Bench's conflict dialog draws a conflicting command's field (what it was, what the person wrote, what the server has now) and asks the same question with two buttons. [RFC 0036](../rfcs/0036-repository-tooling.md) §2 decided that a shared element is extracted to `packages/repo-ui`, never into `apps/brand`, once a second consumer needs it, and named the review element as the first; [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) §5 and §9 say Bench's review "is the shared one", and B5 (stored bases, queued deletes) is meant to build on it rather than add a third copy. Bench is now that second consumer.

### What the two screens have in common

- A **field** that changed, named in the product's words ("Name", "Stat: Weight").
- Up to **three values**: what it was (the hub's base is the copy's snapshot at the last update; Bench's is the value the person saw when they wrote the command), what the other side has now, and what the host has itself. Each is already text by the time it is drawn (the hub's through [ADR 0197](0197-names-in-update-diffs.md)'s names, Bench's through `showValue`).
- A **choice** between two sides: keep the host's value, or take the other side's. Neither side is ever merged.
- A value that is **missing**. The hub says `(none)`; Bench says `nothing of its own (inherited)` for a stat with no value of its own, `none` for no parents and `no link name`; a value that was `undefined` reached the page as the word "undefined", which no one meant.
- A **set** (what an entry inherits from, a stat's choices): the hub shows what was Added and Removed, and [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) §5 compares Bench's sets element by element, so Bench will need the same.

### What differs on purpose

- **When a choice acts.** The hub collects choices and applies them at the end (a radio per field; Apply waits until every conflict has an answer, and a choice can be changed until then). Bench acts at once: pressing a side is the decision, it goes through the command layer's outbox, and the dialog redraws.
- **Where the base comes from.** The update has the copy's snapshot; Bench will have its stored bases (B5). The element takes a value and does not know.
- **What a screen has around a field.** The hub's row has a kind badge, a release mark, a breaking-change confirmation, Skip and Apply; Bench's card has a link to the entry and, for a refused change (no three values, a server's sentence), Try again and Discard. Those stay in their screens.
- **The words**, below.
- **Phone.** Bench drew the three values in three columns, side by side, which [RFC 0036](../rfcs/0036-repository-tooling.md) §2 rules out ("was, now and yours stack"). The hub already stacked them.

## Decision

### A package

**`packages/repo-ui`** (`@lorenzo/repo-ui`, TypeScript and CSS, source shipped like the other packages with no `build`, [ADR 0122](0122-api-client-package.md) and [ADR 0349](0349-the-entry-preview-package.md); no runtime dependencies; version 0.0.0 in release-please). It starts as one element with its own tests ([RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) §9). Own small TypeScript and plain DOM, no framework ([RFC 0036](../rfcs/0036-repository-tooling.md) §2). Its stylesheet, `@lorenzo/repo-ui/repo-ui.css`, uses brand tokens only and is held to the CSS guard ([ADR 0322](0322-calendars-and-sessions-share-a-header-and-the-brand-base.md)); both apps import it the way inventory-web imports the entry preview's.

### The data it takes

Plain data; the element never sees an API type, an id or a model. `renderReview(items, options)` returns one element holding a block per item.

```ts
type ReviewValue = string | { kind: 'empty' } | { kind: 'deleted' };   // EMPTY, DELETED
type ReviewChange =
  | { kind: 'value'; was: ReviewValue; theirs: ReviewValue; mine?: ReviewValue }
  | { kind: 'set'; added: string[]; removed: string[] };
type ReviewItem = {
  id: string;                                    // unique within the review; comes back in the callback
  label: string;                                 // "Name", "Stat: Weight"
  change: ReviewChange;
  note?: string;                                 // why it cannot be taken
  choice?: { chosen: 'mine' | 'theirs' | null }; // present: the person has to choose
};
```

- **A string is text, always.** It is set with `textContent`; nothing is ever parsed as markup, so a value, a name or a note that looks like HTML is shown as the characters it is. A test pushes markup through every place a string goes.
- **`empty` and `deleted`** are the two values that are not text: a field with no value ("No value") and something the other side removed ("Deleted"). Said as words, in the interface's own type and not the monospace of a value, so they cannot be mistaken for a value that reads the same; the words carry the meaning, never type or hue.
- **`mine` is optional.** Without it the host has no change of its own to weigh (a hub field the library did not touch): the block reads Was and Now. With it the block reads Was, Now, Yours. `choice` is separate from `mine` because a set can conflict too: the hub asks for a choice on a set field whose block has no Yours.
- **What is not in the shape**, because only one screen needs it or none yet does: a picture value (no screen can conflict on a picture until Bench's B8), an attachment (the hub's "parent added" rows are a sentence with their own buttons, not a field), a number type (a number is text by the time it is drawn), and anything about stored bases or queued deletes.

### Two modes, so neither screen needs the other's behaviour

`options.mode`:

- **`choose`** (the hub). The choice is a labelled radio group: a `fieldset` named by the field and the question, two native radios, `required`. The element holds no state of its own beyond the DOM; the host keeps what was chosen, passes it back as `chosen` when it draws again, and hears each change in `onChoose(id, side)`. The hub's own Apply reads its map.
- **`act`** (Bench). The choice is two native buttons in a group named for the field. Pressing one is the choice: `onChoose(id, side)` is where the host acts (`keepMine` or `discard` on the command layer), and it redraws as it already did. `chosen` is ignored.

`side` is `mine` (keep the host's value) or `theirs` (take the other side's). Which of those a host's own action means is its own: the hub maps `mine` to the API's `keep_local` and `theirs` to `take_upstream`; Bench maps them to `keepMine` and `discard`. Both modes also set a polite status line (`role="status"`) inside the element, so a screen reader hears what was chosen.

### The words, in one place

`REVIEW_WORDS` in the package is the one table, and `words` in the options overrides single entries. The defaults are the hub's, which are the words of [RFC 0036](../rfcs/0036-repository-tooling.md) §3 ("Was / Now / Yours") and [identity §14.3](../brand/identity.md):

| Entry | Default | Bench's override |
| --- | --- | --- |
| the value before | Was | |
| what the other side has | Now | Theirs |
| what the host has | Yours | Mine |
| a set | Added, Removed | |
| a missing value | No value | |
| a removed one | Deleted | |
| keep the host's | Keep yours | Keep mine |
| take the other side's | Take the update, and replace yours | Use theirs |
| the question over the radios | This is changed in your library too | |
| the buttons' group name | Choose for *field* | |
| what is said on a choice | Keeping yours for *field*. / Taking the update for *field*. | Keeping mine for *field*. / Using theirs for *field*. |

**Why two pairs remain.** Bench's entry pane has its own inline conflict row that says Mine, Theirs, Keep mine and Use theirs, its tests assert them, and [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) writes them; the hub's say Now, Yours, Keep yours and Take the update, and its tests assert them. Changing either on this slice would change a screen's words without a decision about the product's, and would leave Bench disagreeing with itself. So the table is one place and Bench overrides four entries; the terminology sweep ([#495](https://github.com/ramsesoriginal/lorenzo/issues/495), [ADR 0194](0194-user-facing-terminology.md)) settles one pair and deletes the override. What does change, because the element says it once: a missing value reads "No value" in the hub (it read "(none)") and in Bench a value that was `undefined` reads "No value" (it read "undefined"); Bench's values read Was, Theirs, Mine in the hub's order (they read Was, Mine, Theirs).

**Accessibility, [identity §15](../brand/identity.md).** Native radios and buttons, each with a text name; the group named by the field and the question (radios) or by the field (buttons); no meaning by hue or type alone; a visible focus ring from the brand token; 44px targets at phone width and for a coarse pointer; nothing moves, so there is no motion to reduce.

**Phone, [identity §8.5](../brand/identity.md).** A term beside its value on a desk and above it below 720px, one column, a long value wrapping instead of widening the page. The class names are prefixed `repo-review` so that they cannot meet an app's own `review` classes (Bench has them).

### The two screens

- **Hub.** `updatesView.ts` draws a row's fields through `renderReview` in `choose` mode; `lib/updateReview.ts` turns a `FieldView` into an item (pure, unit-tested), and the field template and its two stylesheet rules are gone. Behaviour is unchanged: the radio batch, Apply waiting for every conflict, the release marks, the breaking-change confirmation and the clash cards are the hub's. `tests/real-api/updates.spec.ts` passes as it was, except the phone test's selector for pressed controls, which gains `.repo-review-option` (the conflict radios were `.field-row`).
- **Bench.** `conflictDialog.ts` draws a conflict through `renderReview` in `act` mode with Bench's words; `shell/conflictReview.ts` turns a command into an item (pure, unit-tested). The card keeps the link to the entry; a refused change keeps Try again and Discard. Behaviour is unchanged: `keepMine`, `discard`, the outbox, retry, and the dialog following the outbox.

### Tests

The package has unit tests for the words and the rows (pure, under Node) and DOM tests under jsdom: every kind of value, every state, both modes, the callback, controls that are native and in the tab order, several reviews on one page, and text that looks like markup. jsdom is a development dependency of this package alone, the first DOM environment in the repository (the other packages' drawing is covered by their apps' browser tests); the choice is a question below. The hub's real-API tests and Bench's browser tests cover the same element in a real page, with the keyboard and at 375px.

## Not in scope

- **Bench's stored bases and queued deletes** (B5, [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md)): the element draws whatever base it is given; where Bench keeps it, the set compare and "pending, confirm on sync" are B5's. `deleted` is in the shape for them.
- **Bench's inline conflict row** in the entry pane (a sentence with two buttons and no Was), which is a different, smaller view of the same conflict.
- **A picture value, an attachment row, a number type,** and any change to the API.
- **One pair of words for every screen** (#495).

## Consequences

- A conflict reads the same in the hub and in Bench, and [identity §14.3](../brand/identity.md)'s sentence "shown with the same three-way view as an update" is true of the code.
- B5 adds stored bases and a set compare to Bench without a third copy of the layout, and a change to the review's look or its words is made once.
- The hub and Bench each gain a workspace dependency on it, and both rebuild when `packages/repo-ui` changes (Pages watch paths and the CI graph say so).
- Bench's dialog is one column on a phone, which it was not.
- The first DOM test environment enters the repository as a development dependency.

## Follow-ups and questions

- **Which pair of words?** Yours and Now with Keep yours and Take the update, or Mine and Theirs with Keep mine and Use theirs, for every screen: [#495](https://github.com/ramsesoriginal/lorenzo/issues/495). Until then Bench overrides.
- **Should the entry pane's inline conflict row use the element?** It would gain Was and one set of words, at the cost of a bigger block inside the entry; it is B5's to decide with the stored bases.
- **jsdom for the package's DOM tests.** The alternative is to cover the drawing only in the apps' browser tests, as the other packages do.
