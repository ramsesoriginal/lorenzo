// The Formula pane: the stats of an entry that are worked out rather than typed, and an editor for
// the formula of one (ADR 0253). A formula is held by an entry and reaches what inherits from it;
// writing one is a direct, online write, not a command (ADR 0253 says why and what B4 changes).

import type { Bench } from '../core/bench';
import { findFormula } from '../core/formulaStore';
import {
  COMPARATORS,
  type Comparator,
  describe,
  type Formula,
  isDecimal,
  KIND_LABEL,
  KINDS,
  problems,
  ROUNDS,
  same,
  starting,
} from '../core/formulas';
import { RefusedError, type StatDef } from '../core/transport';

interface Draft {
  entryId: string;
  statId: string;
  formula: Formula;
  /** What was held when the draft began; null for a new formula. */
  base: Formula | null;
  /** The `If-Match` of the formula held on this entry itself, if there is one. */
  version: string | null;
}

export interface FormulaUi {
  draft: Draft | null;
  note: string | null;
}
export const newFormulaUi = (): FormulaUi => ({ draft: null, note: null });

interface Hooks {
  redraw: () => void;
  go: (id: string) => void;
}

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const NUMERIC = (d: StatDef) => d.type === 'int' || d.type === 'float';

function ancestorsOf(bench: Bench, id: string): string[] {
  const parents = new Map(bench.listing().map((e) => [e.id, e.parentIds]));
  const out: string[] = [];
  const walk = (x: string) => {
    for (const p of parents.get(x) ?? [])
      if (!out.includes(p)) {
        out.push(p);
        walk(p);
      }
  };
  walk(id);
  return out;
}

export function renderFormulas(
  bench: Bench,
  id: string | null,
  ui: FormulaUi,
  hooks: Hooks,
): HTMLElement {
  const c = el('div', 'pane pane-formula');
  const item = id ? bench.view(id) : null;
  if (!id || !item) {
    c.append(el('p', 'muted', 'Choose an entry in the explorer.'));
    return c;
  }
  const chain = ancestorsOf(bench, id);
  void bench.formulas.load([id, ...chain]);
  const parentsOf = (x: string) => bench.listing().find((e) => e.id === x)?.parentIds ?? [];
  const nameOf = (statId: string) => bench.statDefs.find((d) => d.id === statId)?.name ?? '?';
  const entryName = (x: string) => bench.listing().find((e) => e.id === x)?.name ?? x;
  const applying = bench.statDefs.flatMap((d) => {
    const h = findFormula((e) => bench.formulas.held(e), parentsOf, id, d.id);
    return h ? [{ def: d, held: h }] : [];
  });

  if (ui.note) c.append(el('p', 'formula-note', ui.note));
  const list = el('ul', 'formulas');
  if (!applying.length) list.append(el('li', 'muted', 'No stat of this entry is worked out.'));
  for (const { def, held } of applying) {
    const own = held.entryId === id;
    const li = el('li', own ? 'formula own' : 'formula inherited');
    li.dataset.formula = def.id;
    li.append(el('span', 'stat-name', `ƒ ${def.name}`));
    li.append(el('span', 'formula-text', describe(held.formula, nameOf)));
    if (!own) {
      const from = el('button', 'btn link', `from ${entryName(held.entryId)}`);
      from.type = 'button';
      from.title = 'Go to the entry that holds it';
      from.addEventListener('click', () => hooks.go(held.entryId));
      li.append(from);
    }
    const edit = el('button', 'btn', own ? 'Edit' : 'Change here');
    edit.type = 'button';
    edit.setAttribute('aria-label', `${own ? 'Edit' : 'Change here'} ${def.name}`);
    edit.addEventListener('click', () => {
      ui.note = null;
      ui.draft = {
        entryId: id,
        statId: def.id,
        formula: structuredClone(held.formula),
        base: own ? held.formula : null,
        version: own ? held.version : null,
      };
      hooks.redraw();
    });
    li.append(edit);
    list.append(li);
  }
  c.append(list);

  const add = el('select', 'add-formula');
  add.setAttribute('aria-label', 'Work out a stat');
  add.append(new Option('Work out a stat…', ''));
  for (const d of bench.statDefs)
    if (!applying.some((a) => a.def.id === d.id)) add.append(new Option(d.name, d.id));
  add.addEventListener('change', () => {
    if (!add.value) return;
    ui.note = null;
    ui.draft = {
      entryId: id,
      statId: add.value,
      formula: starting('sum', bench.statDefs, add.value),
      base: null,
      version: null,
    };
    hooks.redraw();
  });
  c.append(add);

  if (ui.draft && ui.draft.entryId === id) c.append(editor(bench, ui, ui.draft, hooks));
  else if (ui.draft) ui.draft = null;
  return c;
}

