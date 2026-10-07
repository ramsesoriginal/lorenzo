// The update inbox of a library (ADR 0203, RFC 0036 §3): a row for each repository it has copied,
// each checked for updates and said in words ("4 changed, 12 new, 1 removed upstream, 2
// conflicts"), those with the most to do first. A check reads a whole repository, so it runs when
// someone opens the inbox, a few at a time, and each row fills in as its answer comes: nothing is
// asked for on the list of repositories itself.

import { describeError } from '../../lib/describeError';
import { getUpdates } from '../../lib/repositories';
import { shelfHref, shelfState, updatesHref } from '../../lib/shelf';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { SubscriptionOut, TenantSummaryOut } from '../../lib/types';
import {
  countsSentence,
  countUpdates,
  inboxOrder,
  NOT_COMPARED_NOTE,
  todo,
  type UpdateCounts,
} from '../../lib/updates';

const required = requiredIn('Update inbox');

// How many repositories are checked at once.
const AT_ONCE = 3;

type Row = {
  subscription: SubscriptionOut;
  name: string;
  // Null while it is checked, or when it cannot be.
  counts: UpdateCounts | null;
  // What the row says: how it is going, or why it cannot be checked.
  text: string;
  state: 'checking' | 'up-to-date' | 'updates' | 'cannot' | 'error';
};

export type Inbox = {
  open(library: TenantSummaryOut, subscriptions: SubscriptionOut[], isCurrent: () => boolean): void;
  close(): void;
};

const STATE_LABEL: Record<Row['state'], string> = {
  checking: 'Checking…',
  'up-to-date': 'Up to date',
  updates: 'Updates',
  cannot: 'Not checked',
  error: 'Not checked',
};

const STATE_PILL: Record<Row['state'], string> = {
  checking: 'pill',
  'up-to-date': 'pill pill-success',
  updates: 'pill pill-warning',
  cannot: 'pill',
  error: 'pill pill-danger',
};

// `view` is the inbox block in the <RepositoriesPanel />, and `panel` the panel, whose template it
// uses.
export function createInbox(panel: HTMLElement, view: HTMLElement): Inbox {
  const title = required<HTMLElement>(view, '[data-inbox-title]');
  const note = required<HTMLElement>(view, '[data-inbox-note]');
  const error = required<HTMLElement>(view, '[data-inbox-error]');
  const empty = required<HTMLElement>(view, '[data-inbox-empty]');
  const list = required<HTMLElement>(view, '[data-inbox-list]');
  const back = required<HTMLAnchorElement>(view, '[data-inbox-back]');
  const recheck = required<HTMLButtonElement>(view, '[data-inbox-recheck]');

  let library: TenantSummaryOut | null = null;
  let subscriptions: SubscriptionOut[] = [];
  let rows: Row[] = [];
  // A newer open, or a close, makes the answers still on their way not matter.
  let latest = 0;
  let current: () => boolean = () => true;

  function paint(): void {
    const mine = library;

    if (!mine) return;

    list.replaceChildren(
      ...inboxOrder(rows).map((row) => {
        const item = cloneRoot(panel, '[data-inbox-row-template]');
        const link = required<HTMLAnchorElement>(item, '[data-name]');
        const state = required<HTMLElement>(item, '[data-state]');
        const checkable = row.state !== 'cannot';

        link.textContent = row.name;
        link.href = checkable
          ? updatesHref(mine.slug, row.subscription.repository.id)
          : shelfHref(mine.slug, row.subscription.repository.id);
        required<HTMLElement>(item, '[data-summary]').textContent = row.text;
        state.className = STATE_PILL[row.state];
        state.textContent = STATE_LABEL[row.state];

        return item;
      }),
    );
  }

  async function check(row: Row, turn: number): Promise<void> {
    const mine = library;

    if (!mine) return;

    try {
      const updates = await getUpdates(mine.id, row.subscription.repository.id, { fresh: true });

      if (turn !== latest) return;

      if (updates === null) {
        row.state = 'cannot';
        row.text =
          'It cannot be checked right now: it is not offered to your library, or not published.';
      } else {
        row.counts = countUpdates(updates);
        row.state = todo(row.counts) === 0 ? 'up-to-date' : 'updates';
        row.text = countsSentence(row.counts);
      }
    } catch (cause) {
      if (turn !== latest) return;

      row.state = 'error';
      row.text = describeError(cause);
    }

    paint();
  }

  // Checks every row that can be, a few at a time.
  async function checkAll(turn: number): Promise<void> {
    const queue = rows.filter((row) => row.state === 'checking');

    await Promise.all(
      Array.from({ length: Math.min(AT_ONCE, queue.length) }, async () => {
        for (let row = queue.shift(); row; row = queue.shift()) {
          if (turn !== latest) return;

          await check(row, turn);
        }
      }),
    );
  }

  function start(): void {
    const turn = ++latest;

    rows = subscriptions
      .filter((subscription) => subscription.copied_at !== null)
      .map((subscription) => {
        // A copy whose repository is no longer offered or published has nothing to check.
        const state = shelfState(subscription);
        const offered = state === 'copied' || state === 'update-announced';

        return {
          subscription,
          name: subscription.repository.name,
          counts: null,
          text: offered
            ? 'Checking for updates…'
            : 'No updates will arrive: it is no longer offered to your library, or not published.',
          state: offered ? ('checking' as const) : ('cannot' as const),
        };
      });
    empty.hidden = rows.length > 0;
    recheck.hidden = rows.length === 0;
    error.hidden = true;
    paint();
    void checkAll(turn).catch((cause) => {
      if (turn !== latest || !current()) return;

      error.hidden = false;
      error.textContent = describeError(cause);
    });
  }

  recheck.addEventListener('click', start);

  return {
    open(next, all, isCurrent) {
      library = next;
      subscriptions = all;
      current = isCurrent;
      title.textContent = `Updates for ${next.name}`;
      note.textContent = NOT_COMPARED_NOTE;
      back.href = shelfHref(next.slug);
      start();
    },

    close() {
      latest += 1;
      library = null;
    },
  };
}
