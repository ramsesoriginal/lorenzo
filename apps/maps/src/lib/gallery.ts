// A card of the gallery of Maps (MP1): a small drawing, the Map's name, what it is drawn on, and how
// it is tied to a date. The name and the tie come with the list; the rest is read when the card comes
// into view, a few cards at a time, so a long gallery does not ask for everything at once. Every read
// is this reader's own, so nothing hidden can be on a card (D24), and a Map that cannot be read leaves
// its card with the name alone.
import type { MapModel, System } from '@lorenzo/map-renderer';
import { client, type Schema, unwrap } from './api';
import { BRANDING_CSS_URL } from './config';
import { TIE_WORDS, type Tie } from './date-words';
import { el, icon, link } from './dom';
import { chosenTheme, readLook } from './look';
import { type Header, type Row, readPlacements } from './map-api';
import { systemWords } from './system-words';
import { drawThumbnail, queue } from './thumbnail';

export type MapStub = Schema<'MapStub'> & { tie?: Tie | null };

/** How many placements a drawing this small is made from. */
const SAMPLE = 300;

const chip = (iconName: string, text: string) => {
  const node = el('span', '', 'chip map-chip');
  node.append(icon(iconName), document.createTextNode(text));
  return node;
};

const enqueue = queue(3);

/** The dates a Map is tied to, in the calendar's own words. */
async function tiedTo(tenant: string, id: string): Promise<string[]> {
  const periods = await client
    .GET('/tenants/{tenant_id}/entities/{entity_id}/dates', {
      params: { path: { tenant_id: tenant, entity_id: id } },
      cache: 'no-cache',
    })
    .then((r) => r.data ?? [])
    .catch(() => []);

  return periods.map((p) => p.name);
}

export function mapCard(
  tenant: string,
  stub: MapStub,
  href: string,
  build: (header: Header, rows: Row[]) => MapModel,
): HTMLElement {
  const item = el('li', '', `card card-body map-card${stub.tie === 'other' ? ' map-other' : ''}`);
  const thumb = el('div', '', 'map-thumb');
  thumb.dataset.state = 'waiting';
  const title = el('h2', '', 'map-card-title');
  title.append(link(stub.name, href));
  const system = el('p', '', 'status-text map-system');
  const ties = el('div', '', 'row-tight map-ties');
  item.append(thumb, title, system, ties);
  if (stub.tie) ties.append(chip('info', TIE_WORDS[stub.tie]));

  const fill = async () => {
    const result = await client.GET('/tenants/{tenant_id}/maps/{map_id}', {
      params: { path: { tenant_id: tenant, map_id: stub.id } },
      cache: 'no-cache',
    });
    const header = await unwrap(result);
    system.textContent = systemWords(header.system as unknown as System);
    if (header.is_public === false) ties.append(chip('eye-off', 'Not open to the library'));
    const [{ rows }, dates] = await Promise.all([
      readPlacements(tenant, stub.id, SAMPLE),
      tiedTo(tenant, stub.id),
    ]);
    if (!item.isConnected) return;
    drawThumbnail(
      thumb,
      build(header, rows),
      chosenTheme(readLook(), header.theme_hint),
      BRANDING_CSS_URL,
    );
    thumb.dataset.state = 'drawn';
    if (!stub.tie) {
      const first = dates[0];
      ties.prepend(
        first
          ? chip(
              'kind-calendar',
              dates.length > 1 ? `${first} and ${dates.length - 1} more` : first,
            )
          : chip('info', TIE_WORDS.untied),
      );
    }
  };
  // A Map that cannot be read now is left as its list gave it.
  const start = () =>
    enqueue(async () => {
      try {
        await fill();
      } catch {
        thumb.dataset.state = 'failed';
      }
    });
  if ('IntersectionObserver' in window) {
    const watch = new IntersectionObserver((seen) => {
      if (!seen.some((entry) => entry.isIntersecting)) return;
      watch.disconnect();
      start();
    });
    watch.observe(item);
  } else start();

  return item;
}
