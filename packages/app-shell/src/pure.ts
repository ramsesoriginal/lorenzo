// The parts of the header that need no page: what a link's address is, which one is the current
// page, and which theme comes first. Kept apart so they can be tested without a browser.

export type Theme = 'light' | 'dark';

export type NavItem = {
  label: string;
  // The page's path, with its trailing slash: it is both the address and what marks the current page.
  href: string;
  // A library's page: it carries the library in `?tenant=` and stays hidden until there is one.
  needsLibrary?: boolean;
};

/** The saved choice if there is one, otherwise what the system prefers. */
export function initialTheme(saved: string | null, prefersDark: boolean): Theme {
  if (saved === 'light' || saved === 'dark') return saved;

  return prefersDark ? 'dark' : 'light';
}

export function otherTheme(theme: Theme): Theme {
  return theme === 'dark' ? 'light' : 'dark';
}

/** What the toggle says: the theme it would switch to. */
export function themeToggleLabel(theme: Theme): string {
  return theme === 'dark' ? 'Light theme' : 'Dark theme';
}

/**
 * Where a navigation link goes, or null when it cannot yet: a library's page has no address until
 * a library is known.
 */
export function navHref(item: Pick<NavItem, 'href' | 'needsLibrary'>, library: string | null) {
  if (!item.needsLibrary) return item.href;

  return library ? `${item.href}?tenant=${encodeURIComponent(library)}` : null;
}

/** Whether a link to `href` is the page at `pathname`, with or without a trailing slash. */
export function isCurrentPage(href: string, pathname: string): boolean {
  const normal = (path: string) => (path.endsWith('/') ? path : `${path}/`);

  return normal(href) === normal(pathname);
}
