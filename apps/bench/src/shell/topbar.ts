// The rest of the title bar, after the repository menu: the one place to find anything (the
// palette), the layouts, and the choice of a serif or sans-serif text.

import { icon } from './icons';
import type { Shell } from './shell';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const SANS = 'bench:sans';

/** Whether texts are set in the sans-serif (a person's choice, kept on the device). */
function savedSans(): boolean {
  try {
    return localStorage.getItem(SANS) === '1';
  } catch {
    return false;
  }
}

/** Adds the palette button, the layouts and the text font choice to the bar. */
export function decorateTopBar(bar: HTMLElement, shell: Shell): void {
  const cmd = el('button', 'cmd');
  cmd.type = 'button';
  cmd.setAttribute('aria-label', 'Find an entry or do anything');
  cmd.append(
    icon('search'),
    el('span', 'cmd-text', 'Find an entry or do anything'),
    el('kbd', 'kbd', 'Ctrl K'),
  );
  cmd.addEventListener('click', () => shell.openPalette());

  const aa = el('button', 'aa', 'Aa');
  aa.type = 'button';
  const sans = savedSans();
  document.documentElement.classList.toggle('sans', sans);
  aa.setAttribute('aria-pressed', String(sans));
  aa.title = 'Set texts in a serif or a sans-serif';
  aa.setAttribute('aria-label', 'Text in sans-serif');
  aa.addEventListener('click', () => {
    const now = !document.documentElement.classList.contains('sans');
    document.documentElement.classList.toggle('sans', now);
    aa.setAttribute('aria-pressed', String(now));
    try {
      localStorage.setItem(SANS, now ? '1' : '0');
    } catch {
      /* not remembered */
    }
  });

  const who = bar.querySelector('.who');
  for (const n of [el('span', 'sp'), cmd, el('span', 'sp'), shell.layoutEl, aa])
    bar.insertBefore(n, who);
}
