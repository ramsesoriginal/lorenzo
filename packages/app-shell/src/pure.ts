// The parts of the header that need no page: what a link's address is, which one is the current
// page, and which theme comes first. Kept apart so they can be tested without a browser.

export type Theme = 'light' | 'dark';

export type NavItem = {
  label: string;
  // The page's path, with its trailing slash: it is both the address and what marks the current page.
  href: string;
  // A library's page: it carries the library in `?tenant=` and stays hidden until there is one.
  needsLibrary?: boolean;
  // An id in the brand's icons.svg without the `icon-` prefix, for the phone's tab bar.
  icon?: string;
  // The link stays hidden until the app says the person may have it (`shell.allow(requires)`): a page
  // that has nothing for someone is not offered to them.
  requires?: string;
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

/** The locale the clock is written in: the page's language, and for plain English the day-first form the design draws. */
export function clockLocale(lang: string | null | undefined): string | undefined {
  const tag = (lang ?? '').trim();

  if (tag === '') return undefined;

  return tag.toLowerCase() === 'en' ? 'en-GB' : tag;
}

/** The real date and time for the status bar, e.g. "Wed 4 November at 20:59", in the reader's language. */
export function clockText(now: Date, locale?: string): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  }).format(now);
}

/** The time of day alone, "19:40", for "Synced 19:40". */
export function timeText(at: Date, locale?: string): string {
  return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(at);
}

/**
 * The phone's tab bar has room for `max` links and a "More" button: with more links than that, the
 * rest go into the More sheet.
 */
export function splitTabs<T>(items: T[], max = 3): { tabs: T[]; rest: T[] } {
  return { tabs: items.slice(0, max), rest: items.slice(max) };
}

/** The letters on the account button: the first of the first two words, or of an address's name. */
export function initials(label: string | undefined): string {
  const name = (label ?? '').split('@')[0]?.trim() ?? '';
  const parts = name.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((part) => Array.from(part)[0] ?? '');

  return letters.join('').toUpperCase() || '·';
}
