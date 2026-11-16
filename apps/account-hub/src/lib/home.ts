// What Home is made of (ADR 0417, AH1, AH6): the tables split into where a person plays and what they
// run, the tasks that need them, and the pages they were last in. Pure and dependency-free, so each
// is tested without a browser.

import { agoText } from '@lorenzo/app-shell';
import type { RunRow, TableCard } from './campaigns';
import { type GmWords, gmWords } from './gmTitle';
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
export type Task = {
  id: string;
  /** What the task is, for its icon: an update, a link about to end, a new player, a draft. */
  kind: 'update' | 'link' | 'player' | 'draft';
  text: string;
  /** Where it is, under the text: the library, how long ago. */
  meta?: string;
  action: string;
  href: string;
};

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
      kind: 'draft' as const,
      text: `${repository.name} is still a draft.`,
      meta: `You are its ${repository.role}`,
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
      kind: 'update' as const,
      text: `${subscription.repository.name} has an update announced for ${library.name}.`,
      meta: library.name,
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
  where: { label: string; slug: string; place?: string },
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
        kind: 'link' as const,
        ...(where.place ? { meta: where.place } : {}),
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
  campaigns: Map<string, { name: string; slug: string; place?: string }>,
  now: number,
): Task[] {
  const counts = new Map<string, { count: number; latest: number }>();

  for (const entry of entries) {
    const campaign = joinedCampaign(entry);
    const at = Date.parse(entry.created_at);

    if (campaign === null || !campaigns.has(campaign)) continue;
    if (now - at > NEW_PLAYER_WITHIN_DAYS * DAY || at > now) continue;

    const seen = counts.get(campaign);

    counts.set(campaign, {
      count: (seen?.count ?? 0) + 1,
      latest: Math.max(seen?.latest ?? 0, at),
    });
  }

  return [...counts].map(([id, { count, latest }]) => {
    const campaign = campaigns.get(id);

    return {
      id: `players:${id}`,
      kind: 'player' as const,
      meta: [campaign?.place, agoText(now, latest)].filter(Boolean).join(' · '),
      text:
        count === 1
          ? `A new player joined ${campaign?.name}.`
          : `${count} new players joined ${campaign?.name}.`,
      action: 'See players',
      href: tenantHref(campaign?.slug ?? ''),
    };
  });
}

export { agoText } from '@lorenzo/app-shell';

/** The line under "Home": who it is, and how many things need them. */
export function homeSubtitle(name: string | null, needs: number): string {
  const count =
    needs === 0
      ? 'nothing needs you'
      : `${needs} ${needs === 1 ? 'thing needs' : 'things need'} you`;

  return name ? `${name} · ${count}` : count[0]?.toUpperCase() + count.slice(1);
}

/** Updates first, then links, then new players, then drafts; each group as it came. */
export function orderTasks(...groups: Task[][]): Task[] {
  return groups.flat();
}

// --- What you run ---------------------------------------------------------------

/** One line of "What you run": a library or a repository, with where it stands. */
export type RunItem = {
  kind: 'library' | 'repository';
  name: string;
  href: string;
  /** "3 people · 2 campaigns · you Storyteller", or "You are its Owner". */
  meta: string;
  /** Who the person is there: Owner, Organizer, Author, or what the campaign calls its game master. */
  role?: string;
  /** What state it is in, in words, with the pattern and icon the brand's state chip draws. */
  chip?: { state: 'waiting' | 'synced' | 'stale'; text: string; icon: string };
};

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/**
 * The libraries a person looks after (a role there, or a campaign they run) and the repositories they
 * work on, libraries first. A library says what it holds, from what the person may count: people only
 * where they administer it.
 */
export function runItems(input: {
  libraries: { id: string; name: string; slug: string; role: string; admin: boolean }[];
  rows: readonly RunRow[];
  campaignCounts: ReadonlyMap<string, number>;
  peopleCounts: ReadonlyMap<string, number>;
  /** The slugs of the libraries with an update announced. */
  updatesWaiting: ReadonlySet<string>;
  repositories: RepositoryFacts[];
  repositoryHref: (slug: string) => string;
  /** A role in words: "orga" is "Organizer". */
  roleText: (role: string) => string;
}): RunItem[] {
  const items: RunItem[] = [];

  for (const library of input.libraries) {
    const mine = input.rows.filter((row) => row.tenantId === library.id);
    const gm = mine.filter((row) => row.role === 'gm');
    const holdsRole = ['owner', 'orga', 'author'].includes(library.role);

    if (!holdsRole && mine.length === 0) continue;

    const people = input.peopleCounts.get(library.id);
    const campaigns = input.campaignCounts.get(library.id);
    const words: GmWords = gmWords(
      gm.map((row) => ({ gm_title: row.gm.title, gm_title_plural: row.gm.plural })),
    );
    const parts = [
      ...(people === undefined ? [] : [plural(people, 'person', 'people')]),
      ...(campaigns === undefined ? [] : [plural(campaigns, 'campaign', 'campaigns')]),
      ...(gm.length > 0 ? [`you ${words.title}`] : []),
    ];

    items.push({
      kind: 'library',
      name: library.name,
      href: tenantHref(library.slug),
      meta: parts.join(' · '),
      role: holdsRole ? input.roleText(library.role) : words.title,
      ...(input.updatesWaiting.has(library.slug)
        ? { chip: { state: 'waiting' as const, text: 'Updates waiting', icon: 'update-available' } }
        : {}),
    });
  }

  for (const repository of input.repositories) {
    items.push({
      kind: 'repository',
      name: repository.name,
      href: input.repositoryHref(repository.slug),
      meta: `You are its ${repository.role}`,
      ...(repository.status === null
        ? {}
        : repository.status === 'Draft'
          ? { chip: { state: 'stale' as const, text: 'Draft', icon: 'stale' } }
          : { chip: { state: 'synced' as const, text: repository.status, icon: 'select-item' } }),
    });
  }

  return items;
}

// --- Continue ----------------------------------------------------------------

export type { RecentPage } from '@lorenzo/app-shell';
export { pageTitle, parseRecent, RECENT_MAX, rememberPage } from '@lorenzo/app-shell';