function editor(bench: Bench, ui: FormulaUi, draft: Draft, hooks: Hooks): HTMLElement {
  const defs = bench.statDefs;
  const target = defs.find((d) => d.id === draft.statId);
  const box = el('section', 'formula-editor');
  box.setAttribute('aria-label', `Formula for ${target?.name ?? 'a stat'}`);
  box.append(el('h3', undefined, `${target?.name ?? 'Stat'} is worked out as`));

  const preview = el('div', 'formula-preview');
  preview.setAttribute('aria-live', 'polite');
  const issues = el('ul', 'formula-problems');
  const save = el('button', 'btn primary', 'Save');
  save.type = 'button';
  let token = 0;
  const touch = () => {
    const f = draft.formula;
    const found = problems(f, defs, draft.statId);
    issues.replaceChildren(...found.map((m) => el('li', 'bad', m)));
    const unchanged = draft.base !== null && same(draft.base, f);
    save.disabled = found.length > 0 || unchanged;
    const mine = ++token;
    if (found.length) {
      preview.textContent = '';
      return;
    }
    preview.textContent = 'Working it out…';
    bench.transport
      .previewFormula(draft.entryId, draft.statId, f)
      .then((p) => {
        if (mine !== token) return;
        const value = p.value === null ? 'nothing' : String(p.value);
        const read = p.inputs.map((i) => `${i.name} ${i.value ?? '—'}`).join(', ');
        preview.textContent = `This entry would have ${value}${read ? ` (reads ${read})` : ''}.`;
      })
      .catch((e) => {
        if (mine === token)
          preview.textContent = e instanceof Error ? e.message : 'Could not try it.';
      });
  };

  const statSelect = (label: string, value: string, set: (v: string) => void) => {
    const s = el('select');
    s.setAttribute('aria-label', label);
    s.append(new Option('Choose a stat…', ''));
    for (const d of defs)
      if (NUMERIC(d) && d.id !== draft.statId) s.append(new Option(d.name, d.id));
    s.value = value;
    s.addEventListener('change', () => {
      set(s.value);
      touch();
    });
    return s;
  };
  const numberInput = (label: string, value: string, set: (v: string) => void) => {
    const i = el('input');
    i.type = 'text';
    i.inputMode = 'decimal';
    i.size = 6;
    i.value = value;
    i.setAttribute('aria-label', label);
    i.dataset.key = `formula:${label}`;
    i.addEventListener('input', () => {
      set(i.value);
      i.classList.toggle('invalid', !isDecimal(i.value));
      touch();
    });
    return i;
  };
  const roundSelect = (f: Extract<Formula, { round: unknown }>) => {
    const s = el('select');
    s.setAttribute('aria-label', 'Rounding');
    const names: Record<string, string> = {
      none: 'Do not round',
      floor: 'Round down',
      ceil: 'Round up',
      round: 'Round to nearest',
      truncate: 'Drop the decimals',
    };
    for (const r of ROUNDS) s.append(new Option(names[r] ?? r, r));
    s.value = f.round;
    s.addEventListener('change', () => {
      f.round = s.value as typeof f.round;
      touch();
    });
    return s;
  };
  const row = (...kids: (Node | string)[]) => {
    const r = el('div', 'formula-row');
    r.append(...kids);
    return r;
  };

  const kind = el('select');
  kind.setAttribute('aria-label', 'Kind of formula');
  for (const k of KINDS) kind.append(new Option(KIND_LABEL[k], k));
  kind.value = draft.formula.kind;
  kind.addEventListener('change', () => {
    draft.formula = starting(kind.value as Formula['kind'], defs, draft.statId);
    hooks.redraw();
  });
  box.append(row(kind));

  const f = draft.formula;
  if (f.kind === 'sum') {
    f.terms.forEach((t, i) => {
      const gone = el('button', 'x', '×');
      gone.type = 'button';
      gone.setAttribute('aria-label', `Remove row ${i + 1}`);
      gone.addEventListener('click', () => {
        f.terms.splice(i, 1);
        hooks.redraw();
      });
      box.append(
        row(
          numberInput(`Number in row ${i + 1}`, t.coefficient, (v) => {
            t.coefficient = v;
          }),
          ' × ',
          statSelect(`Stat in row ${i + 1}`, t.stat, (v) => {
            t.stat = v;
          }),
          gone,
        ),
      );
    });
    const more = el('button', 'btn', 'Add a stat');
    more.type = 'button';
    more.addEventListener('click', () => {
      f.terms.push({ stat: '', coefficient: '1' });
      hooks.redraw();
    });
    box.append(
      more,
      row(
        '+ ',
        numberInput('Number added', f.offset, (v) => {
          f.offset = v;
        }),
        roundSelect(f),
      ),
    );
  } else if (f.kind === 'linear') {
    box.append(
      row(
        statSelect('Stat to scale', f.source, (v) => {
          f.source = v;
        }),
        ' × ',
        numberInput('Multiplier', f.multiplier, (v) => {
          f.multiplier = v;
        }),
        ' + ',
        numberInput('Number added', f.offset, (v) => {
          f.offset = v;
        }),
        roundSelect(f),
      ),
    );
  } else if (f.kind === 'contents') {
    box.append(
      row(
        'The ',
        statSelect('Stat to count inside', f.source, (v) => {
          f.source = v;
        }),
        ' of everything inside, by how many',
      ),
    );
  } else {
    const op = el('select');
    op.setAttribute('aria-label', 'Comparison');
    for (const [value, text] of COMPARATORS) op.append(new Option(text, value));
    op.value = f.comparator;
    op.addEventListener('change', () => {
      f.comparator = op.value as Comparator;
      touch();
    });
    const withStat = el('select');
    withStat.setAttribute('aria-label', 'Compare with');
    withStat.append(new Option('another stat', 'stat'), new Option('a number', 'constant'));
    withStat.value = 'stat' in f.right ? 'stat' : 'constant';
    withStat.addEventListener('change', () => {
      f.right = withStat.value === 'stat' ? { stat: '' } : { constant: '0' };
      hooks.redraw();
    });
    const right = f.right;
    box.append(
      row(
        statSelect('Stat to compare', f.left, (v) => {
          f.left = v;
        }),
        op,
        withStat,
        'stat' in right
          ? statSelect('Stat to compare with', right.stat, (v) => {
              right.stat = v;
            })
          : numberInput('Number to compare with', right.constant, (v) => {
              right.constant = v;
            }),
      ),
      row(
        'When it holds: ',
        textField('When it holds', f.trueValue, (v) => {
          f.trueValue = v;
          touch();
        }),
        ' When not: ',
        textField('When it does not hold', f.falseValue, (v) => {
          f.falseValue = v;
          touch();
        }),
      ),
    );
  }

  const dependents = el('p', 'muted');
  bench.transport
    .formulaDependents(draft.statId)
    .then((d) => {
      if (d.length)
        dependents.textContent = `${d.length} ${d.length === 1 ? 'formula reads' : 'formulas read'} ${target?.name ?? 'this stat'}.`;
    })
    .catch(() => {});

  const discard = el('button', 'btn', 'Discard');
  discard.type = 'button';
  discard.addEventListener('click', () => {
    ui.draft = null;
    hooks.redraw();
  });
  save.addEventListener('click', async () => {
    try {
      await bench.formulas.save(draft.entryId, draft.statId, draft.formula, draft.version);
      ui.note = `Saved the formula for ${target?.name ?? 'the stat'}.`;
      ui.draft = null;
    } catch (e) {
      if (e instanceof RefusedError && e.precondition) {
        await bench.formulas.load([draft.entryId], true);
        ui.note = 'The formula changed elsewhere. It is shown as it is now; try again.';
        ui.draft = null;
      } else ui.note = e instanceof Error ? e.message : 'Could not save the formula.';
    }
    hooks.redraw();
  });
  const bar = row(save, discard);
  if (draft.version) {
    const remove = el('button', 'btn danger', 'Remove');
    remove.type = 'button';
    remove.title = 'The stat is no longer worked out here';
    remove.addEventListener('click', async () => {
      try {
        await bench.formulas.remove(draft.entryId, draft.statId, draft.version as string);
        ui.note = `${target?.name ?? 'The stat'} is no longer worked out here.`;
        ui.draft = null;
      } catch (e) {
        ui.note = e instanceof Error ? e.message : 'Could not remove the formula.';
      }
      hooks.redraw();
    });
    bar.append(remove);
  }
  box.append(preview, issues, dependents, bar);
  touch();
  return box;
}

function textField(label: string, value: string, set: (v: string) => void): HTMLInputElement {
  const i = el('input');
  i.type = 'text';
  i.size = 8;
  i.value = value;
  i.setAttribute('aria-label', label);
  i.dataset.key = `formula:${label}`;
  i.addEventListener('input', () => set(i.value));
  return i;
}
