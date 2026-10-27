import { installEntryPreview } from '@lorenzo/entry-preview';
import {
  createMapView,
  type Geometry,
  type Groups,
  type MapModel,
  type MapViewController,
  type Placement,
  type Style,
  type System,
  zoomLabel,
} from '@lorenzo/map-renderer';
import { client, type Schema, unwrap } from './api';
import { BRANDING_CSS_URL } from './config';
import {
  audienceBadge,
  backLink,
  claim,
  el,
  empty,
  errorNotice,
  field,
  icon,
  link,
  loading,
  locationHref,
  message,
  metaLine,
  pageHead,
  sectionHead,
  statusLine,
} from './dom';
import { canManage, libraryName, myLibraries } from './names';
import { loadCard, loadPicture } from './previews';
import { start } from './sign-in';
import { resolveEntry } from './views';

type Header = Schema<'MapOut'>;
type Row = Schema<'PlacementOut'>;

const tenantOf = () => new URLSearchParams(location.search).get('tenant');

// The renderer lays out every placement it is given; a Map holds at most this many (ADR 0337) and
// the view says so when it cannot show them all.
const VISIBLE_LIMIT = 5000;

export const mapHref = (tenant: string, id: string, slug?: string | null) =>
  `/map/?${new URLSearchParams({ tenant, ...(slug ? { slug } : { id }) })}`;

const words = (text: string) => text.replaceAll('_', ' ').replaceAll('-', ' ');

/** The placements of a Map in pages until it is complete or the limit is reached. */
async function readPlacements(tenant: string, id: string) {
  const rows: Row[] = [];
  let cursor: string | undefined;
  let more = false;
  do {
    const page = await unwrap(
      await client.GET('/tenants/{tenant_id}/maps/{map_id}/placements', {
        params: {
          path: { tenant_id: tenant, map_id: id },
          query: cursor ? { cursor } : {},
        },
        // Revalidated on every open: what a person may read is never decided by a freshness window.
        cache: 'no-cache',
      }),
    );
    rows.push(...page.items);
    cursor = page.next_cursor ?? undefined;
    if (cursor && rows.length >= VISIBLE_LIMIT) {
      more = true;
      break;
    }
  } while (cursor);
  return { rows, more };
}

function modelOf(header: Header, rows: Row[]): MapModel {
  const placements: Placement[] = rows.map((row) => ({
    entry: { id: row.id, name: row.name, slug: row.slug ?? null, kinds: row.kinds },
    geometry: row.geometry as unknown as Geometry,
    role: row.role ?? null,
    style: (row.style ?? null) as Style | null,
    z: row.z,
  }));
  return { system: header.system as unknown as System, placements };
}

/** Libraries first, as for Locations: a person opens Maps from the library they are working in. */
export async function mountMaps() {
  const host = document.querySelector<HTMLElement>('#maps-list');
  if (!host || !claim(host)) return;
  const me = await start();
  const tenant = tenantOf();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening Maps…'));
    if (!tenant) {
      const libraries = await myLibraries();
      const view = el('div', '', 'stack view');
      view.append(pageHead('Maps', { lede: 'Choose a library to see its Maps.' }));
      const list = el('ul', '', 'list');
      for (const library of libraries) {
        const row = el('li');
        row.append(link(library.name, `/maps/?${new URLSearchParams({ tenant: library.id })}`));
        list.append(row);
      }
      view.append(libraries.length ? list : empty('You are not in a library yet.'));
      host.replaceChildren(view);
      return;
    }
    const scope: string = tenant;
    const name = await libraryName(scope);
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Maps', {
        crumbs: [backLink('Libraries', '/')],
        lede: name ? `In ${name}.` : undefined,
      }),
    );
    const search = field('Find a Map');
    search.input.type = 'search';
    const list = el('ul', '', 'list');
    const status = statusLine();
    let sequence = 0;
    async function show() {
      const mine = ++sequence;
      const query = search.input.value.trim();
      try {
        const page = await unwrap(
          await client.GET('/tenants/{tenant_id}/maps', {
            params: {
              path: { tenant_id: scope },
              query: { ...(query ? { q: query } : {}), size: 100 },
            },
            cache: 'no-cache',
          }),
        );
        if (mine !== sequence) return;
        status.textContent = '';
        list.replaceChildren(
          ...(page.items.length
            ? page.items.map((stub) => {
                const row = el('li');
                row.append(
                  icon('kind-location'),
                  link(stub.name, mapHref(scope, stub.id, stub.slug)),
                );
                return row;
              })
            : [el('li', query ? 'No Map has that name.' : 'No Maps yet.', 'status-text')]),
        );
      } catch (error) {
        if (mine === sequence) {
          status.textContent = message(error);
          status.classList.add('error-text');
        }
      }
    }
    search.input.addEventListener('input', () => void show());
    const section = el('section', '', 'stack');
    section.append(sectionHead('Maps of the library'), search.label, status, list);
    view.append(section);
    host.replaceChildren(view);
    await show();
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

