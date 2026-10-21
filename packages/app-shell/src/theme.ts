import { initialTheme, otherTheme, type Theme, themeToggleLabel } from './pure';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    // A blocked preference store leaves the system's appearance.
    return null;
  }
}

function write(key: string, theme: Theme) {
  try {
    localStorage.setItem(key, theme);
  } catch {
    // A blocked preference store must not stop the appearance changing for this visit.
  }
}

function applied(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

// Astro replaces the <html> element on every in-app navigation; the new one starts without the
// attribute SiteHead set before first paint, so the one in use is carried over.
let swapKept = false;

function keepThemeAcrossSwaps() {
  if (swapKept) return;

  swapKept = true;
  document.addEventListener('astro:before-swap', (event) => {
    (event as Event & { newDocument: Document }).newDocument.documentElement.dataset.theme =
      applied();
  });
}

/**
 * The toggle in the header: the saved choice (or the system's) to begin with, then the button. It
 * names the theme it switches to and says whether dark is on.
 */
export function bindThemeToggle(root: HTMLElement, storageKey: string): void {
  const toggle = root.querySelector<HTMLButtonElement>('[data-theme-toggle]');

  keepThemeAcrossSwaps();

  if (!toggle) return;

  function show() {
    if (!toggle) return;

    toggle.textContent = themeToggleLabel(applied());
    toggle.setAttribute('aria-pressed', String(applied() === 'dark'));
  }

  // SiteHead has already set the attribute; this only covers a page that lacks it.
  if (!document.documentElement.dataset.theme) {
    document.documentElement.dataset.theme = initialTheme(
      read(storageKey),
      window.matchMedia('(prefers-color-scheme: dark)').matches,
    );
  }

  show();
  toggle.addEventListener('click', () => {
    const theme = otherTheme(applied());

    document.documentElement.dataset.theme = theme;
    write(storageKey, theme);
    show();
  });
}
