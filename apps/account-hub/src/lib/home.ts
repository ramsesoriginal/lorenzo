// What Home is made of (ADR 0417, AH1, AH6): the tables split into where a person plays and what they
// run, the tasks that need them, and the pages they were last in. Pure and dependency-free, so each
// is tested without a browser.

import type { TableCard } from './campaigns';

/** Where you play (you hold a seat) and what you run (any other role in it); a table can be in both. */
export function splitTables(cards: TableCard[]): { play: TableCard[]; run: TableCard[] } {
  return {
    play: cards.filter((card) => card.roles.includes('Player')),
    run: cards.filter((card) => card.roles.some((role) => role !== 'Player')),
  };
}

// --- Needs you ---------------------------------------------------------------

/** A task: something to do, never news (notifications stay in the bell and its page, AH6). */
export type Task = { id: string; text: string; action: string; href: string };

export type RepositoryFacts = { name: string; slug: string; role: string; status: string | null };

/**
 * The tasks a person has, from what Home already knows. A repository they work on that is still a
 * draft is one. The list grows as more is computed (updates waiting, a link about to end, a new
 * player); until then it is short, and often empty, which is a good day.
 */
export function needsYou(
  repositories: RepositoryFacts[],
  hrefFor: (slug: string) => string,
): Task[] {
  return repositories
    .filter((repository) => repository.status === 'Draft')
    .map((repository) => ({
      id: `draft:${repository.slug}`,
      text: `${repository.name} is still a draft.`,
      action: 'Open it',
      href: hrefFor(repository.slug),
    }));
}

// --- Continue ----------------------------------------------------------------

export type RecentPage = { href: string; title: string };

export const RECENT_MAX = 3;

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
        (entry as RecentPage).href.startsWith('/'),
    );
  } catch {
    return [];
  }
}

/** The title a page gives itself, without the product: "Your profile — Lorenzo" is "Your profile". */
export function pageTitle(documentTitle: string): string {
  return documentTitle.replace(/\s+[—-]\s+Lorenzo.*$/, '').trim() || documentTitle;
}
