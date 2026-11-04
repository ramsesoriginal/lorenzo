# @lorenzo/repo-ui

The elements the repository screens share ([RFC 0036](../../docs/rfcs/0036-repository-tooling.md)
§2: a shared element is extracted when a second consumer needs it). It holds one so far, the
**three-way review of a change** ([ADR 0389](../../docs/adr/0389-the-shared-review-element.md)):
a field that changed, with what it was, what the other side has now and, where the host changed it
too, what the host has, and the choice between the two. The hub's update inbox
([ADR 0203](../../docs/adr/0203-shelf-the-update-inbox.md)) and Bench's conflict view
([ADR 0254](../../docs/adr/0254-bench-status-bar-and-conflict-review.md)) draw their fields with it.
No framework and no dependencies; it ships TypeScript source and a stylesheet, as the other packages
do.

The element takes plain data. The host turns whatever it holds (an update's rows, a device's queued
commands) into text first, so the package never sees an API type or an id.

```ts
import '@lorenzo/repo-ui/repo-ui.css';
import { EMPTY, renderReview, type ReviewItem } from '@lorenzo/repo-ui';

const items: ReviewItem[] = [
  {
    id: 'name', // comes back in onChoose; unique within one review
    label: 'Name',
    change: { kind: 'value', was: 'Longsword', theirs: 'Longsword +1', mine: 'My blade' },
    choice: { chosen: null }, // ask: `chosen` is what is picked now, or null
  },
  { id: 'slug', label: 'Link name', change: { kind: 'value', was: EMPTY, theirs: 'sword' } },
  { id: 'parents', label: 'Inherits from', change: { kind: 'set', added: ['Weapon'], removed: [] } },
];

// Radios the host reads later and applies once (the hub):
panel.append(renderReview(items, { mode: 'choose', onChoose: (id, side) => remember(id, side) }));

// Two buttons that act at once; the host does the work in onChoose and draws again (Bench):
dialog.append(renderReview(items, { mode: 'act', onChoose: (id, side) => act(id, side) }));
```

- **Values** are a string (shown as text, never as markup), `EMPTY` (the field has no value, said
  "No value") or `DELETED` (the other side removed it, said "Deleted"). A set shows what was Added
  and Removed.
- **Choice**: an item with `choice` asks. `choose` draws a labelled radio group (a fieldset named by
  the field and the question) and tells the host each change; `act` draws two buttons in a named
  group and the press is the choice. A host owns what a side means: keeping the host's value is
  `mine`, taking the other side is `theirs`.
- **Words** are in one table, `REVIEW_WORDS`: Was, Now, Yours, Added, Removed, No value, Deleted,
  Keep yours, Take the update, and replace yours, the question over the radios and what a screen
  reader hears when a side is chosen. A host passes `words` for the ones it says differently (Bench
  says Mine, Theirs, Keep mine and Use theirs).
- **Accessibility**: native radios and buttons, a text name on every control, the value kinds told
  apart by their words and not by type or hue, a visible focus ring, 44px targets at phone width and
  for a coarse pointer, and a polite status line for a screen reader. Nothing moves, so there is no
  motion to reduce.
- **Phone**: one column below 720px with the values stacked, and a long value wraps.

Stored bases and queued deletes are Bench's work on top of this (RFC 0039 B5) and are not here.

`mise run //packages/repo-ui:test` covers the words, the rows, the stylesheet and the drawing (a jsdom
DOM test: every kind of value, both modes, the callback, keyboard-reachable controls and text that
looks like markup). The two screens' own browser tests cover it in a real page.