/** What the selection panel says of one placement. */
async function describe(tenant: string, row: Row, panel: HTMLElement) {
  panel.replaceChildren();
  const isLocation = row.kinds.includes('location');
  const title = el('h3', '', 'group-title');
  title.append(isLocation ? link(row.name, locationHref(tenant, row.id, row.slug)) : row.name);
  panel.append(title);
  const others = row.kinds.map(words);
  if (others.length) panel.append(el('p', others.join(', '), 'status-text'));
  if (row.role) panel.append(el('p', words(row.role), 'chip'));
  if (!isLocation) return;
  try {
    const place = await unwrap(
      await client.GET('/tenants/{tenant_id}/locations/{location_id}', {
        params: { path: { tenant_id: tenant, location_id: row.id } },
      }),
    );
    if (place.within && title.isConnected) {
      const within = el('p', '', 'status-text');
      within.append(
        document.createTextNode('In '),
        link(place.within.name, locationHref(tenant, place.within.id, place.within.slug)),
      );
      panel.append(within);
    }
  } catch {
    // The panel is a convenience; the drawing and the list stand without it.
  }
}

export async function mountMap() {
  const host = document.querySelector<HTMLElement>('#maps-map');
  if (!host || !claim(host)) return;
  const me = await start();
  const tenant = tenantOf();
  if (!me || !tenant || !host.isConnected) return;
  let controller: MapViewController | undefined;
  try {
    host.replaceChildren(loading('Opening this Map…'));
    let id: string;
    let header: Header;
    // One message for a Map that is hidden and one that is missing: the answers are the same.
    try {
      id = await resolveEntry(tenant, 'Map');
      header = await unwrap(
        await client.GET('/tenants/{tenant_id}/maps/{map_id}', {
          params: { path: { tenant_id: tenant, map_id: id } },
          cache: 'no-cache',
        }),
      );
    } catch {
      host.replaceChildren(
        errorNotice(
          new Error('This Map is not available. It may not exist, or it is not open to you.'),
        ),
      );
      return;
    }
    const [name, manage, found] = await Promise.all([
      libraryName(tenant),
      canManage(tenant),
      readPlacements(tenant, id),
    ]);
    const model = modelOf(header, found.rows);
    const view = el('div', '', 'stack view');
    const meta: Node[] = [];
    if (name) meta.push(metaLine('kind-location', name));
    if (manage && header.is_public !== null && header.is_public !== undefined)
      meta.push(
        audienceBadge(header.is_public ? 'Visible to everyone' : 'Restricted', header.is_public),
      );
    if (header.subject) meta.push(metaLine('kind-location', `Shows ${header.subject.name}`));
    view.append(
      pageHead(header.name, {
        crumbs: [backLink('Maps', `/maps/?${new URLSearchParams({ tenant })}`)],
        meta,
      }),
    );

    // The toolbar: what is drawn, the zoom, and the way back to the whole sheet.
    const toolbar = el('div', '', 'row map-toolbar');
    toolbar.setAttribute('role', 'group');
    toolbar.setAttribute('aria-label', 'What the map shows');
    const toggles: [keyof Groups, string][] = [
      ['places', 'Places'],
      ['people', 'People'],
      ['roads', 'Roads'],
      ['names', 'Names'],
      ['showPlaces', 'Show places'],
    ];
    for (const [key, label] of toggles) {
      const box = field(label, '', 'checkbox');
      box.input.checked = true;
      box.input.addEventListener('change', () =>
        controller?.setGroups({ [key]: box.input.checked }),
      );
      toolbar.append(box.label);
    }
    const zoom = el('span', '100%', 'chip');
    zoom.setAttribute('aria-live', 'polite');
    const zoomControls = el('div', '', 'row-tight map-zoom');
    const zoomButton = (label: string, glyph: string, act: () => void) => {
      const node = el('button', glyph, 'btn btn-secondary');
      node.type = 'button';
      node.setAttribute('aria-label', label);
      node.addEventListener('click', act);
      return node;
    };
    const whole = el('button', 'Whole map', 'btn btn-secondary');
    whole.type = 'button';
    whole.addEventListener('click', () => controller?.fit());
    const centre = el('button', '', 'btn btn-secondary');
    centre.type = 'button';
    centre.hidden = true;
    zoomControls.append(
      zoomButton('Zoom out', '−', () => controller?.zoomOut()),
      zoom,
      zoomButton('Zoom in', '+', () => controller?.zoomIn()),
      whole,
      centre,
    );
    toolbar.append(zoomControls);

    // The drawing, the line that names what is pointed at, and a tip.
    const stage = el('div', '', 'map-stage');
    const tip = el(
      'p',
      'Scroll or press + and − to zoom, drag or use the arrow keys to move, and press Tab to reach each place.',
      'status-text',
    );

    // The side panel and the list: the way a keyboard or a screen reader reaches each placement.
    const panel = el('div', '', 'card card-body stack-tight map-panel');
    panel.setAttribute('aria-live', 'polite');
    panel.append(el('p', 'Select a place on the map or in the list.', 'status-text'));
    const list = el('ul', '', 'list map-places');
    const buttons = new Map<string, HTMLButtonElement>();
    const byId = new Map(found.rows.map((row) => [row.id, row]));
    let selected: string | null = null;
    const select = (entryId: string | null, fromList = false) => {
      selected = entryId;
      for (const [key, button] of buttons)
        button.setAttribute('aria-pressed', String(key === entryId));
      const row = entryId ? byId.get(entryId) : undefined;
      if (row) void describe(tenant, row, panel);
      else
        panel.replaceChildren(el('p', 'Select a place on the map or in the list.', 'status-text'));
      centre.hidden = !row;
      if (row) centre.textContent = `Centre on ${row.name}`;
      if (fromList) controller?.select(entryId);
    };
    centre.addEventListener('click', () => selected && controller?.centreOn(selected));
    const sorted = [...found.rows].sort(
      (a, b) => a.name.localeCompare(b.name) || (a.id < b.id ? -1 : 1),
    );
    for (const row of sorted) {
      const item = el('li');
      const button = el('button', row.name, 'place-toggle map-place');
      button.type = 'button';
      button.setAttribute('aria-pressed', 'false');
      button.dataset.entry = row.id;
      button.addEventListener('click', () => select(selected === row.id ? null : row.id, true));
      if (row.role) button.append(el('span', words(row.role), 'chip'));
      buttons.set(row.id, button);
      item.append(button);
      list.append(item);
    }

    const drawing = el('section', '', 'stack');
    drawing.append(sectionHead('The map'), toolbar);
    const layoutRow = el('div', '', 'map-layout');
    const left = el('div', '', 'stack');
    left.append(stage, tip);
    layoutRow.append(left, panel);
    drawing.append(layoutRow);
    view.append(drawing);
    if (found.more)
      view.append(
        el(
          'p',
          `This Map holds more than the ${VISIBLE_LIMIT.toLocaleString('en')} places shown here.`,
          'status-text',
        ),
      );
    const places = el('section', '', 'stack');
    places.append(
      sectionHead('Places on this map', { count: found.rows.length }),
      found.rows.length ? list : empty('Nothing is drawn on this Map yet.'),
    );
    view.append(places);
    host.replaceChildren(view);

    controller = createMapView(stage, {
      model,
      title: `Map of ${header.name}`,
      description: found.rows.length
        ? `${found.rows.length} places are drawn; the list below the map names each one.`
        : 'Nothing is drawn on this Map yet.',
      iconBase: BRANDING_CSS_URL,
      // Focusable marks inside role="img" are not reachable by every screen reader (axe reports
      // nested-interactive), so the drawing is a named group of buttons.
      role: 'group',
      onSelect: (entryId) => select(entryId),
      onView: (state) => {
        zoom.textContent = zoomLabel(state.zoom);
      },
    });
    zoom.textContent = zoomLabel(controller.getView().zoom);
    // A mark of the drawing and a row of the places list open the entry's card (ADR 0350). Maps is a
    // desktop app, so a tap only selects.
    const preview = installEntryPreview({
      selector: '.m-mark[data-entry], .map-place[data-entry]',
      targetOf: (element) => {
        const id = element.getAttribute('data-entry');
        return id ? { tenant, id } : null;
      },
      loadCard,
      loadPicture,
      touch: 'off',
    });
    document.addEventListener(
      'astro:before-swap',
      () => {
        controller?.destroy();
        preview.destroy();
      },
      { once: true },
    );
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.replaceChildren(errorNotice(error));
  }
}
