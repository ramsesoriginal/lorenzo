// How the page looks to its reader: light or dark (or what the device says), and whether texts are
// set in a serif or a sans-serif. Both are a person's choice, kept on the device only.

export type Theme = 'system' | 'light' | 'dark';

export const THEMES: readonly (readonly [Theme, string])[] = [
  ['system', 'System'],
  ['light', 'Light'],
  ['dark', 'Dark'],
];

export const FACES: readonly (readonly ['serif' | 'sans', string])[] = [
  ['serif', 'Serif'],
  ['sans', 'Sans-serif'],
];

const THEME_KEY = 'bench:theme';
const SANS_KEY = 'bench:sans';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Whether the choices can be kept on this device (a private window may not allow it). */
export function canRemember(): boolean {
  try {
    localStorage.setItem('bench:probe', '1');
    localStorage.removeItem('bench:probe');
    return true;
  } catch {
    return false;
  }
}

export function savedTheme(): Theme {
  const t = read(THEME_KEY);
  return t === 'light' || t === 'dark' ? t : 'system';
}

export function savedSans(): boolean {
  return read(SANS_KEY) === '1';
}

/** Paints the page for a theme; "system" follows the device, which `watchDevice` keeps up with. */
export function applyTheme(theme: Theme): void {
  const dark =
    theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
}

export function applySans(sans: boolean): void {
  document.documentElement.classList.toggle('sans', sans);
}

export function rememberTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* not remembered */
  }
}

export function rememberSans(sans: boolean): void {
  try {
    localStorage.setItem(SANS_KEY, sans ? '1' : '0');
  } catch {
    /* not remembered */
  }
}

/** Repaints when the device changes between light and dark, for those who chose "System". */
export function watchDevice(): void {
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    applyTheme(savedTheme());
  });
}
