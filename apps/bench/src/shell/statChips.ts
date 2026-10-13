// The `{weight}` chips in a drawn text (ADR 0252): the value of a stat of the entry the text is
// about, drawn as a chip, with − and + for a number, which write the entry's own value through
// the command layer. A value the entry only inherits is drawn dashed.

import type { Bench } from '../core/bench';
import { add, stepOf } from './gridModel';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls: string, text: string) => {
  const e = document.createElement(tag);
  e.className = cls;
  e.textContent = text;
  return e;
};

/** Gives each `.ls-stat` chip under `root` its buttons. `home` is the entry the text belongs to. */
export function decorateStats(root: HTMLElement, bench: Bench, home: string): void {
  for (const chip of root.querySelectorAll<HTMLElement>('span.ls-stat')) {
    const def = bench.statDefs.find((d) => d.name === chip.title);
    const step = def ? stepOf(def.type) : null;
    chip.tabIndex = 0;
    chip.setAttribute('role', 'group');
    chip.setAttribute('aria-label', `${chip.title}: ${chip.textContent}`);
    if (!def || step === null) continue;
    const view = bench.view(home)?.stats.find((s) => s.statId === def.id);
    const value = typeof view?.value === 'number' ? view.value : null;
    if (value === null) continue;
    const nudge = (sign: 1 | -1) => () => {
      bench.setStat(home, def.id, add(value, sign * step));
    };
    for (const [label, glyph, sign] of [
      [`Decrease ${def.name}`, '−', -1],
      [`Increase ${def.name}`, '+', 1],
    ] as const) {
      const b = el('button', 'stat-step', glyph);
      b.type = 'button';
      b.setAttribute('aria-label', label);
      // Pressing must not turn the block into source.
      b.addEventListener('mousedown', (ev) => ev.preventDefault());
      b.addEventListener('click', nudge(sign));
      chip.append(b);
    }
  }
}
