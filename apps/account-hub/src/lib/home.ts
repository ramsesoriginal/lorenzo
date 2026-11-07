// What Home is made of (ADR 0417, AH1, AH6): the tables split into where a person plays and what they
// run, the tasks that need them, and the pages they were last in. Pure and dependency-free, so each
// is tested without a browser.

import type { TableCard } from './campaigns';
import { shelfState, updatesHref } from './shelf';
import { tenantHref } from './tenantKind';
import type { AuditLogEntryOut, InviteOut, SubscriptionOut } from './types';

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
 * A repository they work on that is still a draft is a task. The others (an update waiting, a link
 * about to end, a new player) are `updateTasks`, `linkTasks` and `playerTasks`; `orderTasks` puts
 * them in the order a person reads them. With none, it is a good day.
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

const DAY = 24 * 60 * 60 * 1000;

/** How soon a link's end is a task, and how recent a new player is. */
export const LINK_ENDS_WITHIN_DAYS = 3;
export const NEW_PLAYER_WITHIN_DAYS = 3;

/** An update announced for a repository a library has copied: one task for each, from the list alone. */
export function updateTasks(
  library: { name: string; slug: string },
  subscriptions: SubscriptionOut[],
): Task[] {
  return subscriptions
    .filter((subscription) => shelfState(subscription) === 'update-announced')
    .map((subscription) => ({
      id: `update:${library.slug}:${subscription.repository.id}`,
      text: `${subscription.repository.name} has an update announced for ${library.name}.`,
      action: 'Review updates',
      href: updatesHref(library.slug, subscription.repository.slug),
    }));
}

// How long is left, rounded down: "in 2 days" is never an overstatement, and under a day it says so.
function timeLeft(milliseconds: number): string {
  const days = Math.floor(milliseconds / DAY);

  if (days < 1) return 'within a day';

  return days === 1 ? 'in 1 day' : `in ${days} days`;
}

/** An invite link that still works and ends within a few days: one task for each. `where` names the library or campaign it is for. */
export function linkTasks(
  where: { label: string; slug: string },
  invites: InviteOut[],
  now: number,
): Task[] {
  return invites
    .filter((invite) => {
      const ends = Date.parse(invite.expires_at);

      return (
        invite.is_active &&
        invite.revoked_at === null &&
        ends > now &&
        ends - now <= LINK_ENDS_WITHIN_DAYS * DAY
      );
    })
    .map((invite) => {
      const used =
        invite.max_uses === null
          ? `used ${invite.use_count} times`
          : `used ${invite.use_count} of ${invite.max_uses} times`;

      return {
        id: `link:${invite.id}`,
        text: `An invite link for ${where.label} ends ${timeLeft(Date.parse(invite.expires_at) - now)} (${used}).`,
        action: 'Make a new link',
        href: tenantHref(where.slug),
      };
    });
}

/** The campaign and player an activity entry says joined by a link, or null for anything else. */
function joinedCampaign(entry: AuditLogEntryOut): string | null {
  if (entry.action !== 'campaign_invite.redeemed') return null;

  const match = /(?:^|, )campaign=([^,\s]+), player=/.exec(entry.detail ?? '');

  return match?.[1] ?? null;
}

/** New players of the campaigns a person runs, from a library's activity: one task for each campaign. */
export function playerTasks(
  entries: AuditLogEntryOut[],
  campaigns: Map<string, { name: string; slug: string }>,
  now: number,
): Task[] {
  const counts = new Map<string, number>();

  for (const entry of entries) {
    const campaign = joinedCampaign(entry);
    const at = Date.parse(entry.created_at);

    if (campaign === null || !campaigns.has(campaign)) continue;
    if (now - at > NEW_PLAYER_WITHIN_DAYS * DAY || at > now) continue;

    counts.set(campaign, (counts.get(campaign) ?? 0) + 1);
  }

  return [...counts].map(([id, count]) => {
    const campaign = campaigns.get(id);

    return {
      id: `players:${id}`,
      text:
        count === 1
          ? `A new player joined ${campaign?.name}.`
          : `${count} new players joined ${campaign?.name}.`,
      action: 'See players',
      href: tenantHref(campaign?.slug ?? ''),
    };
  });
}

/** Updates first, then links, then new players, then drafts; each group as it came. */
export function orderTasks(...groups: Task[][]): Task[] {
  return groups.flat();
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
