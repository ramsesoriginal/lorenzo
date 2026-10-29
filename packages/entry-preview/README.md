# @lorenzo/entry-preview

The card an entry opens when something that names it is hovered, focused or tapped
([ADR 0349](../../docs/adr/0349-the-entry-preview-package.md), after
[ADR 0264](../../docs/adr/0264-link-previews.md) and
[ADR 0350](../../docs/adr/0350-location-and-map-previews.md)). It draws what the API's preview route
returns and decides nothing about what an entry is: which elements are triggers, which entry an element
stands for and how a card and a picture are fetched are the app's. No dependencies; it ships TypeScript
source and a stylesheet, as the other packages do.

```ts
import '@lorenzo/entry-preview/entry-preview.css';
import { createCardCache, installEntryPreview } from '@lorenzo/entry-preview';

const loadCard = createCardCache(fetchCardFromTheApi, (error) => isNotFound(error));

const preview = installEntryPreview({
  selector: '.m-mark[data-entry]', // what opens a card
  targetOf: (el) => ({ tenant, id: el.getAttribute('data-entry') ?? '' }),
  loadCard,
  loadPicture: (url) => fileAsObjectUrl(url), // optional
  touch: 'off', // or 'two-taps' (the default): the first tap shows the card, the second follows
});

preview.destroy();
```

- **Timing** (`createPreviewState`): resting on a trigger opens the card after 300 ms; leaving closes it
  after 150 ms, which coming back to the trigger or onto the card cancels; focus opens and blur closes
  at once; Escape closes.
- **The card** is a `role="tooltip"` with `aria-describedby` from its trigger, inside `main`, taking no
  focus. It follows its trigger when the page scrolls and goes when the trigger leaves the window.
- **Words**: `kindLabel` (Character, Being, Inventory item, Item, Location, Map, else Entry) and
  `statText`.
- **Cache**: `createCardCache` asks once per entry for the page, remembers a missing entry, forgets
  any other failure.

`mise run //packages/entry-preview:test` covers the timing, the cache, the words and the stylesheet.
The drawing and the listeners are covered by the end-to-end tests of the apps that use it
(inventory-web's links, Maps' marks and list rows).
