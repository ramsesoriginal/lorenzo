// What Studio says about who uses a repository and what it is built on (RFC 0036 §4, ADR 0205), as
// plain functions over what the API returns. No DOM and nothing but ./types, so they run under Node
// in the unit tests. The words are those of identity.md §14.3.

import { onRelease } from './releases';
import { dayOf, type ShelfState, shelfState } from './shelf';
import type { SubscriberOut, SubscriptionOut } from './types';

export type UsingState = 'invited' | 'copied' | 'kept';

// Where a library stands with a repository, from what its owner can see: an invitation, a copy, or
// both. A copy that outlived its invitation is the third: the library keeps what it copied and
// gets no more updates.
export function usingState(row: Pick<SubscriberOut, 'granted_at' | 'copied_at'>): UsingState {
  if (row.granted_at === null) return 'kept';

  return row.copied_at === null ? 'invited' : 'copied';
}

export const USING_LABEL: Record<UsingState, string> = {
  invited: 'Invited, not copied yet',
  copied: 'Copied',
  kept: 'Not invited any more',
};

export const USING_PILL: Record<UsingState, string> = {
  invited: 'pill',
  copied: 'pill pill-success',
  kept: 'pill',
};

// What each row says in a line: the days it is invited, copied and last updated.
export function usingLine(row: SubscriberOut): string {
  const parts: string[] = [];

  if (row.granted_at) parts.push(`Invited ${dayOf(row.granted_at)}`);
  if (row.copied_at) parts.push(`copied ${dayOf(row.copied_at)}`);
  if (row.synced_at && row.copied_at && dayOf(row.synced_at) !== dayOf(row.copied_at)) {
    parts.push(`last updated ${dayOf(row.synced_at)}`);
  }
  const release = onRelease(row);

  if (release) parts.push(release);
  if (row.granted_at === null && row.copied_at) {
    return `${parts.join(', ')}. It keeps its copy and gets no more updates unless you invite it again.`;
  }

  return `${parts.join(', ')}.`;
}

// The whole in a sentence: how many have an invitation or a copy, and how many of those copied it.
export function usingSummary(rows: readonly SubscriberOut[]): string {
  if (rows.length === 0) {
    return 'Nothing is using this repository yet: no library has been invited to it.';
  }

  const copied = rows.filter((row) => row.copied_at !== null).length;
  const holders =
    rows.length === 1
      ? '1 library or repository has'
      : `${rows.length} libraries and repositories have`;

  return `${holders} an invitation or a copy. ${copied} of them ${copied === 1 ? 'has' : 'have'} copied it.`;
}

// A library's id as it can be pasted: what the API takes to invite one.
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function libraryIdProblem(text: string): string | null {
  const id = text.trim();

  if (id === '') return 'Paste the id of the library. Its owner can read it off its page.';
  if (!ID.test(id))
    return 'That is not an id: it is 36 characters, letters and numbers with dashes.';

  return null;
}

export const INVITE_HELP =
  'A library can copy a repository once it is invited to it. Invite one by its id, which its owner can give you.';

// What stopping an invitation does, said before it does it: the copy stays, and the library is told
// (ADR 0199).
export function stopInvitingConfirmation(name: string): string {
  return `Stop inviting “${name}”? What it copied stays with it, and it gets no more updates from this repository unless you invite it again. Its Owners and Organizers are told.`;
}

export type BuiltOn = {
  id: string;
  name: string;
  slug: string | null;
  state: ShelfState;
  // Where there is anything to check: a copy of what is still offered and published.
  checkable: boolean;
  line: string;
};

// The repositories a repository copies from, or has been invited to copy from, by name.
export function builtOn(subscriptions: readonly SubscriptionOut[]): BuiltOn[] {
  return subscriptions
    .map((subscription) => {
      const state = shelfState(subscription);
      const { repository } = subscription;
      const parts: string[] = [];

      if (subscription.copied_at) parts.push(`copied ${dayOf(subscription.copied_at)}`);
      if (subscription.synced_at && subscription.copied_at) {
        parts.push(`last updated ${dayOf(subscription.synced_at)}`);
      }
      if (!subscription.copied_at && subscription.granted_at) {
        parts.push(`invited ${dayOf(subscription.granted_at)}`);
      }

      return {
        id: repository.id,
        name: repository.name,
        slug: repository.slug,
        state,
        checkable:
          subscription.copied_at !== null && (state === 'copied' || state === 'update-announced'),
        line: parts.length === 0 ? '' : `${parts.join(', ')}.`,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }));
}

export const BUILT_ON_NONE =
  'This repository is not built on another: it has not copied one, and none is offered to it.';

// Said under the list: how a repository gets another to build on, since only the other's Owner can
// invite it.
export const BUILT_ON_ADD =
  'To build on another repository, ask its Owner to invite this one. Then copy it from the repositories offered to this one.';
