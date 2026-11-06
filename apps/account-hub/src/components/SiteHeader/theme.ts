import { required } from './required';

// The system's preference to begin with (SiteHead sets it before first paint), then the button.
export function renderThemeToggle(root: HTMLElement): void {
  const toggle = required<HTMLButtonElement>(root, '[data-theme-toggle]');
  const page = document.documentElement;

  function apply(dark: boolean) {
    if (dark) {
      page.setAttribute('data-theme', 'dark');
    } else {
      page.removeAttribute('data-theme');
    }

    toggle.textContent = dark ? '☀ light' : '☾ dark';
    toggle.setAttribute('aria-pressed', String(dark));
  }

  apply(window.matchMedia('(prefers-color-scheme: dark)').matches);

  toggle.addEventListener('click', () => apply(page.getAttribute('data-theme') !== 'dark'));
}
