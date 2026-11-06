import { LorenzoApiError } from '@lorenzo/api-client';
import {
  actions,
  button,
  card,
  claim,
  el,
  empty,
  errorNotice,
  link,
  loading,
  message,
  pageHead,
  say,
  select,
  statusLine,
} from './dom';
import {
  batches,
  buildCells,
  type Cell,
  cellKey,
  type Edit,
  isConflict,
  moveFocus,
  type Planned,
  parseInput,
  planOperations,
  visibleRange,
  windows,
} from './matrix';
import {
  limitsOf,
  listStats,
  readStanding,
  readWindow,
  type StatDef,
  typeIsDirected,
  versionOf,
  writeBatch,
} from './matrix-api';
import { canManage } from './names';
import { entryPicker } from './pickers';
import { start } from './sign-in';
import { readGraph, readWeb } from './web-api';

const ROW_H = 36;
const COL_W = 112;
const HEAD_W = 168;
const HEAD_H = 44;

interface Member {
  id: string;
  name: string;
}

/** The matrix of one web: its members on both sides, a standing (or presence) in every cell. */
export async function mountMatrix() {
  const host = document.querySelector<HTMLElement>('#social-matrix');
  if (!host || !claim(host)) return;
  const params = new URLSearchParams(location.search);
  const tenant = params.get('tenant');
  const id = params.get('id');
  if (!tenant || !id) {
    location.replace('/');
    return;
  }
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening the matrix…'));
    const [{ web }, graph, manage, stats] = await Promise.all([
      readWeb(tenant, id),
      readGraph(tenant, id),
      canManage(tenant),
      listStats(tenant),
    ]);
    const members: Member[] = graph.members.map((m) => ({ id: m.entry.id, name: m.entry.name }));
    const view = el('div', '', 'stack view');
    view.append(
      pageHead(`${web.name}: matrix`, {
        crumbs: [
          link('Webs', `/webs/?${new URLSearchParams({ tenant })}`),
          link(web.name, `/web/?${new URLSearchParams({ tenant, id })}`),
        ],
        lede: 'One ordered pair of its entries in every cell: the row to the column.',
      }),
    );
    if (members.length < 2) {
      view.append(empty('A matrix needs at least two entries: add them to the web first.'));
      host.replaceChildren(view);
      return;
    }
    view.append(await matrix(tenant, members, stats, manage, web.standing_stat_id ?? null));
    host.replaceChildren(view);
  } catch (error) {
    host.replaceChildren(errorNotice(error));
  }
}

