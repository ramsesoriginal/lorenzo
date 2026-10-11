// The Stats pane: the stats an entry has, those it has of its own and those it inherits, each
// edited through the command layer (core/bench.ts). A bool is a tag.

import type { Bench } from '../core/bench';
import {
  canEditStat,
  parseDecimal,
  type StatDef,
  type StatScalar,
  type StatValue,
} from '../core/transport';
import { redraw } from './entryPane';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

/** What a stat starts as when a person adds it to an entry. */
function starting(def: StatDef): StatScalar {
  if (def.type === 'bool') return true;
  if (def.type === 'int' || def.type === 'float') return 0;
  if (def.type === 'enum') return def.enumValues[0] ?? '';
  return '';
}

function control(bench: Bench, entryId: string, def: StatDef, stat: StatValue): HTMLElement {
  const label = `${def.name}${stat.own ? '' : ' (inherited)'}`;
  const key = `stat:${entryId}:${def.id}`;
  const set = (value: StatScalar) => {
    if (!redraw.active) bench.setStat(entryId, def.id, value);
  };
  if (!canEditStat(def.type)) return el('span', 'stat-value muted', String(stat.value ?? ''));
  if (def.type === 'bool') {
    const box = el('input');
    box.type = 'checkbox';
    box.checked = stat.value === true;
    box.dataset.key = key;
    box.setAttribute('aria-label', label);
    box.addEventListener('change', () => set(box.checked));
    return box;
  }
  if (def.type === 'enum') {
    const select = el('select');
    select.dataset.key = key;
    select.setAttribute('aria-label', label);
    if (stat.value === null) select.append(new Option('(inherited)', ''));
    for (const v of def.enumValues) select.append(new Option(v, v));
    select.value = stat.value === null ? '' : String(stat.value);
    select.addEventListener('change', () => select.value && set(select.value));
    return select;
  }
  const input = el('input');
  input.type = def.type === 'int' ? 'number' : 'text';
  if (def.type === 'int') input.step = '1';
  if (def.type === 'float') input.inputMode = 'decimal';
  input.value = stat.value === null ? '' : String(stat.value);
  input.placeholder = stat.value === null ? 'inherited' : '';
  input.dataset.key = key;
  input.setAttribute('aria-label', label);
  input.addEventListener('change', () => {
    if (def.type === 'text') return set(input.value);
    const n = def.type === 'float' ? parseDecimal(input.value) : Number(input.value);
    const fits = def.type === 'float' ? n !== null : Number.isInteger(n);
    if (input.value.trim() !== '' && fits) set(n as number);
    else input.value = stat.value === null ? '' : String(stat.value);
  });
  return input;
}

export function renderStats(bench: Bench, id: string | null): HTMLElement {
  const c = el('div', 'pane pane-props');
  const item = id ? bench.view(id) : null;
  if (!id || !item) {
    c.append(el('p', 'muted', 'Choose an entry in the explorer.'));
    return c;
  }
  void bench.loadFormulas(id);
  const byId = new Map(bench.statDefs.map((d) => [d.id, d]));
  const rows = el('ul', 'stats');
  if (!item.stats.length) rows.append(el('li', 'muted', 'No stats.'));
  for (const stat of [...item.stats].sort((a, b) => a.name.localeCompare(b.name))) {
    const def = byId.get(stat.statId);
    if (!def) continue;
    const li = el('li', stat.own ? 'stat own' : 'stat inherited');
    li.dataset.stat = def.id;
    li.append(el('span', 'stat-name', def.name));
    const worked = bench.formulaFor(id, def.id);
    if (worked) {
      const mark = el('span', 'stat-formula', 'ƒ');
      mark.title = 'Worked out by a formula (see the Formulas pane)';
      li.append(mark);
    }
    li.append(control(bench, id, def, stat));
    if (stat.own && canEditStat(def.type)) {
      const clear = el('button', 'x', '×');
      clear.type = 'button';
      clear.title = `Remove ${def.name} from this entry (it inherits again)`;
      clear.setAttribute('aria-label', `Remove ${def.name}`);
      clear.addEventListener('click', () => bench.setStat(id, def.id, null));
      li.append(clear);
    }
    rows.append(li);
  }
  c.append(rows);

  const have = new Set(item.stats.map((s) => s.statId));
  const add = el('select', 'add-stat');
  add.setAttribute('aria-label', 'Add a stat');
  add.append(new Option('Add a stat…', ''));
  for (const d of bench.statDefs)
    if (!have.has(d.id) && canEditStat(d.type)) add.append(new Option(d.name, d.id));
  add.addEventListener('change', () => {
    const def = byId.get(add.value);
    if (def) bench.setStat(id, def.id, starting(def));
  });
  c.append(add);
  return c;
}
