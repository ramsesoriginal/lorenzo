// The places of a library that are not on this Map yet (MP4, screen 12): found by name, each with a
// Place button, and each can be dragged onto the Map. The button is the keyboard's way of the same
// thing: it puts the entry where the view is centred. Only for a writer, and only while the tools are on.

import { el, field, icon, say, statusLine } from './dom';
import { findEntries } from './map-api';

export type Entry = { id: string; name: string };

/** What a drag carries, and where a drop reads it. */
export const DRAG_TYPE = 'application/x-lorenzo-place';

export function createOutliner(options: {
  tenant: string;
  /** Ids of what is on the Map now. */
  placed: () => Set<string>;
  /** Puts an entry on the Map at the middle of what is seen. */
  place: (entry: Entry) => Promise<void>;
}) {
  const root = el('section', '', 'stack-tight map-outliner');
  const search = field('Search entries');
  search.input.type = 'search';
  const list = el('ul', '', 'list map-outline-list');
  const status = statusLine();
  const hint = el('p', 'Drag an entry onto the Map, or press Place.', 'status-text');
  root.append(search.label, list, hint, status);
  let sequence = 0;

  async function refresh() {
    const mine = ++sequence;
    try {
      const found = await findEntries(options.tenant, search.input.value.trim(), 50);
      if (mine !== sequence) return;
      const placed = options.placed();
      const rows = found.filter((place) => !placed.has(place.id));
      list.replaceChildren(
        ...(rows.length
          ? rows.map((place) => {
              const item = el('li', '', 'row-tight map-outline-row');
              item.draggable = true;
              item.addEventListener('dragstart', (event) => {
                event.dataTransfer?.setData(
                  DRAG_TYPE,
                  JSON.stringify({ id: place.id, name: place.name }),
                );
                if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
              });
              const name = el('span', place.name, 'grow');
              const put = el('button', 'Place', 'btn btn-secondary');
              put.type = 'button';
              put.setAttribute('aria-label', `Place ${place.name} on the Map`);
              put.addEventListener('click', () => void options.place(place));
              item.append(
                icon(place.kinds.includes('location') ? 'kind-location' : 'kind-being'),
                name,
                put,
              );
              return item;
            })
          : [el('li', 'Everything found is on this Map.', 'status-text')]),
      );
      say(status, '');
    } catch (error) {
      if (mine === sequence)
        say(status, error instanceof Error ? error.message : 'Not read.', true);
    }
  }
  search.input.addEventListener('input', () => void refresh());

  return { root, refresh };
}