async function matrix(
  tenant: string,
  members: Member[],
  stats: StatDef[],
  manage: boolean,
  savedStanding: string | null,
) {
  const root = el('div', '', 'stack');
  const names = new Map(members.map((m) => [m.id, m.name]));
  const numbers = stats.filter((s) => s.value_type === 'int' || s.value_type === 'float');
  let mode: 'value' | 'presence' = numbers.length ? 'value' : 'presence';
  let stat: StatDef | undefined = numbers.find((s) => s.id === savedStanding) ?? numbers[0];
  let type: { id: string; name: string } | null = null;
  let order: 'name' | 'standing' = 'name';
  let rowWindow = 0;
  let colWindow = 0;
  let cells = new Map<string, Cell>();
  const edits = new Map<string, Edit>();
  const failures = new Map<string, string>();
  const undo: { key: string; before: Edit | undefined }[] = [];
  const redo: { key: string; after: Edit | undefined }[] = [];
  let focus = { row: 0, col: 0 };
  let confirmedDelete = false;
  let ordered = [...members];

  const controls = card();
  const status = statusLine();
  const gridHost = el('div', '', 'matrix');
  const summary = el('p', '', 'status-text');
  summary.setAttribute('role', 'status');

  const modeSelect = select(
    'Show',
    [
      ...(numbers.length ? ([['value', 'A standing in every cell']] as [string, string][]) : []),
      ['presence', 'Whether a relationship is there'],
    ],
    mode,
  );
  const statSelect = select(
    'Standing',
    numbers.map((s) => [s.id, s.name]),
    stat?.id ?? '',
  );
  const orderSelect = select(
    'Order',
    [
      ['name', 'By name'],
      ['standing', 'By standing, highest first'],
    ],
    order,
  );
  const typePicker = entryPicker(tenant, 'Type of relationship (to show, and for new ones)');
  const clearType = button('No type', () => {
    type = null;
    void load();
  });
  const useType = button('Use this type', () => {
    const picked = typePicker.value();
    type = picked ? { id: picked, name: typePicker.name() } : null;
    void load();
  });
  controls.body.append(
    modeSelect.label,
    ...(numbers.length ? [statSelect.label, orderSelect.label] : []),
    typePicker.label,
    actions(useType, clearType),
  );
  modeSelect.input.addEventListener('change', () => {
    mode = modeSelect.input.value as typeof mode;
    void load();
  });
  statSelect.input.addEventListener('change', () => {
    stat = numbers.find((s) => s.id === statSelect.input.value);
    edits.clear();
    void load();
  });
  orderSelect.input.addEventListener('change', () => {
    order = orderSelect.input.value as typeof order;
    sortMembers();
    render();
  });

  const rowRanges = windows(members.length);
  const windowSelect = (label: string, set: (n: number) => void) => {
    const options = rowRanges.map(([from, to], i) => [
      String(i),
      `${label} ${from + 1} to ${to} of ${members.length}`,
    ]) as [string, string][];
    const picker = select(label, options, '0');
    picker.input.addEventListener('change', () => {
      set(Number(picker.input.value));
      void load();
    });
    return picker.label;
  };
  if (rowRanges.length > 1) {
    controls.body.append(
      windowSelect('Rows', (n) => {
        rowWindow = n;
      }),
      windowSelect('Columns', (n) => {
        colWindow = n;
      }),
    );
  }

  const sortMembers = () => {
    ordered = [...members].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    if (order === 'standing' && mode === 'value') {
      const total = (m: Member) =>
        [...cells]
          .filter(([k]) => k.startsWith(`${m.id}|`))
          .reduce(
            (sum, [, c]) => sum + (typeof c.value?.value === 'number' ? c.value.value : 0),
            0,
          );
      ordered = [...ordered].sort((a, b) => total(b) - total(a));
    }
  };
  const rowsOf = () => ordered.slice(...(rowRanges[rowWindow] ?? [0, 0]));
  const colsOf = () => ordered.slice(...(rowRanges[colWindow] ?? [0, 0]));

  /** What a cell shows, in words and marks: a value, a dash for none, a conflict, a pending edit. */
  const cellText = (row: string, col: string) => {
    const k = cellKey(row, col);
    const pending = edits.get(k);
    const cell = cells.get(k);
    if (pending) return pending.value === null ? '' : String(pending.value);
    if (isConflict(cell)) return `${cell?.ties.length} here`;
    if (mode === 'presence') return cell ? 'Yes' : '';
    if (!cell) return '';
    return cell.value ? String(cell.value.value) : '–';
  };
  const cellName = (row: string, col: string) => {
    const k = cellKey(row, col);
    const cell = cells.get(k);
    const bits = [`${names.get(row)} to ${names.get(col)}`];
    const pending = edits.get(k);
    if (pending) bits.push(pending.value === null ? 'cleared' : String(pending.value));
    else if (isConflict(cell)) bits.push(`${cell?.ties.length} relationships, a conflict`);
    else if (cell)
      bits.push(mode === 'presence' ? 'a relationship' : cellText(row, col) || 'no value');
    else bits.push('none');
    if (cell?.value && !cell.value.own && !edits.has(k)) bits.push('inherited');
    if (edits.has(k)) bits.push('not saved');
    if (failures.has(k)) bits.push(`refused: ${failures.get(k)}`);
    return bits.join(', ');
  };

  const scroller = el('div', '', 'matrix-scroll');
  const content = el('div', '', 'matrix-content');
  const headRow = el('div', '', 'matrix-row matrix-head');
  headRow.setAttribute('role', 'row');
  const body = el('div', '', 'matrix-body');
  content.append(headRow, body);
  scroller.append(content);
  gridHost.setAttribute('role', 'grid');
  gridHost.setAttribute('aria-label', 'Relationship matrix');
  gridHost.append(scroller);

  const focusCell = () => {
    const r = rowsOf()[focus.row];
    const c = colsOf()[focus.col];
    if (!r || !c) return;
    const node = body.querySelector<HTMLElement>(
      `[data-cell="${CSS.escape(cellKey(r.id, c.id))}"]`,
    );
    node?.focus();
  };

  const editCell = (node: HTMLElement, row: string, col: string, seed?: string) => {
    if (!manage || mode !== 'value' || !stat) {
      say(
        status,
        mode === 'value' ? 'You may read these, not change them.' : 'Switch to a standing to edit.',
      );
      return;
    }
    const cell = cells.get(cellKey(row, col));
    if (isConflict(cell)) {
      say(status, 'Two relationships fill this cell: open them from the list to choose.', true);
      return;
    }
    const input = el('input', '', 'text-input matrix-input');
    input.setAttribute('aria-label', `${names.get(row)} to ${names.get(col)}: ${stat.name}`);
    input.value =
      seed ??
      edits.get(cellKey(row, col))?.value?.toString() ??
      (cell?.value ? String(cell.value.value) : '');
    node.replaceChildren(input);
    input.focus();
    if (seed === undefined) input.select();
    else input.setSelectionRange(input.value.length, input.value.length);
    const finish = (commit: boolean, step: number) => {
      if (commit) {
        const parsed = parseInput(input.value, limitsOf(stat as StatDef));
        if (!parsed.ok) {
          say(status, parsed.reason, true);
          input.focus();
          return;
        }
        const k = cellKey(row, col);
        const before = edits.get(k);
        const unchanged =
          parsed.value === (cell?.value ? Number(cell.value.value) : null) && !before;
        if (!unchanged) {
          undo.push({ key: k, before });
          redo.length = 0;
          edits.set(k, { row, col, before: cell, value: parsed.value });
          failures.delete(k);
        }
        say(status, '');
      }
      render();
      focus = { row: Math.min(rowsOf().length - 1, focus.row + step), col: focus.col };
      render();
      focusCell();
    };
    input.addEventListener('keydown', (event) => {
      event.stopPropagation();
      if (event.key === 'Enter') {
        event.preventDefault();
        finish(true, 1);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        finish(false, 0);
      } else if (event.key === 'Tab') {
        finish(true, 0);
      }
    });
    input.addEventListener('blur', () => {
      if (node.contains(input)) finish(true, 0);
    });
  };

  const render = () => {
    const rows = rowsOf();
    const cols = colsOf();
    const [r0, r1] = visibleRange(
      scroller.scrollTop,
      scroller.clientHeight || 400,
      ROW_H,
      rows.length,
    );
    const [c0, c1] = visibleRange(
      scroller.scrollLeft,
      scroller.clientWidth || 800,
      COL_W,
      cols.length,
    );
    content.style.width = `${HEAD_W + cols.length * COL_W}px`;
    body.style.height = `${rows.length * ROW_H}px`;
    gridHost.setAttribute('aria-rowcount', String(rows.length + 1));
    gridHost.setAttribute('aria-colcount', String(cols.length + 1));
    headRow.style.height = `${HEAD_H}px`;
    const corner = el('div', '', 'matrix-cell matrix-corner');
    corner.setAttribute('role', 'columnheader');
    corner.append(el('span', 'From ↓  To →', 'status-text'));
    headRow.replaceChildren(corner);
    for (let c = c0; c < c1; c += 1) {
      const m = cols[c] as Member;
      const h = el('div', m.name, 'matrix-cell matrix-colhead');
      h.setAttribute('role', 'columnheader');
      h.setAttribute('aria-colindex', String(c + 2));
      h.style.left = `${HEAD_W + c * COL_W}px`;
      headRow.append(h);
    }
    const out: HTMLElement[] = [];
    for (let r = r0; r < r1; r += 1) {
      const rowMember = rows[r] as Member;
      const row = el('div', '', 'matrix-row');
      row.setAttribute('role', 'row');
      row.setAttribute('aria-rowindex', String(r + 2));
      row.style.top = `${r * ROW_H}px`;
      row.style.height = `${ROW_H}px`;
      const head = el('div', rowMember.name, 'matrix-cell matrix-rowhead');
      head.setAttribute('role', 'rowheader');
      row.append(head);
      for (let c = c0; c < c1; c += 1) {
        const colMember = cols[c] as Member;
        const k = cellKey(rowMember.id, colMember.id);
        const node = el('div', '', 'matrix-cell matrix-data');
        node.setAttribute('role', 'gridcell');
        node.setAttribute('aria-colindex', String(c + 2));
        node.dataset.cell = k;
        node.style.left = `${HEAD_W + c * COL_W}px`;
        node.tabIndex = r === focus.row && c === focus.col ? 0 : -1;
        node.setAttribute('aria-label', cellName(rowMember.id, colMember.id));
        node.textContent = cellText(rowMember.id, colMember.id);
        const cell = cells.get(k);
        if (rowMember.id === colMember.id) node.classList.add('is-self');
        if (isConflict(cell)) node.classList.add('is-conflict');
        if (cell?.value && !cell.value.own && !edits.has(k)) node.classList.add('is-inherited');
        if (edits.has(k)) node.classList.add('is-pending');
        if (failures.has(k)) node.classList.add('is-failed');
        node.addEventListener('focus', () => {
          focus = { row: r, col: c };
          summarize();
        });
        node.addEventListener('dblclick', () => editCell(node, rowMember.id, colMember.id));
        node.addEventListener('click', () => {
          focus = { row: r, col: c };
          node.focus();
        });
        node.addEventListener('keydown', (event) => {
          if (event.ctrlKey || event.metaKey) {
            if (event.key === 'z') {
              event.preventDefault();
              undoOne();
            } else if (event.key === 'y') {
              event.preventDefault();
              redoOne();
            }
            return;
          }
          const to = moveFocus(focus, event.key, {
            rows: rows.length,
            cols: cols.length,
            page: Math.max(1, Math.floor((scroller.clientHeight || 400) / ROW_H) - 1),
          });
          if (to) {
            event.preventDefault();
            focus = to;
            scroller.scrollTop = Math.min(
              Math.max(
                scroller.scrollTop,
                to.row * ROW_H - (scroller.clientHeight - HEAD_H - ROW_H),
              ),
              to.row * ROW_H,
            );
            scroller.scrollLeft = Math.min(
              Math.max(
                scroller.scrollLeft,
                to.col * COL_W - (scroller.clientWidth - HEAD_W - COL_W),
              ),
              to.col * COL_W,
            );
            render();
            focusCell();
          } else if (event.key === 'Enter' || event.key === 'F2') {
            event.preventDefault();
            editCell(node, rowMember.id, colMember.id);
          } else if (event.key === 'Delete' || event.key === 'Backspace') {
            event.preventDefault();
            clearCell(rowMember.id, colMember.id);
          } else if (event.key.length === 1 && /[-0-9]/.test(event.key)) {
            event.preventDefault();
            editCell(node, rowMember.id, colMember.id, event.key);
          }
        });
        row.append(node);
      }
      out.push(row);
    }
    body.replaceChildren(...out);
    saveButton.textContent = `Save changes (${edits.size})`;
    saveButton.disabled = edits.size === 0;
  };

  const clearCell = (row: string, col: string) => {
    if (!manage || mode !== 'value') return;
    const k = cellKey(row, col);
    const cell = cells.get(k);
    if (!cell && !edits.has(k)) return;
    if (!confirmedDelete && !confirm('Clear this standing? The relationship stays.')) return;
    confirmedDelete = true;
    undo.push({ key: k, before: edits.get(k) });
    redo.length = 0;
    edits.set(k, { row, col, before: cell, value: null });
    render();
    focusCell();
  };
  const undoOne = () => {
    const last = undo.pop();
    if (!last) return;
    redo.push({ key: last.key, after: edits.get(last.key) });
    if (last.before) edits.set(last.key, last.before);
    else edits.delete(last.key);
    render();
    focusCell();
  };
  const redoOne = () => {
    const last = redo.pop();
    if (!last) return;
    undo.push({ key: last.key, before: edits.get(last.key) });
    if (last.after) edits.set(last.key, last.after);
    else edits.delete(last.key);
    render();
    focusCell();
  };

  /** A total of a row, worked out here from what the reader sees, and worded so. */
  const summarize = () => {
    const rowMember = rowsOf()[focus.row];
    if (!rowMember || mode !== 'value') {
      summary.textContent = '';
      return;
    }
    let sum = 0;
    let n = 0;
    for (const col of colsOf()) {
      const v = cells.get(cellKey(rowMember.id, col.id))?.value?.value;
      if (typeof v === 'number') {
        sum += v;
        n += 1;
      }
    }
    summary.textContent = `${rowMember.name}: ${n} ${n === 1 ? 'value' : 'values'} you can see, adding up to ${sum}. Someone who sees more may see a different total.`;
  };

  const load = async () => {
    say(status, 'Reading the matrix…');
    try {
      const rows = rowsOf();
      const cols = colsOf();
      const ties = await readWindow(
        tenant,
        rows.map((m) => m.id),
        cols.map((m) => m.id),
        type?.id ?? null,
      );
      const values = mode === 'value' && stat ? await readStanding(tenant, stat.id) : new Map();
      cells = buildCells(
        ties,
        values,
        new Set(rows.map((m) => m.id)),
        new Set(cols.map((m) => m.id)),
      );
      sortMembers();
      render();
      summarize();
      say(
        status,
        ties.length === 0
          ? 'No relationship ties these entries yet.'
          : `${ties.length} ${ties.length === 1 ? 'relationship' : 'relationships'} between these entries.`,
      );
    } catch (error) {
      say(status, message(error), true);
    }
  };

  const save = async () => {
    if (!stat || edits.size === 0) return;
    say(status, 'Saving…');
    const wanted = [...edits.values()];
    const existing = new Set(
      wanted.flatMap((e) => (e.before?.ties.length === 1 ? [e.before.ties[0]?.id as string] : [])),
    );
    const versions = new Map<string, string>();
    await Promise.all(
      [...existing].map(async (tie) => versions.set(tie, await versionOf(tenant, tie))),
    );
    const directed = type ? await typeIsDirected(tenant, type.id) : false;
    const { planned, skipped } = planOperations({
      edits: wanted,
      stat: stat.id,
      type,
      directed,
      nameOf: (entry) => names.get(entry) ?? '',
      versions,
    });
    failures.clear();
    for (const k of skipped) failures.set(k, 'two relationships fill this cell');
    let written = 0;
    let stale = false;
    for (const batch of batches<Planned>(planned)) {
      const result = await writeBatch(
        tenant,
        batch.map((p) => p.operation),
      );
      if (result.ok) {
        for (const p of batch) for (const k of p.cells) edits.delete(k);
        written += batch.length;
        continue;
      }
      const { failure } = result;
      if (failure.status === 412) stale = true;
      const culprit = failure.operation === null ? null : batch[failure.operation];
      for (const p of culprit ? [culprit] : batch) {
        for (const k of p.cells) failures.set(k, failure.detail);
      }
    }
    await load();
    const left = failures.size;
    say(
      status,
      stale
        ? 'Someone changed one of these meanwhile: your draft is kept. Check the marked cells.'
        : left
          ? `Saved ${written}; ${left} ${left === 1 ? 'cell was' : 'cells were'} refused and keep their reason.`
          : `Saved ${written} ${written === 1 ? 'change' : 'changes'}.`,
      left > 0,
    );
  };
  const saveButton = button('Save changes (0)', () =>
    save().catch((error) => {
      if (error instanceof LorenzoApiError) say(status, error.message, true);
      else throw error;
    }),
  );
  saveButton.disabled = true;
  const bar = actions(
    ...(manage
      ? [
          saveButton,
          button('Undo', undoOne),
          button('Redo', redoOne),
          button('Discard changes', () => {
            edits.clear();
            failures.clear();
            render();
          }),
        ]
      : []),
  );
  scroller.addEventListener('scroll', () => render());
  if (matchMedia('(max-width: 720px)').matches) {
    root.append(controls.root, phoneList());
  } else {
    root.append(controls.root, gridHost, summary, bar, status);
  }
  await load();
  return root;

  /** On a phone the matrix does not fit: one entry's standings as a list, with the same save. */
  function phoneList() {
    const section = el('section', '', 'stack');
    section.append(
      el(
        'p',
        'The matrix is for a tablet or a desktop. Here is one entry’s standings as a list.',
        'status-text',
      ),
    );
    const who = select(
      'Entry',
      members.map((m) => [m.id, m.name]),
      members[0]?.id ?? '',
    );
    const list = el('ul', '', 'list');
    list.setAttribute('aria-label', 'Standings of one entry');
    const draw = () => {
      const from = who.input.value;
      list.replaceChildren(
        ...members
          .filter((m) => m.id !== from)
          .map((m) => {
            const row = el('li');
            const k = cellKey(from, m.id);
            const cell = cells.get(k);
            row.append(el('span', `${names.get(from)} to ${m.name}`, 'grow'));
            if (manage && mode === 'value' && stat) {
              const input = el('input', '', 'text-input matrix-input');
              input.inputMode = 'numeric';
              input.setAttribute('aria-label', `${names.get(from)} to ${m.name}: ${stat.name}`);
              input.value =
                edits.get(k)?.value?.toString() ?? (cell?.value ? String(cell.value.value) : '');
              input.addEventListener('change', () => {
                const parsed = parseInput(input.value, limitsOf(stat as StatDef));
                if (!parsed.ok) {
                  say(status, parsed.reason, true);
                  return;
                }
                edits.set(k, { row: from, col: m.id, before: cell, value: parsed.value });
                saveButton.textContent = `Save changes (${edits.size})`;
                saveButton.disabled = edits.size === 0;
              });
              row.append(input);
            } else {
              row.append(el('span', cellText(from, m.id) || 'none', 'chip'));
            }
            return row;
          }),
      );
    };
    who.input.addEventListener('change', draw);
    section.append(who.label, list, bar, status);
    const original = load;
    void original().then(draw);
    return section;
  }
}
