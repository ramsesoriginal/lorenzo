// The compare grid and the Table pane (ADR 0249): entries as rows, stats as columns, each cell
// edited through the command layer. The Table pane is the same grid, smaller, in the corner of
// the workbench; the Compare pane is the whole of it, with selections of many cells.

import type { Bench } from '../core/bench';
import { canEditStat, type StatDef } from '../core/transport';
import { redraw } from './entryPane';
import {
  add,
  cellsOf,
  clamp,
  defaultColumns,
  fromTsv,
  gridOrder,
  normalise,
  parseCell,
  type Range,
  showCell,
  stepOf,
  toTsv,
  type Values,
  valueSource,
  valuesOf,
} from './gridModel';

/** What a grid remembers while the page is drawn again around it. */
export interface GridState {
  order: 'inherits' | 'name';
  filter: string;
  /** The stats shown, by id; null until a person chooses, then the numeric ones. */
  columns: string[] | null;
  anchor: { row: number; col: number } | null;
  focus: { row: number; col: number } | null;
  editing: { row: number; col: number; seed: string | null } | null;
  scroll: number;
  columnsOpen: boolean;
  /** What a cell that was typed in a way that cannot be read said. */
  problem: string | null;
}

export const newGridState = (): GridState => ({
  order: 'inherits',
  filter: '',
  columns: null,
  anchor: null,
  focus: null,
  editing: null,
  scroll: 0,
  columnsOpen: false,
  problem: null,
});

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const button = (label: string, onClick: () => void, cls = 'btn') => {
  const b = el('button', cls, label);
  b.type = 'button';
  b.addEventListener('click', onClick);
  return b;
};

export interface GridOptions {
  /** The Table pane: the first three numeric stats, no toolbar, a way to open the whole grid. */
  compact: boolean;
  /** Draw the page again (the state changed). */
  redraw: () => void;
  go: (id: string) => void;
  openGrid?: () => void;
}

