# 0349 - The entry preview as a package

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 5. Moves the card of
[ADR 0264](0264-link-previews.md) out of inventory-web; the endpoint and its visibility rules are
unchanged.

## Context

The hover and focus card of ADR 0264 lives in `apps/inventory-web`: a small state machine for when it
opens and closes, a cache of cards per page, the words under a card's name, and a renderer that draws
the card, places it, and wires the document's pointer, focus, key and touch events. Lorenzo Maps now
has marks and list rows that name entries and want the same card (ADR 0340 left it for this slice),
and RFC 0048 decided the card is extracted before it is used a second time rather than copied.

## Decision

**A package, `packages/entry-preview`** (`@lorenzo/entry-preview`, TypeScript, source shipped like the
other TypeScript packages, no dependencies). It holds what is not specific to one app:

- `createPreviewState(open, close, timers?)`, the timing of ADR 0264 unchanged: a pointer resting on a
  trigger opens the card after 300 ms, leaving closes it after 150 ms that coming back to the trigger
  or onto the card cancels, focus opens and blur closes at once, Escape closes, a tap opens it and a
  second tap on the same trigger follows it.
- `createCardCache(fetchCard)`: one request per entry for the page, a 404 remembered as "no card",
  any other failure forgotten so the next hover asks again.
- `kindLabel(kinds)` and `statText(stat)`: the one word under a name in the words of the product
  (Character, Being, Inventory item, Item, Location, Map, else Entry), and a stat as "weight 3".
- `installEntryPreview(options)`, which draws the card and listens on the document. It is given what
  is app-specific and nothing else:
  - `selector`: which elements open a card;
  - `targetOf(element)`: the library and entry an element stands for, or `null` for none;
  - `loadCard(tenant, id)`: the card as the API's preview route gives it, or `null`;
  - `loadPicture(url)`, optional: how a protected picture becomes something an `<img>` can show;
  - `touch`, `"two-taps"` (the first tap on a trigger shows its card and does not follow it, as in
    ADR 0264) or `"off"` (a tap acts as a click does).
  It returns `{ destroy() }`, which removes every listener and the card.
- `EntryCard`, the shape of the API's `LinkPreviewOut`, declared in the package so that it needs no
  generated client; an app passes `loadCard` and the types meet there.

**The card is drawn as before**: a `role="tooltip"` over the page, taking no focus and no controls,
linked to its trigger with `aria-describedby` while open, kept open while the pointer is on it
(WCAG 1.4.13), put away on scroll and on Escape with focus left where it was, and dropped if it
arrives after it was closed or after its trigger left the page. It is placed under its trigger, above
it when there is no room, inside the window. The trigger may be an HTML element or an SVG one.

**Its stylesheet ships with it** (`@lorenzo/entry-preview/entry-preview.css`), brand tokens only and
checked by the brand CSS guard. The classes are renamed from `link-preview*` to `entry-preview*`, and
the card's one visual change is that it has a border and no drop shadow, as the guard requires of
every brand surface.

**What stays in an app**: the choice of triggers and how they name an entry. inventory-web keeps
`previewTarget` (a link of a rendered description names its library and entry in its address) and
its wiring (`.ls-content a.ls-entity`, the API client, the authenticated picture loader). Bench keeps
its own card, drawn from the data it mirrors ([ADR 0233](0233-bench-links-to-entries-in-text.md)),
and does not use the package.

## Validation and delivery

The state machine, the cache and the labels keep the unit tests they have in inventory-web, moved with
the code, and gain the Location and Map words. The DOM wiring is covered where it runs: inventory-web's
existing end-to-end tests of the card pass unchanged but for the renamed class and element id, and
Lorenzo Maps adds its own (ADR 0350). The package's stylesheet passes the CSS guard. Nothing in the
API changes in this ADR.

## Excluded

A card for Bench, a second visual design, links or controls inside the card, a card for something that
is not an entry, caching a card across page loads, and any change to what the endpoint returns (ADR
0350).
