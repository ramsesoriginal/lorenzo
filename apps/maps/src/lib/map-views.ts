import { pageState } from '@lorenzo/app-shell';
import { installEntryPreview } from '@lorenzo/entry-preview';
import {
  createMapView,
  type Geometry,
  type GridSpec,
  type Groups,
  gridOf,
  isSphere,
  type Layer,
  type MapModel,
  type MapViewController,
  onGlobe,
  type Placement,
  type Projection,
  placementCentre,
  projectionOf,
  type Style,
  type System,
  screenToDrawing,
  unproject,
  zoomLabel,
} from '@lorenzo/map-renderer';
import { client, unwrap } from './api';
import { cellOfPoint, cellWords } from './cells-edit';
import { BRANDING_CSS_URL } from './config';
import { wayWords } from './connection-words';
import { dateLens } from './date-lens';
import { leftWords } from './date-words';
import { distanceSection } from './distance-section';
import {
  audienceBadge,
  backLink,
  claim,
  el,
  empty,
  errorNotice,
  field,
  groupTitle,
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
import { mapCard } from './gallery';
import { loadLayers } from './layer-pictures';
import { picturesSection } from './layers-settings';
import { chosenTheme, LOOKS, type Look, readLook, writeLook } from './look';
import {
  type Header,
  type LinkRow,
  type Row,
  readLinks,
  readPlacements,
  VISIBLE_LIMIT,
} from './map-api';
import { createEditor, type Editor } from './map-edit';
import { createLegend } from './map-legend';
import { makeMapForm, settingsSection } from './map-settings';
import { canManage, libraryName, myLibraries } from './names';
import { loadCard, loadPicture } from './previews';
import { start } from './sign-in';
import { smallChanges } from './small-changes';
import {
  PROJECTION_WORDS,
  positionWords,
  projectionFrom,
  readProjectionChoice,
  type Turn,
  turned,
  writeProjectionChoice,
} from './sphere-words';
import { systemWords } from './system-words';
import { resolveEntry } from './views';

/** Whether this window is a phone's: drawing is not offered there (MP2). */
const phoneNow = () => window.matchMedia('(max-width: 720px)').matches;

const tenantOf = () => new URLSearchParams(location.search).get('tenant');

export const mapHref = (tenant: string, id: string, slug?: string | null) =>
  `/map/?${new URLSearchParams({ tenant, ...(slug ? { slug } : { id }) })}`;

const words = (text: string) => text.replaceAll('_', ' ').replaceAll('-', ' ');

/** The Map as the renderer draws it; a sphere takes the projection it is to be seen through. */
function modelOf(
  header: Header,
  rows: Row[],
  projection?: Projection,
  layers: readonly Layer[] = [],
): MapModel {
  const placements: Placement[] = rows.map((row) => ({
    entry: { id: row.id, name: row.name, slug: row.slug ?? null, kinds: row.kinds },
    geometry: row.geometry as unknown as Geometry,
    role: row.role ?? null,
    style: (row.style ?? null) as Style | null,
    z: row.z,
  }));
  const system = header.system as unknown as System;
  const seen = projection ?? projectionFrom(header.view);
  return {
    system: isSphere(system) && seen ? { ...system, projection: seen } : system,
    placements,
    overlay: ((header.view as { grid?: GridSpec } | null)?.grid ?? null) as GridSpec | null,
    ...(layers.length > 0 ? { layers } : {}),
  };
}

/** Where a place is, for the panel: the cell on a grid Map, the position on a sphere. */
function whereWords(row: Row, model: MapModel): string | null {
  const part = (row.geometry as unknown as Geometry).parts[0];
  if (!part) return null;
  if (isSphere(model.system)) {
    const at =
      part.shape === 'point'
        ? part.at
        : placementCentre({ geometry: row.geometry } as unknown as Placement);
    return at ? `${part.shape === 'point' ? 'At' : 'Around'} ${positionWords(at)}` : null;
  }
  const grid = gridOf(model);
  const extent = model.system.extent as unknown as [number, number, number, number];
  if (!grid || part.shape !== 'point') return null;
  const cell = cellOfPoint(grid, extent, part.at);
  return cell ? `In cell: ${cellWords(cell)}` : null;
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
    const [name, manage] = await Promise.all([libraryName(scope), canManage(scope)]);
    const view = el('div', '', 'stack view');
    const search = field('Find a Map');
    search.input.type = 'search';
    search.label.classList.add('map-find');
    const gallery = el('ul', '', 'map-gallery');
    const none = el('div', '', 'stack');
    const status = statusLine();
    const left = el('p', '', 'status-text');
    left.setAttribute('role', 'status');
    const lens = await dateLens(scope, () => {
      when.textContent = lens?.chosen() ? 'A date is chosen' : 'Any date';
      when.prepend(icon('kind-calendar'));
      void show();
    });
    // The page's own actions (MP1): looking through a date, and making a Map, first.
    const headActions: HTMLElement[] = [];
    const when = el('button', '', 'btn btn-secondary');
    when.type = 'button';
    when.append(icon('kind-calendar'), document.createTextNode('Any date'));
    const lensPanel = el('section', '', 'card card-body map-lens-panel');
    lensPanel.hidden = true;
    lensPanel.id = 'map-lens-panel';
    if (lens) {
      when.setAttribute('aria-controls', lensPanel.id);
      when.setAttribute('aria-expanded', 'false');
      when.addEventListener('click', () => {
        lensPanel.hidden = !lensPanel.hidden;
        when.setAttribute('aria-expanded', String(!lensPanel.hidden));
      });
      lensPanel.append(lens.element);
      headActions.push(when);
    }
    const make = manage ? el('section', '', 'card card-body map-make') : null;
    if (make) {
      make.hidden = true;
      make.id = 'map-make';
      make.append(makeMapForm(scope, (id, slug) => location.assign(mapHref(scope, id, slug))));
      const open = el('button', '', 'btn btn-primary');
      open.type = 'button';
      open.setAttribute('aria-controls', make.id);
      open.setAttribute('aria-expanded', 'false');
      open.append(icon('add'), document.createTextNode('Make a Map'));
      open.addEventListener('click', () => {
        make.hidden = !make.hidden;
        open.setAttribute('aria-expanded', String(!make.hidden));
      });
      headActions.push(open);
    }
    view.append(
      pageHead('Maps', {
        lede: name ? `The places of ${name}, drawn.` : undefined,
        actions: headActions,
      }),
    );
    if (make) view.append(make);
    view.append(lensPanel, search.label, status, left, gallery, none);
    let sequence = 0;
    async function show() {
      const mine = ++sequence;
      const query = search.input.value.trim();
      try {
        const page = await unwrap(
          await client.GET('/tenants/{tenant_id}/maps', {
            params: {
              path: { tenant_id: scope },
              query: { ...(query ? { q: query } : {}), ...(lens ? lens.query() : {}), size: 100 },
            },
            cache: 'no-cache',
          }),
        );
        if (mine !== sequence) return;
        status.textContent = '';
        left.textContent = lens?.leavesOut() ? leftWords(page.total) : '';
        gallery.replaceChildren(
          ...page.items.map((stub) =>
            mapCard(scope, stub, mapHref(scope, stub.id, stub.slug), (header, rows) =>
              modelOf(header, rows),
            ),
          ),
        );
        none.replaceChildren(
          ...(page.items.length
            ? []
            : [
                query
                  ? el('p', 'No Map has that name.', 'status-text')
                  : pageState(BRANDING_CSS_URL, {
                      art: 'empty-map',
                      level: 2,
                      title: 'No Maps yet',
                      text: manage
                        ? 'Make a Map to draw the places of this library.'
                        : 'No Map is open to you in this library yet.',
                    }),
              ]),
        );
      } catch (error) {
        if (mine === sequence) {
          status.textContent = message(error);
          status.classList.add('error-text');
        }
      }
    }
    search.input.addEventListener('input', () => void show());
    host.replaceChildren(view);
    await show();
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

/** What the selection panel says of one placement. */
async function describe(
  tenant: string,
  row: Row,
  panel: HTMLElement,
  where: string | null = null,
  ways: readonly LinkRow[] = [],
) {
  panel.replaceChildren();
  const isLocation = row.kinds.includes('location');
  const title = el('h3', '', 'group-title');
  title.append(isLocation ? link(row.name, locationHref(tenant, row.id, row.slug)) : row.name);
  panel.append(title);
  const others = row.kinds.map(words);
  if (others.length) panel.append(el('p', others.join(', '), 'status-text'));
  if (row.role) panel.append(el('p', words(row.role), 'chip'));
  if (where) panel.append(el('p', where, 'status-text'));
  if (ways.length > 0) {
    // Where it leads, derived from the connections' ends (ADR 0364); never a claim about where anything is.
    panel.append(groupTitle('h4', 'Leads to'));
    const leads = el('ul', '', 'list map-ways');
    for (const way of ways) {
      const item = el('li', `${way.connection.name} ${wayWords(way.direction, way.other.name)}`);
      if (way.other_maps.length > 0) {
        item.append(document.createTextNode(' (also on '));
        way.other_maps.forEach((other, index) => {
          if (index > 0) item.append(document.createTextNode(', '));
          item.append(link(other.name, mapHref(tenant, other.id, other.slug)));
        });
        item.append(document.createTextNode(')'));
      }
      leads.append(item);
    }
    panel.append(leads);
  }
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
  // What the page made and must undo before it draws again or is left.
  let cleanup: (() => void) | undefined;
  document.addEventListener('astro:before-swap', () => cleanup?.(), { once: true });
  // Which tab of the panel is open stays so across a redraw (a save draws the page again).
  const panelMemory = { open: false, tab: 'selected' };
  const render = async () => {
    const restore = { ...panelMemory };
    cleanup?.();
    cleanup = undefined;
    try {
      host.replaceChildren(loading('Opening this Map…'));
      let id: string;
      let header: Header;
      let version = '';
      // One message for a Map that is hidden and one that is missing: the answers are the same.
      try {
        id = await resolveEntry(tenant, 'Map');
        const result = await client.GET('/tenants/{tenant_id}/maps/{map_id}', {
          params: { path: { tenant_id: tenant, map_id: id } },
          cache: 'no-cache',
        });
        header = await unwrap(result);
        version = result.response.headers.get('etag') ?? '';
      } catch {
        host.replaceChildren(
          errorNotice(
            new Error('This Map is not available. It may not exist, or it is not open to you.'),
          ),
        );
        return;
      }
      const [name, manage, found, links] = await Promise.all([
        libraryName(tenant),
        canManage(tenant),
        readPlacements(tenant, id),
        readLinks(tenant, id),
      ]);
      const waysOf = (entry: string) => links.filter((row) => row.here.id === entry);
      const mapId = id;
      let rows: Row[] = found.rows;
      // How a sphere is seen: what this reader chose for themselves, else what the Map is saved
      // with (ADR 0359). Nothing for any other kind.
      const onSphere = isSphere(header.system as unknown as System);
      let projection: Projection | undefined = onSphere
        ? (readProjectionChoice(mapId) ?? projectionFrom(header.view))
        : undefined;
      // The pictures under the Map, loaded after the first drawing (ADR 0362).
      let pictures: Layer[] = [];
      const build = (next: Row[] = rows): MapModel => modelOf(header, next, projection, pictures);
      // Where a place is, in words: the cell on a grid Map and the position on a sphere.
      const pinCell = (row: Row): string | null => whereWords(row, build());
      let controller: MapViewController | undefined;
      let editor: Editor | undefined;
      const writer = manage && header.can_manage;

      // The Map fills the page (MP3): floating controls sit over it and a panel slides over from the
      // side. This is the card that names it.
      const view = el('div', '', 'map-workspace');
      const meta: Node[] = [];
      if (name) meta.push(metaLine('kind-location', name));
      if (writer && header.is_public !== null && header.is_public !== undefined)
        meta.push(
          audienceBadge(header.is_public ? 'Visible to everyone' : 'Restricted', header.is_public),
        );
      if (header.subject) meta.push(metaLine('kind-location', `Shows ${header.subject.name}`));
      const titleCard = el('div', '', 'card card-body stack-tight map-title-card');
      titleCard.append(
        backLink('Maps', `/maps/?${new URLSearchParams({ tenant })}`),
        el('h1', header.name, 'map-title'),
        el('p', systemWords(header.system as unknown as System), 'status-text'),
      );
      if (meta.length) {
        const metaRow = el('div', '', 'row');
        metaRow.append(...meta);
        titleCard.append(metaRow);
      }
      // What the controls open: only one at a time, and Escape puts the open one away.
      const pops: { close: () => void }[] = [];
      let popCount = 0;
      const popover = (label: string, iconName: string, content: HTMLElement) => {
        const root = el('div', '', 'map-pop-wrap');
        const trigger = el('button', '', 'btn btn-secondary');
        trigger.type = 'button';
        trigger.append(icon(iconName), document.createTextNode(label));
        const body = el('div', '', 'card card-body map-pop stack-tight');
        popCount += 1;
        body.id = `map-pop-${popCount}`;
        body.hidden = true;
        body.append(content);
        trigger.setAttribute('aria-expanded', 'false');
        trigger.setAttribute('aria-controls', body.id);
        const close = () => {
          body.hidden = true;
          trigger.setAttribute('aria-expanded', 'false');
        };
        pops.push({ close });
        trigger.addEventListener('click', () => {
          const open = body.hidden;
          for (const other of pops) other.close();
          body.hidden = !open;
          trigger.setAttribute('aria-expanded', String(open));
        });
        body.addEventListener('keydown', (event) => {
          if (event.key !== 'Escape') return;
          close();
          trigger.focus();
        });
        root.append(trigger, body);
        return { root, trigger, body, close };
      };

      // What is drawn (Layers), the look, the way a sphere is drawn and the zoom: each a floating control.
      const lookBox = el('div', '', 'stack-tight');
      const sphereBox = el('div', '', 'stack-tight');
      const zoomBox = el('div', '', 'map-float map-float--zoom');
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
      const gridSpec = gridOf(build());
      // "Zoom in to see the grid" when the grid is on but too fine to draw (ADR 0355), and the cell
      // under the pointer in words (ADR 0356).
      const gridNote = el('span', '', 'status-text map-grid-note');
      const cellNote = el('span', '', 'status-text map-cell');
      cellNote.setAttribute('aria-hidden', 'true');
      const updateGridNote = () =>
        requestAnimationFrame(() => {
          const drawn = controller?.scene()?.prims.some((prim) => prim.id === 'grid');
          const on = controller?.getView().groups.grid ?? true;
          gridNote.textContent = gridSpec && on && !drawn ? 'Zoom in to see the grid.' : '';
        });
      // A sphere's grid is its lines of longitude and latitude (ADR 0358).
      if (gridSpec || onSphere) toggles.push(['grid', 'Grid']);
      const picturesHere = !onSphere && (header.layers ?? []).some((layer) => layer.payload_id);
      if (picturesHere) toggles.push(['layers', 'Pictures']);
      for (const [key, label] of toggles) {
        const box = field(label, '', 'checkbox');
        box.input.checked = true;
        box.input.addEventListener('change', () => {
          controller?.setGroups({ [key]: box.input.checked });
          updateGridNote();
        });
        toolbar.append(box.label);
      }
      let look: Look = readLook();
      let legendPop: ReturnType<typeof popover> | undefined;
      const legend = createLegend((shown) => {
        if (legendPop) legendPop.root.hidden = !shown;
      });
      const themeNow = () => chosenTheme(look, header.theme_hint);
      const looks = el('label', '', 'field-inline');
      const lookSelect = el('select', '', 'text-input');
      for (const [value, label] of LOOKS) {
        const option = el('option', label);
        option.value = value;
        lookSelect.append(option);
      }
      lookSelect.value = look;
      lookSelect.addEventListener('change', () => {
        look = lookSelect.value as Look;
        writeLook(look);
        controller?.setTheme(themeNow());
        legend.update(build(), themeNow());
      });
      looks.append(el('span', 'Look', 'field-label'), lookSelect);
      lookBox.append(looks);

      // A sphere: how it is drawn, and for a globe the buttons that turn it. Both are this reader's
      // own and nothing is saved (ADR 0359).
      const turnBar = el('div', '', 'row-tight map-turn');
      turnBar.setAttribute('role', 'group');
      turnBar.setAttribute('aria-label', 'Turn the globe');
      const redrawSphere = (fit: boolean) => {
        controller?.setModel(build());
        if (fit) controller?.fit();
        updateTurn();
      };
      const drawnAs = el('label', '', 'field-inline');
      const drawnSelect = el('select', '', 'text-input');
      for (const [value, label] of PROJECTION_WORDS) {
        const option = el('option', label);
        option.value = value;
        drawnSelect.append(option);
      }
      const seenAs = () => projectionOf(projection ? { projection } : {});
      drawnSelect.value = seenAs().kind;
      drawnSelect.addEventListener('change', () => {
        const kind = drawnSelect.value as Projection['kind'];
        projection =
          kind === 'orthographic'
            ? { kind, centre: projection?.centre ?? projectionFrom(header.view)?.centre ?? [0, 0] }
            : { kind };
        writeProjectionChoice(mapId, projection);
        redrawSphere(true);
      });
      drawnAs.append(el('span', 'Drawn as', 'field-label'), drawnSelect);
      const turnButton = (label: string, turn: Turn) => {
        const node = el('button', label, 'btn btn-secondary');
        node.type = 'button';
        node.addEventListener('click', () => {
          projection = { kind: 'orthographic', centre: turned(seenAs().centre ?? [0, 0], turn) };
          writeProjectionChoice(mapId, projection);
          redrawSphere(false);
        });
        return node;
      };
      const saved = el('button', 'Back to the saved view', 'btn btn-secondary');
      saved.type = 'button';
      saved.addEventListener('click', () => {
        projection = projectionFrom(header.view);
        writeProjectionChoice(mapId, undefined);
        drawnSelect.value = seenAs().kind;
        redrawSphere(true);
      });
      turnBar.append(
        turnButton('Turn west', 'west'),
        turnButton('Turn east', 'east'),
        turnButton('Turn north', 'north'),
        turnButton('Turn south', 'south'),
        saved,
      );
      const updateTurn = () => {
        turnBar.hidden = seenAs().kind !== 'orthographic';
      };
      updateTurn();
      if (onSphere) sphereBox.append(drawnAs, turnBar);
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
        cellNote,
        gridNote,
        zoomButton('Zoom out', '−', () => controller?.zoomOut()),
        zoom,
        zoomButton('Zoom in', '+', () => controller?.zoomIn()),
        whole,
        centre,
      );
      zoomBox.append(zoomControls);

      // The drawing and a tip.
      const stageHost = el('div', '', 'map-stage');
      const tip = el(
        'p',
        'Scroll or press + and − to zoom, drag or use the arrow keys to move, and press Tab to reach each place.',
        'status-text',
      );

      // The side panel and the list: the way a keyboard or a screen reader reaches each placement.
      const panel = el('div', '', 'card card-body stack-tight map-panel');
      panel.setAttribute('aria-live', 'polite');
      const noSelection = () =>
        panel.replaceChildren(el('p', 'Select a place on the map or in the list.', 'status-text'));
      noSelection();
      const list = el('ul', '', 'list map-places');
      const places = el('section', '', 'stack');
      const buttons = new Map<string, HTMLButtonElement>();
      let selected: string | null = null;
      const select = (entryId: string | null, fromList = false) => {
        selected = entryId;
        for (const [key, button] of buttons)
          button.setAttribute('aria-pressed', String(key === entryId));
        const row = entryId ? rows.find((r) => r.id === entryId) : undefined;
        // biome-ignore lint/correctness/usePlaywrightValidDescribeCallback: describe is this app's own helper, not Playwright's
        if (row) void describe(tenant, row, panel, pinCell(row), waysOf(row.id));
        else noSelection();
        centre.hidden = !row;
        if (row) centre.textContent = `Centre on ${row.name}`;
        // While drawing, what is selected shows in the dock and the Map stays clear of the panel.
        if (row && !editor?.editing()) openPanel('selected');
        if (fromList || (entryId === null && controller?.getView().selection)) {
          controller?.select(entryId);
        }
        editor?.selected(entryId);
      };
      centre.addEventListener('click', () => selected && controller?.centreOn(selected));

      const drawList = () => {
        buttons.clear();
        list.replaceChildren();
        const sorted = [...rows].sort(
          (a, b) => a.name.localeCompare(b.name) || (a.id < b.id ? -1 : 1),
        );
        for (const row of sorted) {
          const item = el('li');
          const button = el('button', row.name, 'place-toggle map-place');
          button.type = 'button';
          button.setAttribute('aria-pressed', String(row.id === selected));
          button.dataset.entry = row.id;
          button.addEventListener('click', () => select(selected === row.id ? null : row.id, true));
          if (row.role) button.append(el('span', words(row.role), 'chip'));
          buttons.set(row.id, button);
          item.append(button);
          list.append(item);
        }
        places.replaceChildren(
          sectionHead('Places on this map', { count: rows.length }),
          rows.length ? list : empty('Nothing is drawn on this Map yet.'),
        );
      };
      drawList();

      // The panel that slides over: the selected mark, the places, and for a writer the settings.
      const slide = el('aside', '', 'card map-slideover');
      slide.hidden = true;
      slide.id = 'map-slideover';
      slide.setAttribute('aria-label', 'This Map');
      const tabNames = writer
        ? ([
            ['selected', 'Selected'],
            ['places', 'Places'],
            ['settings', 'Settings'],
          ] as const)
        : ([
            ['selected', 'Selected'],
            ['places', 'Places'],
          ] as const);
      const tabList = el('div', '', 'row-tight map-tabs');
      tabList.setAttribute('role', 'tablist');
      tabList.setAttribute('aria-label', 'What the panel shows');
      const bodies = new Map<string, HTMLElement>();
      const tabs = new Map<string, HTMLButtonElement>();
      const showTab = (name: string) => {
        panelMemory.tab = name;
        for (const [key, tab] of tabs) {
          tab.setAttribute('aria-selected', String(key === name));
          tab.tabIndex = key === name ? 0 : -1;
          const body = bodies.get(key);
          if (body) body.hidden = key !== name;
        }
      };
      const openPanel = (name: string) => {
        panelMemory.open = true;
        slide.hidden = false;
        view.dataset.panel = 'open';
        showTab(name);
      };
      const closePanel = () => {
        panelMemory.open = false;
        slide.hidden = true;
        delete view.dataset.panel;
      };
      for (const [key, label] of tabNames) {
        const tab = el('button', label, 'btn btn-secondary map-tab');
        tab.type = 'button';
        tab.id = `map-tab-${key}`;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', `map-body-${key}`);
        tab.addEventListener('click', () => showTab(key));
        tab.addEventListener('keydown', (event) => {
          if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
          const names = tabNames.map(([name]) => name);
          const at = names.indexOf(key);
          const to =
            names[(at + (event.key === 'ArrowRight' ? 1 : names.length - 1)) % names.length];
          if (!to) return;
          showTab(to);
          tabs.get(to)?.focus();
        });
        tabs.set(key, tab);
        tabList.append(tab);
        const body = el('div', '', 'stack map-body');
        body.id = `map-body-${key}`;
        body.setAttribute('role', 'tabpanel');
        body.setAttribute('aria-labelledby', tab.id);
        body.hidden = true;
        bodies.set(key, body);
      }
      const closeButton = el('button', '', 'btn btn-secondary');
      closeButton.type = 'button';
      closeButton.setAttribute('aria-label', 'Close the panel');
      closeButton.append(icon('close'));
      closeButton.addEventListener('click', closePanel);
      slide.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closePanel();
      });
      const slideHead = el('div', '', 'row map-slideover-head');
      slideHead.append(el('h2', 'Map panel', 'grow'), closeButton);
      slide.append(slideHead, tabList, ...bodies.values());

      const selectedBody = bodies.get('selected') as HTMLElement;
      selectedBody.append(panel);
      const placesBody = bodies.get('places') as HTMLElement;
      placesBody.append(tip, places);
      if (found.more)
        placesBody.append(
          el(
            'p',
            `This Map holds more than the ${VISIBLE_LIMIT.toLocaleString('en')} places shown here.`,
            'status-text',
          ),
        );
      placesBody.append(
        distanceSection({
          tenant,
          map: { id: header.id, system: header.system as Record<string, unknown> },
          places: rows,
        }),
      );
      if (writer) {
        const settingsBody = bodies.get('settings') as HTMLElement;
        if ((header.layers ?? []).some((layer) => layer.needs_review)) {
          settingsBody.append(
            el(
              'p',
              'A picture under this Map was replaced after it was set up. Look at it against the places, then mark it reviewed in Settings.',
              'status-text',
            ),
          );
        }
        settingsBody.append(
          sectionHead('Settings'),
          settingsSection(tenant, header, version, render),
        );
        if (!onSphere) {
          settingsBody.append(
            sectionHead('Pictures'),
            picturesSection({ tenant, header, version, again: render }),
          );
        }
      }
      showTab('selected');
      if (restore.open) openPanel(restore.tab);

      // The floating controls: Places beside the title, what is drawn, the look and the legend over a
      // corner, and the zoom at the foot.
      const placesButton = el('button', '', 'btn btn-secondary');
      placesButton.type = 'button';
      placesButton.append(icon('list'), document.createTextNode('Places'));
      placesButton.setAttribute('aria-controls', slide.id);
      placesButton.addEventListener('click', () => {
        if (slide.hidden || bodies.get('places')?.hidden) openPanel('places');
        else closePanel();
      });
      const titleRow = el('div', '', 'row-tight');
      titleRow.append(placesButton);
      // What a writer draws with sits in this card until the toolbox of the drawing view takes its place.
      const tools = el('div', '', 'map-tools');
      titleCard.append(titleRow, tools);
      const topRight = el('div', '', 'row-tight map-float map-float--controls');
      const layersPop = popover('Layers', 'layers', toolbar);
      const lookPop = popover('Look', 'eye', lookBox);
      legendPop = popover('Legend', 'legend', legend.root);
      legendPop.root.hidden = true;
      topRight.append(layersPop.root, lookPop.root, legendPop.root);
      if (onSphere) topRight.append(popover('Projection', 'map', sphereBox).root);
      // Pictures load after the drawing, and say so when some could not be shown (ADR 0362).
      const pictureNote = el('p', '', 'status-text');
      pictureNote.setAttribute('role', 'status');
      const status = el('div', '', 'row-tight map-float map-float--status');
      status.append(pictureNote);
      const stage = stageHost;
      // What is being drawn or changed floats over the Map until the toolbox of the drawing view takes its place.
      const editDock = el('div', '', 'map-edit-dock');
      const leftColumn = el('div', '', 'map-float map-float--left');
      leftColumn.append(titleCard, editDock);
      view.append(stage, leftColumn, topRight, zoomBox, status, slide);
      host.replaceChildren(view);

      const model = build();
      controller = createMapView(stage, {
        model,
        theme: themeNow(),
        title: `Map of ${header.name}`,
        description: rows.length
          ? 'Places are drawn; the list below the map names each one.'
          : 'Nothing is drawn on this Map yet.',
        iconBase: BRANDING_CSS_URL,
        // Focusable marks inside role="img" are not reachable by every screen reader (axe reports
        // nested-interactive), so the drawing is a named group of buttons.
        role: 'group',
        onSelect: (entryId) => select(entryId),
        onView: (state) => {
          zoom.textContent = zoomLabel(state.zoom);
          updateGridNote();
        },
      });
      zoom.textContent = zoomLabel(controller.getView().zoom);
      updateGridNote();
      if (picturesHere) {
        pictureNote.textContent = 'Loading the pictures…';
        void loadLayers(tenant, header.layers ?? []).then(({ layers, failed }) => {
          if (!stage.isConnected) return;
          pictures = layers;
          controller?.setModel(build());
          pictureNote.textContent =
            failed > 0
              ? `${failed} ${failed === 1 ? 'picture' : 'pictures'} could not be shown.`
              : '';
        });
      }
      if (gridSpec) {
        const sheet = (header.system as { extent: number[] }).extent as unknown as [
          number,
          number,
          number,
          number,
        ];
        stage.addEventListener('pointermove', (event) => {
          const box = stage.getBoundingClientRect();
          const state = controller?.getView();
          if (!state) return;
          const at = screenToDrawing(
            model.system,
            { width: stage.clientWidth, height: stage.clientHeight },
            { zoom: state.zoom, centre: state.centre },
            [event.clientX - box.left, event.clientY - box.top],
          );
          const cell = cellOfPoint(gridSpec, sheet, at);
          cellNote.textContent = cell ? cellWords(cell) : '';
        });
        stage.addEventListener('pointerleave', () => {
          cellNote.textContent = '';
        });
      }
      if (onSphere) {
        // Where the pointer is, in words; nothing on the far side of a globe (ADR 0359).
        stage.addEventListener('pointermove', (event) => {
          const box = stage.getBoundingClientRect();
          const state = controller?.getView();
          if (!state) return;
          const now = build();
          const at = screenToDrawing(
            now.system,
            { width: stage.clientWidth, height: stage.clientHeight },
            { zoom: state.zoom, centre: state.centre },
            [event.clientX - box.left, event.clientY - box.top],
          );
          cellNote.textContent = onGlobe(projectionOf(now.system), at[0], at[1])
            ? positionWords(unproject(now.system, at))
            : '';
        });
        stage.addEventListener('pointerleave', () => {
          cellNote.textContent = '';
        });
      }
      legend.update(model, themeNow());

      const setRows = (next: Row[]) => {
        rows = next;
        const updated = build();
        controller?.setModel(updated);
        legend.update(updated, themeNow());
        drawList();
        if (selected && !rows.some((r) => r.id === selected)) select(null);
        else if (selected) {
          const row = rows.find((r) => r.id === selected);
          // biome-ignore lint/correctness/usePlaywrightValidDescribeCallback: describe is this app's own helper, not Playwright's
          if (row) void describe(tenant, row, panel, pinCell(row), waysOf(row.id));
        }
      };

      if (writer) {
        const extent = (header.system as { extent?: number[] }).extent ?? [0, 0, 1000, 800];
        editor = createEditor({
          tenant,
          mapId,
          mapIsPublic: header.is_public === true,
          extent: [extent[0] ?? 0, extent[1] ?? 0, extent[2] ?? 1000, extent[3] ?? 800],
          grid: () => gridOf(model),
          sphere: onSphere,
          view: () => controller as MapViewController,
          rows: () => rows,
          setRows,
          select: (entryId) => select(entryId, true),
        });
        if (phoneNow()) {
          // A phone reads everything and writes what needs no pointer on the sheet (MP2).
          const small = smallChanges({
            tenant,
            header,
            version,
            selected: () => rows.find((r) => r.id === selected),
            again: render,
            back: () => {
              small.root.hidden = true;
              edit.hidden = false;
              delete view.dataset.small;
            },
          });
          small.root.hidden = true;
          const edit = el('button', '', 'btn btn-primary');
          edit.type = 'button';
          edit.append(icon('edit'), document.createTextNode('Edit this map'));
          edit.addEventListener('click', () => {
            closePanel();
            small.refresh();
            small.root.hidden = false;
            edit.hidden = true;
            view.dataset.small = 'open';
          });
          tools.append(edit);
          editDock.append(small.root);
        } else {
          tools.append(editor.toolbar);
          // Drawing starts with the Map clear: the panel puts itself away.
          editor.toolbar.addEventListener('click', () => {
            if (editor?.editing()) closePanel();
          });
        }
        editDock.append(editor.panel);
      }

      // A mark of the drawing and a row of the places list open the entry's card (ADR 0350). Maps is
      // a desktop app, so a tap only selects.
      const preview = installEntryPreview({
        selector: '.m-mark[data-entry], .map-place[data-entry]',
        targetOf: (element) => {
          const entry = element.getAttribute('data-entry');
          return entry ? { tenant, id: entry } : null;
        },
        loadCard,
        loadPicture,
        touch: 'off',
      });
      cleanup = () => {
        editor?.destroy();
        controller?.destroy();
        preview.destroy();
      };
    } catch (error) {
      host.querySelector('[data-loading]')?.remove();
      host.replaceChildren(errorNotice(error));
    }
  };
  await render();
}