export function renderGrid(bench: Bench, state: GridState, opts: GridOptions): HTMLElement {
  const root = el('div', opts.compact ? 'pane pane-table' : 'pane pane-grid');
  void bench.loadAll();
  const { read, of } = bench.loaded();

  const defs = new Map(bench.statDefs.map((d) => [d.id, d]));
  const columns = (state.columns ?? defaultColumns(bench.statDefs, opts.compact ? 3 : 4))
    .map((id) => defs.get(id))
    .filter((d): d is StatDef => d !== undefined);
  const rows = gridOrder(bench.listing(), state.order, state.filter);
  // The sources of inherited values need what is above a row, which may not be in the rows shown.
  const listing = bench.listing();
  const byId = new Map(listing.map((e) => [e.id, e]));
  const values = new Map<string, Values>();
  for (const e of listing) values.set(e.id, valuesOf(bench.view(e.id)));

  const rerender = () => opts.redraw();
  const cellDef = (col: number) => columns[col];
  const lastRow = rows.length - 1;
  const lastCol = columns.length - 1;

  // ---- writing --------------------------------------------------------------------------------

  const writeCell = (row: number, col: number, text: string): boolean => {
    const entry = rows[row]?.entry;
    const def = cellDef(col);
    if (!entry || !def || !canEditStat(def.type)) return false;
    if (def.type === 'enum') {
      const ok = text.trim() === '' || def.enumValues.includes(text.trim());
      if (!ok) return false;
      bench.setStat(entry.id, def.id, text.trim() === '' ? null : text.trim());
      return true;
    }
    const value = parseCell(def.type, text);
    if (value === undefined) return false;
    bench.setStat(entry.id, def.id, value);
    return true;
  };
  const effective = (row: number, col: number): number | null => {
    const entry = rows[row]?.entry;
    const def = cellDef(col);
    const v = entry && def ? values.get(entry.id)?.get(def.id)?.value : null;
    return typeof v === 'number' ? v : null;
  };
  const selection = (): Range | null =>
    state.anchor && state.focus
      ? { r0: state.anchor.row, c0: state.anchor.col, r1: state.focus.row, c1: state.focus.col }
      : null;
  const selected = () => {
    const sel = selection();
    return sel ? cellsOf(sel) : [];
  };
  const applyToSelection = (fn: (row: number, col: number) => void) => {
    for (const { row, col } of selected()) fn(row, col);
  };

  // ---- toolbar (the whole grid only) ----------------------------------------------------------

  if (!opts.compact) {
    const bar = el('div', 'grid-bar');
    const filter = el('input', 'grid-filter');
    filter.type = 'search';
    filter.placeholder = 'Filter entries';
    filter.value = state.filter;
    filter.dataset.key = 'grid-filter';
    filter.setAttribute('aria-label', 'Filter the grid');
    filter.addEventListener('input', () => {
      if (filter.value === state.filter) return;
      state.filter = filter.value;
      state.anchor = state.focus = null;
      rerender();
    });
    const seg = el('div', 'seg');
    seg.setAttribute('role', 'group');
    seg.setAttribute('aria-label', 'Grid order');
    for (const [o, label] of [
      ['inherits', 'By inheritance'],
      ['name', 'A to Z'],
    ] as const) {
      const b = button(label, () => {
        state.order = o;
        state.anchor = state.focus = null;
        rerender();
      });
      b.setAttribute('aria-pressed', String(state.order === o));
      seg.append(b);
    }
    const count = el(
      'span',
      'muted',
      read < of
        ? `Reading ${read} of ${of} entries…`
        : `${new Set(rows.map((r) => r.entry.id)).size} of ${of} entries`,
    );
    const pick = button('Columns', () => {
      state.columnsOpen = !state.columnsOpen;
      rerender();
    });
    pick.setAttribute('aria-expanded', String(state.columnsOpen));
    bar.append(filter, seg, count, pick);
    root.append(bar);
    if (state.columnsOpen) {
      const menu = el('div', 'grid-columns');
      menu.setAttribute('role', 'group');
      menu.setAttribute('aria-label', 'Columns');
      const shown = new Set(columns.map((c) => c.id));
      for (const d of bench.statDefs) {
        const label = el('label', 'grid-col-choice');
        const box = el('input');
        box.type = 'checkbox';
        box.checked = shown.has(d.id);
        box.addEventListener('change', () => {
          const next = bench.statDefs
            .map((x) => x.id)
            .filter((id) => (id === d.id ? box.checked : shown.has(id)));
          state.columns = next;
          state.anchor = state.focus = null;
          rerender();
        });
        label.append(box, document.createTextNode(` ${d.name}`));
        menu.append(label);
      }
      root.append(menu);
    }
  } else {
    const note = el('div', 'grid-note');
    note.append(el('span', 'muted', 'Edit any cell; every view follows.'));
    if (opts.openGrid) note.append(button('Open as grid', opts.openGrid, 'lnk'));
    root.append(note);
  }

  // ---- selection bar --------------------------------------------------------------------------

  const cells = selected();
  if (!opts.compact && cells.length) {
    const sel = normalise(selection() as Range);
    const bar = el('div', 'grid-selbar');
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'Change the selected cells');
    const stat = sel.c0 === sel.c1 ? ` · ${cellDef(sel.c0)?.name ?? ''}` : '';
    bar.append(
      el('span', undefined, `${cells.length} ${cells.length === 1 ? 'cell' : 'cells'}${stat}`),
    );
    const value = el('input', 'grid-set');
    value.type = 'text';
    value.placeholder = 'Value';
    value.setAttribute('aria-label', 'Value for the selected cells');
    value.dataset.key = 'grid-set';
    const set = () => {
      let bad = false;
      applyToSelection((r, c) => {
        if (!writeCell(r, c, value.value)) bad = true;
      });
      state.problem = bad ? 'Some cells did not take that value.' : null;
      rerender();
    };
    value.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        set();
      }
    });
    const nudge = (sign: 1 | -1) => () => {
      applyToSelection((r, c) => {
        const def = cellDef(c);
        const step = def ? stepOf(def.type) : null;
        const now = effective(r, c);
        if (def && step !== null) {
          const entry = rows[r]?.entry;
          if (entry) bench.setStat(entry.id, def.id, add(now ?? 0, sign * step));
        }
      });
      rerender();
    };
    const fill = () => {
      const r = normalise(selection() as Range);
      for (let col = r.c0; col <= r.c1; col++) {
        const def = cellDef(col);
        const from = values.get(rows[r.r0]?.entry.id ?? '')?.get(def?.id ?? '')?.value;
        if (!def || from === undefined || from === null) continue;
        for (let row = r.r0 + 1; row <= r.r1; row++) {
          const entry = rows[row]?.entry;
          if (entry) bench.setStat(entry.id, def.id, from);
        }
      }
      rerender();
    };
    const inherit = () => {
      applyToSelection((r, c) => {
        const entry = rows[r]?.entry;
        const def = cellDef(c);
        if (entry && def) bench.setStat(entry.id, def.id, null);
      });
      rerender();
    };
    bar.append(
      value,
      button('Set', set),
      button('−', nudge(-1)),
      button('+', nudge(1)),
      button('Fill down', fill),
      button('Make inherit', inherit),
      button('×', () => {
        state.anchor = state.focus = null;
        rerender();
      }),
    );
    root.append(bar);
  }
  if (state.problem) {
    const p = el('p', 'bad', state.problem);
    p.setAttribute('role', 'alert');
    root.append(p);
  }

  // ---- the table ------------------------------------------------------------------------------

  const wrap = el('div', 'grid-scroll');
  const table = el('table', 'grid');
  table.tabIndex = 0;
  table.dataset.key = opts.compact ? 'table' : 'grid';
  table.setAttribute('role', 'grid');
  table.setAttribute('aria-label', opts.compact ? 'Table' : 'Compare');
  const head = el('tr');
  head.append(el('th', undefined, 'Name'));
  if (opts.compact) head.append(el('th', undefined, 'Inherits from'));
  for (const d of columns) head.append(el('th', undefined, d.name));
  const thead = el('thead');
  thead.append(head);
  table.append(thead);
  const body = el('tbody');
  const inRange = (row: number, col: number) => {
    const sel = selection();
    if (!sel) return false;
    const r = normalise(sel);
    return row >= r.r0 && row <= r.r1 && col >= r.c0 && col <= r.c1;
  };
  rows.forEach(({ entry, depth }, row) => {
    const tr = el('tr');
    const nameCell = el('th', 'grid-name');
    nameCell.scope = 'row';
    nameCell.style.paddingLeft = `${8 + depth * 14}px`;
    nameCell.append(button(entry.name, () => opts.go(entry.id), 'lnk'));
    tr.append(nameCell);
    if (opts.compact) {
      const parents = entry.parentIds.map((p) => bench.displayName(p)).join(', ');
      tr.append(el('td', 'muted', parents || 'None'));
    }
    columns.forEach((def, col) => {
      const td = el('td', 'grid-cell');
      td.dataset.cell = `${row},${col}`;
      td.setAttribute('role', 'gridcell');
      const mine = values.get(entry.id)?.get(def.id);
      const source = valueSource(byId, values, entry.id, def.id);
      if (inRange(row, col)) td.classList.add('sel');
      if (state.focus?.row === row && state.focus.col === col) td.classList.add('cur');
      if (state.editing?.row === row && state.editing.col === col) {
        td.append(
          editorFor(bench, def, mine?.value ?? null, state, row, col, writeCell, rerender, lastRow),
        );
      } else {
        const shown = showCell(mine?.value);
        if (source.kind === 'inherited') {
          td.classList.add('inh');
          td.title = `From ${bench.displayName(source.from)}`;
          td.append(
            el('span', 'grid-from', `↳ ${bench.displayName(source.from)} `),
            document.createTextNode(shown),
          );
        } else td.append(document.createTextNode(shown || '—'));
        if (!shown) td.classList.add('blank');
      }
      td.addEventListener('mousedown', (ev) => {
        if (state.editing) return;
        if (ev.shiftKey && state.anchor) state.focus = { row, col };
        else state.anchor = state.focus = { row, col };
        rerender();
        ev.preventDefault();
        (
          document.querySelector(`[data-key="${table.dataset.key}"]`) as HTMLElement | null
        )?.focus();
      });
      td.addEventListener('dblclick', () => {
        state.editing = { row, col, seed: null };
        rerender();
      });
      tr.append(td);
    });
    body.append(tr);
  });
  table.append(body);

  // ---- keyboard and clipboard -----------------------------------------------------------------

  table.addEventListener('keydown', (ev) => {
    if (state.editing || ev.target !== table) return;
    const cur = state.focus ?? { row: 0, col: 0 };
    const move = (dr: number, dc: number) => {
      const next = { row: clamp(cur.row + dr, lastRow), col: clamp(cur.col + dc, lastCol) };
      state.focus = next;
      if (!ev.shiftKey || !state.anchor) state.anchor = next;
      ev.preventDefault();
      rerender();
    };
    if (ev.key === 'ArrowDown') return move(1, 0);
    if (ev.key === 'ArrowUp') return move(-1, 0);
    if (ev.key === 'ArrowLeft') return move(0, -1);
    if (ev.key === 'ArrowRight') return move(0, 1);
    if (!state.focus) return;
    if (ev.key === 'Enter' || ev.key === 'F2') {
      ev.preventDefault();
      state.editing = { ...state.focus, seed: null };
      rerender();
    } else if (ev.key === 'Delete' || ev.key === 'Backspace') {
      ev.preventDefault();
      applyToSelection((r, c) => {
        const entry = rows[r]?.entry;
        const def = cellDef(c);
        if (entry && def) bench.setStat(entry.id, def.id, null);
      });
      rerender();
    } else if (ev.key === 'Escape') {
      state.anchor = state.focus = null;
      rerender();
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'c') {
      ev.preventDefault();
      const r = normalise(selection() as Range);
      const text = toTsv(
        Array.from({ length: r.r1 - r.r0 + 1 }, (_, i) =>
          Array.from({ length: r.c1 - r.c0 + 1 }, (_, j) =>
            showCell(
              values.get(rows[r.r0 + i]?.entry.id ?? '')?.get(cellDef(r.c0 + j)?.id ?? '')?.value,
            ),
          ),
        ),
      );
      void navigator.clipboard?.writeText(text);
    } else if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      // Typing replaces what is there.
      ev.preventDefault();
      state.editing = { ...state.focus, seed: ev.key };
      rerender();
    }
  });
  table.addEventListener('paste', (ev) => {
    if (state.editing || !state.focus) return;
    const text = ev.clipboardData?.getData('text/plain');
    if (!text) return;
    ev.preventDefault();
    const start = normalise(selection() as Range);
    let bad = 0;
    for (const [i, line] of fromTsv(text).entries()) {
      for (const [j, cell] of line.entries()) {
        const row = start.r0 + i;
        const col = start.c0 + j;
        if (row <= lastRow && col <= lastCol && !writeCell(row, col, cell)) bad++;
      }
    }
    state.problem = bad
      ? `${bad} pasted ${bad === 1 ? 'value' : 'values'} did not fit their cell.`
      : null;
    rerender();
  });
  wrap.addEventListener('scroll', () => {
    state.scroll = wrap.scrollTop;
  });
  wrap.append(table);
  root.append(wrap);
  queueMicrotask(() => {
    wrap.scrollTop = state.scroll;
  });

  // ---- where the focused cell's value comes from (the whole grid only) ------------------------

  if (!opts.compact && state.focus) {
    const entry = rows[state.focus.row]?.entry;
    const def = cellDef(state.focus.col);
    if (entry && def) {
      const source = valueSource(byId, values, entry.id, def.id);
      const card = el('div', 'grid-source');
      card.append(el('strong', undefined, entry.name));
      card.append(
        document.createTextNode(
          source.kind === 'own'
            ? ` · ${def.name} is set on this entry.`
            : source.kind === 'inherited'
              ? ` · ${def.name} comes from ${bench.displayName(source.from)}. `
              : ` · ${def.name} is not set on ${entry.name} or on anything it inherits from.`,
        ),
      );
      if (source.kind === 'inherited')
        card.append(
          button(`Go to ${bench.displayName(source.from)}`, () => opts.go(source.from), 'lnk'),
        );
      root.append(card);
    }
  }
  return root;
}

