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
import { loadLayers } from './layer-pictures';
import { picturesSection } from './layers-settings';
import { chosenTheme, LOOKS, type Look, readLook, writeLook } from './look';
import { type Header, type Row, readPlacements, VISIBLE_LIMIT } from './map-api';
import { createEditor, type Editor } from './map-edit';
import { createLegend } from './map-legend';
import { makeMapForm, settingsSection } from './map-settings';
import { canManage, libraryName, myLibraries } from './names';
import { loadCard, loadPicture } from './previews';
import { start } from './sign-in';
import {
  PROJECTION_WORDS,
  positionWords,
  projectionFrom,
  readProjectionChoice,
  type Turn,
  turned,
  writeProjectionChoice,
} from './sphere-words';
import { resolveEntry } from './views';

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
    if (manage) {
      const add = el('section', '', 'stack');
      add.append(
        sectionHead('Make a Map'),
        makeMapForm(scope, (id, slug) => location.assign(mapHref(scope, id, slug))),
      );
      view.append(add);
    }
    host.replaceChildren(view);
    await show();
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

/** What the selection panel says of one placement. */
async function describe(tenant: string, row: Row, panel: HTMLElement, where: string | null = null) {
  panel.replaceChildren();
  const isLocation = row.kinds.includes('location');
  const title = el('h3', '', 'group-title');
  title.append(isLocation ? link(row.name, locationHref(tenant, row.id, row.slug)) : row.name);
  panel.append(title);
  const others = row.kinds.map(words);
  if (others.length) panel.append(el('p', others.join(', '), 'status-text'));
  if (row.role) panel.append(el('p', words(row.role), 'chip'));
  if (where) panel.append(el('p', where, 'status-text'));
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
  const render = async () => {
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
      const [name, manage, found] = await Promise.all([
        libraryName(tenant),
        canManage(tenant),
        readPlacements(tenant, id),
      ]);
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

      const view = el('div', '', 'stack view');
      const meta: Node[] = [];
      if (name) meta.push(metaLine('kind-location', name));
      if (writer && header.is_public !== null && header.is_public !== undefined)
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

      // The toolbar: what is drawn, the look, the zoom, and the way back to the whole sheet.
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
      const legend = createLegend();
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
      toolbar.append(looks);

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
      if (onSphere) toolbar.append(drawnAs, turnBar);
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
      toolbar.append(zoomControls);

      // The drawing and a tip.
      const stage = el('div', '', 'map-stage');
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
        if (row) void describe(tenant, row, panel, pinCell(row));
        else noSelection();
        centre.hidden = !row;
        if (row) centre.textContent = `Centre on ${row.name}`;
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

      const drawing = el('section', '', 'stack');
      drawing.append(sectionHead('The map'), toolbar);
      const layoutRow = el('div', '', 'map-layout');
      const left = el('div', '', 'stack');
      const side = el('div', '', 'stack');
      side.append(panel);
      // Pictures load after the drawing, and say so when some could not be shown (ADR 0362).
      const pictureNote = el('p', '', 'status-text');
      pictureNote.setAttribute('role', 'status');
      left.append(stage, tip, pictureNote);
      if (writer && (header.layers ?? []).some((layer) => layer.needs_review)) {
        side.append(
          el(
            'p',
            'A picture under this Map was replaced after it was set up. Look at it against the places, then mark it reviewed in Settings.',
            'status-text',
          ),
        );
      }
      layoutRow.append(left, side);
      drawing.append(layoutRow, legend.root);
      view.append(drawing);
      if (found.more)
        view.append(
          el(
            'p',
            `This Map holds more than the ${VISIBLE_LIMIT.toLocaleString('en')} places shown here.`,
            'status-text',
          ),
        );
      view.append(places);
      if (writer) {
        const settings = el('section', '', 'stack');
        settings.append(sectionHead('Settings'), settingsSection(tenant, header, version, render));
        if (!onSphere) {
          settings.append(
            sectionHead('Pictures'),
            picturesSection({ tenant, header, version, again: render }),
          );
        }
        view.append(settings);
      }
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
          if (row) void describe(tenant, row, panel, pinCell(row));
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
        drawing.insertBefore(editor.toolbar, layoutRow);
        side.append(editor.panel);
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
