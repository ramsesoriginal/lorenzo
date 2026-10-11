// The Pack pane (ADR 0256): the contents list in the description of the selected entry, edited as
// rows. Every change writes the whole description back through the command layer, so it is undone
// and synced like any text change; the prose around the list is kept as it was.

import type { Bench } from '../core/bench';
import {
  indent,
  move,
  outdent,
  type Pack,
  parsePack,
  type Row,
  remove,
  total,
  writePack,
} from './packModel';

export interface PackUi {
  asText: boolean;
  /** The weight of each link name asked for; null when it has none. */
  weights: Map<string, number | null>;
  /** The row to put the cursor on after the next drawing (the one that was moved). */
  focus: number | null;
}
export const newPackUi = (): PackUi => ({ asText: false, weights: new Map(), focus: null });

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const button = (text: string, label: string, run: () => void) => {
  const b = el('button', 'btn pack-btn', text);
  b.type = 'button';
  b.setAttribute('aria-label', label);
  b.title = label;
  b.addEventListener('click', (e) => {
    e.stopPropagation();
    run();
  });
  return b;
};

/** Reads the weight of the entries the rows link to (once each). */
async function loadWeights(bench: Bench, ui: PackUi, rows: Row[]): Promise<boolean> {
  const wanted = [
    ...new Set(rows.flatMap((r) => (r.slug && !ui.weights.has(r.slug) ? [r.slug] : []))),
  ];
  if (!wanted.length) return false;
  for (const s of wanted) ui.weights.set(s, null);
  try {
    const found = await bench.transport.resolveSlugs(wanted);
    await Promise.all(found.map((f) => bench.open(f.id, true)));
    for (const f of found) {
      const w = bench.view(f.id)?.stats.find((s) => {
        return bench.statDefs.find((d) => d.id === s.statId)?.name.toLowerCase() === 'weight';
      })?.value;
      ui.weights.set(f.slug, typeof w === 'number' ? w : null);
    }
  } catch {
    /* no weights: the total says how many it knows */
  }
  return true;
}