/** The control in a cell being edited: a field, or a choice for a tag and a choice of values. */
function editorFor(
  _bench: Bench,
  def: StatDef,
  current: unknown,
  state: GridState,
  row: number,
  col: number,
  write: (row: number, col: number, text: string) => boolean,
  rerender: () => void,
  lastRow: number,
): HTMLElement {
  const done = (text: string | null, down: boolean) => {
    state.editing = null;
    if (text !== null && !write(row, col, text))
      state.problem = `That is not a ${def.type} value for ${def.name}.`;
    else state.problem = null;
    if (down) {
      state.focus = state.anchor = { row: Math.min(row + 1, lastRow), col };
    }
    rerender();
  };
  const hold = state.editing?.seed ?? null;
  if (def.type === 'bool' || def.type === 'enum') {
    const select = el('select', 'grid-edit');
    select.dataset.key = 'grid-edit';
    select.setAttribute('aria-label', def.name);
    const options: [string, string][] =
      def.type === 'bool'
        ? [
            ['', '(inherit)'],
            ['On', 'On'],
            ['Off', 'Off'],
          ]
        : [['', '(inherit)'], ...def.enumValues.map((v): [string, string] => [v, v])];
    for (const [value, label] of options) select.append(new Option(label, value));
    select.value =
      current === null || current === undefined
        ? ''
        : def.type === 'bool'
          ? current
            ? 'On'
            : 'Off'
          : String(current);
    select.addEventListener('change', () => done(select.value, false));
    select.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') done(null, false);
    });
    queueMicrotask(() => select.focus());
    return select;
  }
  const input = el('input', 'grid-edit');
  input.type = 'text';
  input.dataset.key = 'grid-edit';
  input.setAttribute('aria-label', def.name);
  input.value = hold ?? (current === null || current === undefined ? '' : String(current));
  let finished = false;
  const finish = (text: string | null, down: boolean) => {
    if (finished) return;
    finished = true;
    done(text, down);
  };
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      finish(input.value, true);
    } else if (ev.key === 'Escape') {
      ev.preventDefault();
      finish(null, false);
    }
  });
  // A page drawn again takes the field away, which is not the person leaving it.
  input.addEventListener('blur', () => {
    if (!redraw.active && input.isConnected) finish(input.value, false);
  });
  queueMicrotask(() => {
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  });
  return input;
}
