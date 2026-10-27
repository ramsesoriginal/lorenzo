// Authoring a Map (ADR 0353): the toolbar, the tools the pointer belongs to while one is on, the
// panel for what is being drawn or what is selected, and every write. The renderer draws; this
// decides what a click means and asks the API. Nothing here is shown to those who may not write.
import {
  type Geometry,
  type MapViewController,
  type Overlay,
  ROLE_WORDS,
  ROLES,
  type Tool,
  type ToolEvent,
} from '@lorenzo/map-renderer';
import { LorenzoApiError } from './api';
import { button, el, field, groupTitle, message, select, statusLine } from './dom';
import {
  type Editable,
  editableOf,
  handlesOf,
  insertVertex,
  moveHandle,
  type Pt,
  placesInside,
  removeVertex,
  round2,
  toGeometry,
  translate,
} from './geometry-edit';
import { type Change, createHistory, type Step, writeFor } from './history';
import {
  batchPlacements,
  type EntryChoice,
  findEntries,
  makeLocation,
  partsOf,
  putPlacement,
  type Row,
  readPlacements,
  removePlacement,
  rowState,
} from './map-api';

export type EditorContext = {
  tenant: string;
  mapId: string;
  /** Whether everyone in the library may see the Map: the default for a new Location. */
  mapIsPublic: boolean;
  /** The sheet the Map draws on, `[x0, y0, x1, y1]`. */
  extent: [number, number, number, number];
  view: () => MapViewController;
  rows: () => Row[];
  /** Replaces the placements the page shows. */
  setRows: (rows: Row[]) => void;
  select: (id: string | null) => void;
};

export type Editor = {
  /** The switch and the tools; always there for those who may write. */
  toolbar: HTMLElement;
  /** What is being drawn, or what is selected, with the controls for it. */
  panel: HTMLElement;
  /** The page's selection changed. */
  selected(id: string | null): void;
  destroy(): void;
};

type ToolName = 'select' | 'pin' | 'circle' | 'line' | 'area';

const TOOLS: [ToolName, string][] = [
  ['select', 'Select'],
  ['pin', 'Pin'],
  ['circle', 'Circle'],
  ['line', 'Line'],
  ['area', 'Area'],
];

const STROKES: [string, string][] = [
  ['', "The theme's own"],
  ['solid', 'Solid'],
  ['dashed', 'Dashed'],
  ['dotted', 'Dotted'],
  ['double', 'Double'],
  ['none', 'Hit only (draws no line)'],
];

const WEIGHTS: [string, string][] = [
  ['', "The theme's own"],
  ['hairline', 'Hairline'],
  ['thin', 'Thin'],
  ['regular', 'Regular'],
  ['thick', 'Thick'],
  ['heavy', 'Heavy'],
];

const ROLE_OPTIONS: [string, string][] = [
  ['', 'No role'],
  ...ROLES.map((role): [string, string] => [
    role,
    ROLE_WORDS[role].charAt(0).toUpperCase() + ROLE_WORDS[role].slice(1),
  ]),
];

const BATCH_MAX = 100;

const same = (a: Pt, b: Pt) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 0.01;
const asText = (error: unknown) =>
  error instanceof LorenzoApiError ? error.message : message(error);

