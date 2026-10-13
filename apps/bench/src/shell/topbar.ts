// The rest of the title bar, after the repository menu: the one place to find anything (the
// palette), the layouts, and the appearance (light or dark, a serif or a sans-serif for texts).

import { canRemember, FACES, THEMES, type Theme } from './appearance';
import { icon } from './icons';
import type { Shell } from './shell';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

/** A row of exclusive choices: the one that holds is pressed. */
function choices<T extends string>(
  label: string,
  options: readonly (readonly [T, string])[],
  current: () => T,
  choose: (value: T) => void,
): HTMLElement {
  const seg = el('div', 'seg');
  seg.setAttribute('role', 'group');
  seg.setAttribute('aria-label', label);
  const draw = () => {
    for (const b of seg.querySelectorAll('button'))
      b.setAttribute('aria-pressed', String(b.dataset.value === current()));
  };
  for (const [value, text] of options) {
    const b = el('button', undefined, text);
    b.type = 'button';
    b.dataset.value = value;
    b.addEventListener('click', () => {
      choose(value);
      draw();
    });
    seg.append(b);
  }
  draw();
  return seg;
}

/** The appearance popover: the theme and the writing font, under the button that opened it. */
function openAppearance(anchor: HTMLButtonElement, shell: Shell): void {
  if (document.querySelector('.ap')) return;
  const backdrop = el('div', 'ap-bg');
  const box = el('div', 'ap');
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', 'Appearance');
  const close = () => {
    backdrop.remove();
    box.remove();
    anchor.setAttribute('aria-expanded', 'false');
    anchor.focus();
  };
  const theme = choices<Theme>(
    'Theme',
    THEMES,
    () => shell.theme(),
    (t) => shell.setTheme(t),
  );
  const face = choices<'serif' | 'sans'>(
    'Writing font',
    FACES,
    () => (shell.sans() ? 'sans' : 'serif'),
    (f) => shell.setSans(f === 'sans'),
  );
  box.append(
    el('p', 'aph', 'Theme'),
    theme,
    el('p', 'aph', 'Writing font'),
    face,
    el(
      'p',
      'apn',
      canRemember()
        ? 'System follows your device. Both choices are remembered on this device.'
        : 'System follows your device. This browser cannot remember your choices.',
    ),
  );
  backdrop.addEventListener('pointerdown', close);
  box.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      close();
    }
  });
  anchor.setAttribute('aria-expanded', 'true');
  document.body.append(backdrop, box);
  (box.querySelector('[aria-pressed="true"]') as HTMLElement | null)?.focus();
}

/** Adds the palette button, the layouts and the appearance choices to the bar. */
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

  // The letters are the button's mark, as in the design: the type is the icon.
  const aa = el('button', 'aa', 'Aa');
  aa.type = 'button';
  aa.title = 'Appearance: theme and writing font';
  aa.setAttribute('aria-label', 'Appearance');
  aa.addEventListener('click', () => openAppearance(aa, shell));
  aa.setAttribute('aria-haspopup', 'dialog');
  aa.setAttribute('aria-expanded', 'false');

  const who = bar.querySelector('.who');
  for (const n of [el('span', 'sp'), cmd, el('span', 'sp'), shell.layoutEl, aa])
    bar.insertBefore(n, who);
}