export function renderPack(
  bench: Bench,
  id: string | null,
  ui: PackUi,
  hooks: { redraw: () => void; go: (id: string) => void },
): HTMLElement {
  const c = el('div', 'pane pane-pack');
  const item = id ? bench.view(id) : null;
  if (!id || !item) {
    c.append(el('p', 'muted', 'Choose an entry in the explorer.'));
    return c;
  }
  const text = item.description?.text ?? '';
  const pack: Pack = parsePack(text);
  const write = (rows: Row[], at?: number) => {
    bench.setDescription(id, writePack({ ...pack, rows }));
    if (at !== undefined) ui.focus = at;
  };

  void loadWeights(bench, ui, pack.rows).then((asked) => asked && hooks.redraw());

  const entries = bench
    .listing()
    .filter((e) => e.id !== id)
    .sort((a, b) => a.name.localeCompare(b.name));
  const entrySelect = (label: string, pick: (entryId: string) => void) => {
    const s = el('select');
    s.setAttribute('aria-label', label);
    s.append(new Option(`${label}…`, ''));
    for (const e of entries) s.append(new Option(e.name, e.id));
    s.addEventListener('change', () => s.value && pick(s.value));
    return s;
  };
  /** The row for an entry: linked if it has a link name, plain text if not. */
  const rowFor = async (entryId: string): Promise<{ label: string; slug: string | null }> => {
    await bench.open(entryId, true);
    const e = bench.view(entryId);
    return { label: e?.name ?? entryId, slug: e?.slug ?? null };
  };

  if (!pack.rows.length) {
    c.append(el('p', 'muted', 'This description has no list of contents.'));
  } else if (pack.mixed) {
    c.append(
      el(
        'p',
        'bad',
        'Other text sits between the lines of the list, so it is shown but not edited here. Edit it in the description.',
      ),
    );
  }

  if (ui.asText) {
    const area = el('textarea', 'pack-text');
    area.setAttribute('aria-label', 'Pack as text');
    area.value = text;
    area.rows = 10;
    area.addEventListener('change', () => bench.setDescription(id, area.value));
    c.append(area);
  } else {
    const list = el('ul', 'pack-rows');
    pack.rows.forEach((r, i) => {
      const li = el('li', `pack-row depth-${r.depth}`);
      li.dataset.row = String(i);
      li.dataset.key = `pack-row:${id}:${i}`;
      li.tabIndex = 0;
      li.setAttribute('aria-label', `${r.count} x ${r.label}`);
      li.style.paddingLeft = `${r.depth * 20}px`;
      const edit = !pack.mixed;
      li.addEventListener('keydown', (e) => {
        if (!e.altKey || !edit || e.target !== li) return;
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
          const m = move(pack.rows, i, e.key === 'ArrowUp' ? -1 : 1);
          if (m.at !== i) write(m.rows, m.at);
        } else if (e.key === 'ArrowRight') write(indent(pack.rows, i), i);
        else if (e.key === 'ArrowLeft') write(outdent(pack.rows, i), i);
        else return;
        e.preventDefault();
      });

      const count = el('input');
      count.type = 'number';
      count.min = '1';
      count.step = '1';
      count.value = String(r.count);
      count.disabled = !edit;
      count.setAttribute('aria-label', `Count of ${r.label}`);
      count.addEventListener('change', () => {
        const n = Math.floor(Number(count.value));
        if (n >= 1) write(pack.rows.map((x, j) => (j === i ? { ...x, count: n } : x)));
        else count.value = String(r.count);
      });
      li.append(count, el('span', 'muted', '×'));

      if (r.slug) {
        const open = el('button', 'row pack-name', r.label);
        open.type = 'button';
        open.title = `Open ${r.label}`;
        open.addEventListener('click', async () => {
          const found = await bench.transport.resolveSlugs([r.slug as string]).catch(() => []);
          if (found[0]) hooks.go(found[0].id);
        });
        li.append(open);
      } else {
        li.append(el('span', 'pack-name plain', r.label), el('span', 'muted', '(plain text)'));
        if (edit)
          li.append(
            entrySelect('Make this an item', async (entryId) => {
              const made = await rowFor(entryId);
              write(pack.rows.map((x, j) => (j === i ? { ...x, ...made } : x)));
            }),
          );
      }
      const w = r.slug ? ui.weights.get(r.slug) : null;
      if (typeof w === 'number') li.append(el('span', 'muted', `${w * r.count} kg`));

      if (edit) {
        const up = move(pack.rows, i, -1);
        const down = move(pack.rows, i, 1);
        const b1 = button('↑', 'Move up', () => write(up.rows, up.at));
        b1.disabled = up.at === i;
        const b2 = button('↓', 'Move down', () => write(down.rows, down.at));
        b2.disabled = down.at === i;
        const b3 = button('←', 'Out of its container', () => write(outdent(pack.rows, i), i));
        b3.disabled = r.depth === 0;
        const b4 = button('→', 'Into the row above', () => write(indent(pack.rows, i), i));
        b4.disabled = indent(pack.rows, i).every((x, j) => x.depth === (pack.rows[j] as Row).depth);
        li.append(
          b1,
          b2,
          b3,
          b4,
          button('×', `Remove ${r.label}`, () => write(remove(pack.rows, i))),
        );
      }
      list.append(li);
    });
    c.append(list);

    if (!pack.mixed) {
      c.append(
        entrySelect('Add an item', async (entryId) => {
          const made = await rowFor(entryId);
          write([...pack.rows, { depth: 0, count: 1, ...made }]);
        }),
      );
      const plain = el('form', 'pack-add');
      const input = el('input');
      input.type = 'text';
      input.placeholder = 'Something that is not an item';
      input.setAttribute('aria-label', 'Plain text row');
      const add = el('button', 'btn', 'Add text');
      add.type = 'submit';
      plain.append(input, add);
      plain.addEventListener('submit', (e) => {
        e.preventDefault();
        const label = input.value.trim();
        if (label) write([...pack.rows, { depth: 0, count: 1, label, slug: null }]);
      });
      c.append(plain);
    }
  }

  if (pack.rows.length) {
    const t = total(pack.rows, (s) => ui.weights.get(s));
    c.append(
      el(
        'p',
        'pack-total muted',
        `Weighs ${t.weight} kg together (${t.known} of ${t.listed} rows have a weight). Alt+arrows move the row you are on.`,
      ),
    );
  }
  const toggle = el('button', 'btn', ui.asText ? 'Show as rows' : 'Show as text');
  toggle.type = 'button';
  toggle.addEventListener('click', () => {
    ui.asText = !ui.asText;
    hooks.redraw();
  });
  c.append(toggle);
  const row = ui.focus;
  ui.focus = null;
  if (row !== null)
    queueMicrotask(() => c.querySelector<HTMLElement>(`[data-row="${row}"]`)?.focus());
  return c;
}
