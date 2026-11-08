// "Continue" (D16), the block every Home shares: the pages a person had open most lately in this app,
// kept in the browser. The logic is here so each app keeps the same list in the same shape; where it is
// kept (the key) is the app's.

export type RecentPage = { href: string; title: string; at?: number };

export const RECENT_MAX = 3;

const DAY = 24 * 60 * 60 * 1000;

/** The page just opened first, no repeats, at most `max`. */
export function rememberPage(
  recent: RecentPage[],
  page: RecentPage,
  max = RECENT_MAX,
): RecentPage[] {
  return [page, ...recent.filter((entry) => entry.href !== page.href)].slice(0, max);
}

/** What was stored, kept only where it is the right shape (it is read from a browser). */
export function parseRecent(text: string | null): RecentPage[] {
  try {
    const value: unknown = JSON.parse(text ?? '[]');

    if (!Array.isArray(value)) return [];

    return value.filter(
      (entry): entry is RecentPage =>
        typeof entry === 'object' &&
        entry !== null &&
        typeof (entry as RecentPage).href === 'string' &&
        typeof (entry as RecentPage).title === 'string' &&
        (typeof (entry as RecentPage).at === 'number' || (entry as RecentPage).at === undefined) &&
        (entry as RecentPage).href.startsWith('/'),
    );
  } catch {
    return [];
  }
}

/** The title a page gives itself, without the product: "Your profile — Lorenzo" is "Your profile". */
export function pageTitle(documentTitle: string): string {
  // Found from the dash, not from the space before it: a title is whatever a page wrote, and a regular
  // expression that starts at every space is quadratic on a long run of them.
  for (const match of documentTitle.matchAll(/[—-]\s+Lorenzo/g)) {
    const before = documentTitle.slice(0, match.index);

    if (before === '' || before.charAt(before.length - 1).trim() !== '') continue;

    return before.trim() || documentTitle;
  }

  return documentTitle;
}

/** How long ago, in days: "today", "yesterday", "3 days ago". */
export function agoText(now: number, at: number): string {
  const days = Math.floor((now - at) / DAY);

  if (days < 1) return 'today';

  return days === 1 ? 'yesterday' : `${days} days ago`;
}