export function createEditor(context: EditorContext): Editor {
  const history = createHistory();
  const toolbar = el('div', '', 'row map-edit-bar');
  toolbar.setAttribute('role', 'group');
  toolbar.setAttribute('aria-label', 'Edit this map');
  const panel = el('div', '', 'stack-tight map-edit-panel');
  const status = statusLine();

  let editing = false;
  let toolName: ToolName = 'select';
  let target: { id?: string; name: string; create?: { isPublic: boolean } } | null = null;
  let draft: Pt[] = [];
  let rubber: Pt | null = null;
  let selectedId: string | null = null;
  // The selected shape while a handle or the shape is being dragged, drawn as an overlay.
  let working: Editable | null = null;
  let dragging: { handle: string | null; base: Editable; start: Pt } | null = null;
  let busy = false;

  const say = (text: string, failed = false) => {
    status.textContent = text;
    status.classList.toggle('error-text', failed);
    status.setAttribute('role', failed ? 'alert' : 'status');
  };
  const rowOf = (id: string | null) =>
    id ? context.rows().find((row) => row.id === id) : undefined;
  const inSheet = (p: Pt) =>
    p[0] >= context.extent[0] &&
    p[0] <= context.extent[2] &&
    p[1] >= context.extent[1] &&
    p[1] <= context.extent[3];

  // --- what is drawn over the map -------------------------------------------------------------

  function shapeOverlay(shape: Editable, id: string, handles: boolean, active?: string): Overlay {
    const out: Overlay[number][] = [];
    if (shape.kind === 'circle') out.push({ id, kind: 'disc', at: shape.at, r: shape.r });
    else if (shape.kind === 'line' || shape.kind === 'area') {
      out.push({ id, kind: 'line', pts: shape.pts, closed: shape.kind === 'area' });
    }
    if (handles) {
      for (const handle of handlesOf(shape)) {
        out.push({ id: handle.id, kind: 'handle', at: handle.at, active: handle.id === active });
      }
    }
    return out;
  }

  function overlay(): Overlay {
    if (!editing) return [];
    if (toolName !== 'select') {
      if (draft.length === 0) return [];
      const last = draft[draft.length - 1] as Pt;
      const out: Overlay[number][] = [];
      if (toolName === 'circle') {
        const r = rubber ? Math.hypot(rubber[0] - last[0], rubber[1] - last[1]) : 0;
        if (r > 0) out.push({ id: 'draft', kind: 'disc', at: last, r });
      } else {
        out.push({ id: 'draft', kind: 'line', pts: draft });
        if (rubber) out.push({ id: 'band', kind: 'line', pts: [last, rubber], preview: true });
      }
      for (const [i, at] of draft.entries()) out.push({ id: `d${i}`, kind: 'handle', at });
      return out;
    }
    const row = rowOf(selectedId);
    const shape = working ?? (row ? editableOf(row.geometry as unknown as Geometry) : null);
    return shape ? shapeOverlay(shape, 'shape', true, dragging?.handle ?? undefined) : [];
  }

  const refresh = () => context.view().setOverlay(overlay());

  // --- writing --------------------------------------------------------------------------------

  const upsert = (row: Row) => {
    const rows = context.rows();
    return rows.some((r) => r.id === row.id)
      ? rows.map((r) => (r.id === row.id ? row : r))
      : [...rows, row];
  };

  async function guarded(action: () => Promise<void>) {
    if (busy) return;
    busy = true;
    try {
      await action();
    } catch (error) {
      say(asText(error), true);
    } finally {
      busy = false;
      renderToolbar();
    }
  }

  async function reload() {
    context.setRows((await readPlacements(context.tenant, context.mapId)).rows);
  }

  async function saveRow(row: Row, patch: Partial<ReturnType<typeof rowState>>) {
    await guarded(async () => {
      const before = rowState(row);
      const after = { ...before, ...patch };
      const saved = await putPlacement(context.tenant, context.mapId, row.id, after);
      history.record([{ entry: row.id, before, after: rowState(saved) }]);
      context.setRows(upsert(saved));
      working = null;
      say('Saved.');
      render();
      refresh();
    });
  }

  async function removeRow(row: Row) {
    await guarded(async () => {
      await removePlacement(context.tenant, context.mapId, row.id);
      history.record([{ entry: row.id, before: rowState(row), after: null }]);
      context.setRows(context.rows().filter((r) => r.id !== row.id));
      context.select(null);
      say(`${row.name} is no longer on this map.`);
    });
  }

  async function finish(geometry: Geometry) {
    const chosen = target;
    if (!chosen) return;
    await guarded(async () => {
      let id = chosen.id;
      if (!id && chosen.create) {
        const made = await makeLocation(context.tenant, chosen.name, chosen.create.isPublic);
        id = made.id;
        // The Location exists now: a retry must not make another.
        target = { id, name: made.name };
      }
      if (!id) return;
      const before = rowOf(id);
      const role = toolName === 'pin' ? 'site' : null;
      const saved = await putPlacement(context.tenant, context.mapId, id, {
        geometry,
        role,
        style: null,
        z: 0,
      });
      history.record([
        { entry: id, before: before ? rowState(before) : null, after: rowState(saved) },
      ]);
      context.setRows(upsert(saved));
      draft = [];
      rubber = null;
      target = null;
      toolName = 'select';
      context.view().setTool(tool());
      context.select(id);
      say(`${saved.name} is on the map.`);
      render();
      refresh();
    });
  }

  async function applyStep(step: Step, direction: 'undo' | 'redo') {
    const put: NonNullable<Parameters<typeof batchPlacements>[2]['put']> = [];
    const remove: string[] = [];
    for (const change of step) {
      const write = writeFor(change, direction);
      if ('put' in write) {
        put.push({
          entry_id: write.put.entry_id,
          geometry: write.put.geometry,
          role: write.put.role,
          style: write.put.style,
          z: write.put.z,
        });
      } else remove.push(write.remove);
    }
    await batchPlacements(context.tenant, context.mapId, { put, remove });
    await reload();
    if (selectedId && !rowOf(selectedId)) context.select(null);
    say(direction === 'undo' ? 'Undone.' : 'Done again.');
    render();
    refresh();
  }

  const undo = () =>
    guarded(async () => {
      const step = history.undo();
      if (!step) return;
      try {
        await applyStep(step, 'undo');
      } catch (error) {
        history.redo();
        throw error;
      }
    });
  const redo = () =>
    guarded(async () => {
      const step = history.redo();
      if (!step) return;
      try {
        await applyStep(step, 'redo');
      } catch (error) {
        history.undo();
        throw error;
      }
    });

  async function placeChildren(
    row: Row,
    shape: Editable,
    children: { id: string; name: string }[],
  ) {
    await guarded(async () => {
      const chosen = children.slice(0, BATCH_MAX);
      const spots = placesInside(shape, chosen.length);
      if (spots.length < chosen.length) {
        say('There is no room inside this shape for that many places.', true);
        return;
      }
      const put = chosen.map((child, i) => ({
        entry_id: child.id,
        geometry: toGeometry({ kind: 'point', at: spots[i] as Pt }) as unknown as Record<
          string,
          unknown
        >,
        role: 'site' as string | null,
        style: null,
        z: 0,
      }));
      await batchPlacements(context.tenant, context.mapId, { put });
      const step: Change[] = put.map((item) => ({
        entry: item.entry_id,
        before: null,
        after: { geometry: item.geometry, role: item.role, style: null, z: 0 },
      }));
      history.record(step);
      await reload();
      say(
        children.length > chosen.length
          ? `Placed ${chosen.length} places inside ${row.name}; ${children.length - chosen.length} more remain.`
          : `Placed ${chosen.length} places inside ${row.name}.`,
      );
      render();
      refresh();
    });
  }

  // --- the tools ------------------------------------------------------------------------------

  const finishDraft = () => {
    if (toolName === 'line' && draft.length >= 2) {
      void finish(toGeometry({ kind: 'line', pts: draft }));
    } else if (toolName === 'area' && draft.length >= 3) {
      void finish(toGeometry({ kind: 'area', pts: draft }));
    } else {
      say(toolName === 'line' ? 'A line needs two points.' : 'An area needs three points.', true);
    }
  };

  const selectTool: Tool = {
    down(event: ToolEvent) {
      const row = rowOf(selectedId);
      const base = row ? editableOf(row.geometry as unknown as Geometry) : null;
      if (!row || !base) return false;
      if (event.handle || event.hit === row.id) {
        dragging = { handle: event.handle, base, start: event.point };
        working = base;
        return true;
      }
      return false;
    },
    drag(event: ToolEvent) {
      if (!dragging) return;
      const { handle, base, start } = dragging;
      working = handle
        ? moveHandle(base, handle, event.point)
        : translate(base, event.point[0] - start[0], event.point[1] - start[1]);
      refresh();
    },
    up() {
      const drag = dragging;
      const shape = working;
      dragging = null;
      const row = rowOf(selectedId);
      if (!drag || !shape || !row || JSON.stringify(shape) === JSON.stringify(drag.base)) {
        working = null;
        refresh();
        return;
      }
      void saveRow(row, { geometry: toGeometry(shape) });
    },
  };

  const drawTool: Tool = {
    cursor: 'crosshair',
    click(event: ToolEvent) {
      if (!target) {
        say('Choose what you are drawing first.', true);
        return true;
      }
      const p: Pt = [round2(event.point[0]), round2(event.point[1])];
      if (!inSheet(p)) return true;
      if (toolName === 'pin') {
        void finish(toGeometry({ kind: 'point', at: p }));
      } else if (toolName === 'circle') {
        const centre = draft[0];
        if (!centre) draft = [p];
        else if (!same(centre, p)) {
          void finish(
            toGeometry({
              kind: 'circle',
              at: centre,
              r: Math.hypot(p[0] - centre[0], p[1] - centre[1]),
            }),
          );
        }
      } else {
        const last = draft[draft.length - 1];
        if (!last || !same(last, p)) draft = [...draft, p];
      }
      refresh();
      render();
      return true;
    },
    dblclick() {
      if (toolName === 'line' || toolName === 'area') finishDraft();
      return true;
    },
    move(event: ToolEvent) {
      if (draft.length === 0) return;
      rubber = event.point;
      refresh();
    },
    key(event: KeyboardEvent) {
      if (event.key === 'Enter' && (toolName === 'line' || toolName === 'area')) {
        finishDraft();
        return true;
      }
      if (event.key === 'Backspace' && draft.length > 0) {
        draft = draft.slice(0, -1);
        refresh();
        render();
        return true;
      }
      if (event.key === 'Escape') {
        if (draft.length > 0) draft = [];
        else setTool('select');
        rubber = null;
        refresh();
        render();
        return true;
      }
      return false;
    },
  };

  const tool = (): Tool | null => (!editing ? null : toolName === 'select' ? selectTool : drawTool);

  function setTool(next: ToolName) {
    toolName = next;
    draft = [];
    rubber = null;
    working = null;
    dragging = null;
    if (next === 'select') target = null;
    context.view().setTool(tool());
    renderToolbar();
    render();
    refresh();
  }

  // --- the toolbar ----------------------------------------------------------------------------

  function renderToolbar() {
    toolbar.replaceChildren();
    const toggle = el('button', editing ? 'Stop editing' : 'Edit this map', 'btn btn-secondary');
    toggle.type = 'button';
    toggle.setAttribute('aria-pressed', String(editing));
    toggle.addEventListener('click', () => {
      editing = !editing;
      if (!editing) {
        toolName = 'select';
        draft = [];
        target = null;
        working = null;
      }
      context.view().setTool(tool());
      renderToolbar();
      render();
      refresh();
    });
    toolbar.append(toggle);
    if (!editing) return;
    const tools = el('div', '', 'row-tight');
    tools.setAttribute('role', 'group');
    tools.setAttribute('aria-label', 'Tool');
    for (const [name, label] of TOOLS) {
      const node = el('button', label, 'btn btn-secondary');
      node.type = 'button';
      node.setAttribute('aria-pressed', String(toolName === name));
      node.addEventListener('click', () => setTool(name));
      tools.append(node);
    }
    const undoButton = el('button', 'Undo', 'btn btn-secondary');
    undoButton.type = 'button';
    undoButton.disabled = busy || !history.canUndo();
    undoButton.addEventListener('click', () => void undo());
    const redoButton = el('button', 'Redo', 'btn btn-secondary');
    redoButton.type = 'button';
    redoButton.disabled = busy || !history.canRedo();
    redoButton.addEventListener('click', () => void redo());
    toolbar.append(tools, undoButton, redoButton, status);
  }

  // --- the panel ------------------------------------------------------------------------------

  function chooser(): HTMLElement {
    const box = el('div', '', 'stack-tight');
    const label = TOOLS.find(([name]) => name === toolName)?.[1] ?? '';
    box.append(groupTitle('h3', `Draw: ${label.toLowerCase()}`));
    if (target) {
      const placed = target.id ? rowOf(target.id) : undefined;
      box.append(
        el('p', target.create ? `A new Location, ${target.name}` : target.name, 'status-text'),
      );
      if (placed) {
        box.append(
          el(
            'p',
            'It is already on this Map; drawing it again replaces its drawing.',
            'status-text',
          ),
        );
      }
      box.append(
        el(
          'p',
          toolName === 'pin'
            ? 'Click the map to place it.'
            : toolName === 'circle'
              ? 'Click the centre, then the edge.'
              : 'Click each point. Press Enter or double-click to finish, Backspace to take back a point, Escape to start again.',
          'status-text',
        ),
      );
      box.append(
        button('Choose another', () => {
          target = null;
          draft = [];
          refresh();
          render();
        }),
      );
      return box;
    }
    const search = field('Find an entry by name');
    search.input.type = 'search';
    const results = el('ul', '', 'list');
    let sequence = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    search.input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const mine = ++sequence;
        const query = search.input.value.trim();
        if (!query) {
          results.replaceChildren();
          return;
        }
        void findEntries(context.tenant, query)
          .then((found: EntryChoice[]) => {
            if (mine !== sequence) return;
            results.replaceChildren(
              ...(found.length
                ? found.map((entry) => {
                    const item = el('li');
                    const pick = el('button', entry.name, 'place-toggle map-place');
                    pick.type = 'button';
                    pick.addEventListener('click', () => {
                      target = { id: entry.id, name: entry.name };
                      render();
                    });
                    if (entry.kinds.length) {
                      pick.append(el('span', entry.kinds.join(', ').replaceAll('_', ' '), 'chip'));
                    }
                    item.append(pick);
                    return item;
                  })
                : [el('li', 'No entry has that name.', 'status-text')]),
            );
          })
          .catch((error) => say(asText(error), true));
      }, 250);
    });
    box.append(search.label, results);
    const fresh = el('form', '', 'stack-tight');
    const name = field('Or make a new Location, named');
    name.input.required = true;
    const open = field('Open it to the library', '', 'checkbox');
    open.input.checked = context.mapIsPublic;
    const use = el('button', 'Draw a new Location', 'btn btn-secondary');
    use.type = 'submit';
    fresh.append(name.label, open.label, use);
    fresh.addEventListener('submit', (event) => {
      event.preventDefault();
      const text = name.input.value.trim();
      if (!text) return;
      target = { name: text, create: { isPublic: open.input.checked } };
      render();
    });
    box.append(fresh);
    return box;
  }

  function pointFields(row: Row, shape: Editable): HTMLElement {
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h4', 'Points'));
    const inputs: HTMLInputElement[][] = [];
    const commit = () => {
      const number = (input: HTMLInputElement | undefined) => Number(input?.value ?? Number.NaN);
      const values = inputs.map((pair) => pair.map(number));
      if (values.some((pair) => pair.some((n) => !Number.isFinite(n)))) {
        say('Every point needs two numbers.', true);
        return;
      }
      const at = (i: number): Pt => [values[i]?.[0] ?? 0, values[i]?.[1] ?? 0];
      let next: Editable;
      if (shape.kind === 'point') next = { kind: 'point', at: at(0) };
      else if (shape.kind === 'circle')
        next = { kind: 'circle', at: at(0), r: values[1]?.[0] ?? shape.r };
      else next = { kind: shape.kind, pts: values.map((_, i) => at(i)) };
      void saveRow(row, { geometry: toGeometry(next) });
    };
    // One point is one group of its own: a legend and two short fields, so a screen reader says
    // "Point 2, x" and the fields stay narrow beside their buttons.
    const pair = (label: string, x: number, y: number | null, index: number) => {
      const line = el('fieldset', '', 'map-point');
      line.append(el('legend', label, 'map-point-name'));
      const first = field(y === null ? 'Value' : 'x', String(x), 'number');
      first.input.step = 'any';
      first.input.addEventListener('change', commit);
      const group: HTMLInputElement[] = [first.input];
      line.append(first.label);
      if (y !== null) {
        const second = field('y', String(y), 'number');
        second.input.step = 'any';
        second.input.addEventListener('change', commit);
        group.push(second.input);
        line.append(second.label);
      }
      inputs[index] = group;
      return line;
    };
    // A small button whose visible word is part of the longer name a screen reader says.
    const small = (word: string, name: string, action: () => Promise<void>) => {
      const node = button(word, action, { variant: 'secondary' });
      node.setAttribute('aria-label', name);
      node.classList.add('map-point-button');
      return node;
    };
    if (shape.kind === 'point') box.append(pair('Point', shape.at[0], shape.at[1], 0));
    else if (shape.kind === 'circle') {
      box.append(pair('Centre', shape.at[0], shape.at[1], 0), pair('Radius', shape.r, null, 1));
    } else {
      for (const [i, at] of shape.pts.entries()) {
        const line = pair(`Point ${i + 1}`, at[0], at[1], i);
        const after = insertVertex(shape, i);
        line.append(
          small('Add', `Add a point after point ${i + 1}`, () =>
            saveRow(row, { geometry: toGeometry(after) }),
          ),
        );
        const without = removeVertex(shape, i);
        if (without) {
          line.append(
            small('Remove', `Remove point ${i + 1}`, () =>
              saveRow(row, { geometry: toGeometry(without) }),
            ),
          );
        }
        box.append(line);
      }
    }
    return box;
  }

  function childrenControl(row: Row, shape: Editable): HTMLElement | null {
    if (!row.kinds.includes('location') || (shape.kind !== 'area' && shape.kind !== 'circle')) {
      return null;
    }
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h4', 'Places inside'));
    const line = el('p', 'Looking for what is inside…', 'status-text');
    box.append(line);
    void partsOf(context.tenant, row.id)
      .then((parts) => {
        const placed = new Set(context.rows().map((r) => r.id));
        const missing = parts.filter((part) => !placed.has(part.id));
        if (missing.length === 0) {
          line.textContent = parts.length
            ? 'Everything inside it is on this map.'
            : 'Nothing is inside it yet.';
          return;
        }
        line.textContent = `${missing.length} of the places inside ${row.name} are not on this map.`;
        line.after(
          button(
            `Place ${Math.min(missing.length, BATCH_MAX)} inside it`,
            () => placeChildren(row, shape, missing),
            { variant: 'secondary' },
          ),
        );
      })
      .catch((error) => {
        line.textContent = asText(error);
        line.classList.add('error-text');
      });
    return box;
  }

  function editPanel(row: Row): HTMLElement {
    const box = el('div', '', 'stack-tight');
    box.append(groupTitle('h3', `Change ${row.name}`));
    const role = select('Role', ROLE_OPTIONS, row.role ?? '');
    role.input.addEventListener(
      'change',
      () => void saveRow(row, { role: role.input.value || null }),
    );
    const stroke = select('Line', STROKES, (row.style as { stroke?: string } | null)?.stroke ?? '');
    const weight = select(
      'Weight',
      WEIGHTS,
      (row.style as { weight?: string } | null)?.weight ?? '',
    );
    const saveStyle = () => {
      const style: Record<string, string> = {};
      if (stroke.input.value) style.stroke = stroke.input.value;
      if (weight.input.value) style.weight = weight.input.value;
      void saveRow(row, { style: Object.keys(style).length ? style : null });
    };
    stroke.input.addEventListener('change', saveStyle);
    weight.input.addEventListener('change', saveStyle);
    const order = field('Drawing order (−100 to 100)', String(row.z), 'number');
    order.input.min = '-100';
    order.input.max = '100';
    order.input.step = '1';
    order.input.addEventListener('change', () => {
      const z = Number(order.input.value);
      if (!Number.isInteger(z) || z < -100 || z > 100) {
        say('The drawing order is a whole number from −100 to 100.', true);
        return;
      }
      void saveRow(row, { z });
    });
    box.append(role.label, stroke.label, weight.label, order.label);
    const shape = editableOf(row.geometry as unknown as Geometry);
    if (shape) {
      box.append(pointFields(row, shape));
      const children = childrenControl(row, shape);
      if (children) box.append(children);
    } else {
      box.append(
        el(
          'p',
          'This drawing has several parts, curves or holes: it is drawn with the API.',
          'status-text',
        ),
      );
    }
    box.append(button('Remove from this map', () => removeRow(row), { variant: 'danger' }));
    return box;
  }

  function render() {
    panel.replaceChildren();
    panel.hidden = !editing;
    if (!editing) return;
    if (toolName !== 'select') {
      panel.append(chooser());
      return;
    }
    const row = rowOf(selectedId);
    if (row) panel.append(editPanel(row));
    else {
      panel.append(
        el(
          'p',
          'Select a place on the map or in the list to change it, or choose a tool to draw.',
          'status-text',
        ),
      );
    }
  }

  // Undo and redo from the keyboard, unless a field has the keys.
  const onKey = (event: KeyboardEvent) => {
    if (!editing || !(event.ctrlKey || event.metaKey) || event.altKey) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest('input, textarea, select')) return;
    const key = event.key.toLowerCase();
    if (key === 'z' && !event.shiftKey) {
      event.preventDefault();
      void undo();
    } else if (key === 'y' || (key === 'z' && event.shiftKey)) {
      event.preventDefault();
      void redo();
    }
  };
  document.addEventListener('keydown', onKey);

  renderToolbar();
  render();

  return {
    toolbar,
    panel,
    selected(id) {
      selectedId = id;
      working = null;
      if (editing && toolName === 'select') {
        render();
        refresh();
      }
    },
    destroy() {
      document.removeEventListener('keydown', onKey);
      context.view().setTool(null);
      context.view().setOverlay([]);
    },
  };
}
