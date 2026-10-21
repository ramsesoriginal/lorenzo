/** Keep the active appearance when Astro replaces the HTML element. */
document.addEventListener('astro:before-swap', (event) => {
  event.newDocument.documentElement.dataset.theme =
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
});

export function bindThemeToggle() {
  const toggle = document.querySelector<HTMLButtonElement>('[data-theme-toggle]');
  if (!toggle) return;
  function show() {
    const dark = document.documentElement.dataset.theme === 'dark';
    if (!toggle) return;
    toggle.textContent = dark ? 'Light theme' : 'Dark theme';
    toggle.setAttribute('aria-pressed', String(dark));
  }
  show();
  toggle.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('lorenzo:sessions:theme', theme);
    } catch {
      // A blocked preference store must not prevent changing appearance for this visit.
    }
    show();
  });
}
