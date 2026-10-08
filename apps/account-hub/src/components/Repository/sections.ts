// The tabs of a repository in Studio that are about its place among others (ADR 0205): who uses it,
// what it is built on, and its activity. Each reads what it shows when the repository is shown,
// says its own failure in its own place, and is dropped if another repository was shown meanwhile.

import { knownNames } from '../../lib/activityNames';
import { describeError } from '../../lib/describeError';
import {
  getUpdates,
  inviteLibrary,
  listLibraryRepositories,
  listSubscribers,
  stopInviting,
} from '../../lib/repositories';
import { SHELF_STATE_LABEL, SHELF_STATE_PILL, shelfHref, updatesHref } from '../../lib/shelf';
import { say, sayError } from '../../lib/statusLine';
import { canChangePeople } from '../../lib/studio';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { RosterEntry, TenantSummaryOut } from '../../lib/types';
import { countsSentence, countUpdates } from '../../lib/updates';
import {
  BUILT_ON_ADD,
  BUILT_ON_NONE,
  builtOn,
  INVITE_HELP,
  libraryIdProblem,
  stopInvitingConfirmation,
  USING_LABEL,
  USING_PILL,
  usingLine,
  usingState,
  usingSummary,
} from '../../lib/using';
import { renderActivityLog } from '../ActivityLog/renderer';

const required = requiredIn('Repository');

export type Section = {
  clear(): void;
  // Reads and shows the section for `repository`. `isCurrent` says whether it is still the one on
  // show; `roster` is who works on it, for names.
  load(
    repository: TenantSummaryOut,
    isCurrent: () => boolean,
    roster: RosterEntry[] | null,
  ): Promise<void>;
};

// How many repositories are checked for updates at once.
const AT_ONCE = 3;

// `root` is the <Repository /> article. `onChanged` is called when an invitation was made or
// stopped, for what is shown around it.
export function createUsing(root: HTMLElement, onChanged: () => void): Section {
  const section = required<HTMLElement>(root, '[data-using]');
  const summary = required<HTMLElement>(root, '[data-using-summary]');
  const error = required<HTMLElement>(root, '[data-using-error]');
  const list = required<HTMLElement>(root, '[data-using-list]');
  const form = required<HTMLFormElement>(root, '[data-invite]');
  const input = required<HTMLInputElement>(root, '[data-invite-id]');
  const status = required<HTMLElement>(root, '[data-invite-status]');

  required<HTMLElement>(root, '[data-invite-help]').textContent = INVITE_HELP;

  let shown: TenantSummaryOut | null = null;

  async function repaint(repository: TenantSummaryOut, isCurrent: () => boolean): Promise<void> {
    const rows = await listSubscribers(repository.id);

    if (!isCurrent()) return;

    summary.textContent = usingSummary(rows);
    list.replaceChildren(
      ...rows.map((row) => {
        const item = cloneRoot(root, '[data-using-template]');
        const state = usingState(row);
        const stop = required<HTMLButtonElement>(item, '[data-stop]');
        const rowStatus = required<HTMLElement>(item, '[data-status]');

        required<HTMLElement>(item, '[data-name]').textContent = row.name;
        required<HTMLElement>(item, '[data-line]').textContent = usingLine(row);

        const pill = required<HTMLElement>(item, '[data-state]');

        pill.className = USING_PILL[state];
        pill.textContent = USING_LABEL[state];

        // Only an Owner stops an invitation, and only where there is one.
        stop.hidden = !(canChangePeople(repository.role) && row.granted_at !== null);
        stop.addEventListener('click', async () => {
          if (!window.confirm(stopInvitingConfirmation(row.name))) return;

          stop.disabled = true;
          say(rowStatus, 'Stopping…');

          try {
            await stopInviting(repository.id, row.tenant_id);
            onChanged();
            await repaint(repository, isCurrent);
          } catch (cause) {
            stop.disabled = false;
            sayError(rowStatus, cause);
          }
        });

        return item;
      }),
    );
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const repository = shown;
    const problem = libraryIdProblem(input.value);

    if (!repository) return;

    if (problem) {
      say(status, problem, true);
      return;
    }

    say(status, 'Inviting…');

    try {
      await inviteLibrary(repository.id, input.value.trim());
      input.value = '';
      say(status, 'Invited. It can copy this repository now, once it is published.');
      await repaint(repository, () => shown === repository);
    } catch (cause) {
      sayError(status, cause);
    }
  });

  return {
    clear() {
      shown = null;
      section.hidden = true;
      list.replaceChildren();
      error.hidden = true;
      form.hidden = true;
      say(status, '');
    },

    async load(repository, isCurrent) {
      shown = repository;
      form.hidden = !canChangePeople(repository.role);

      try {
        await repaint(repository, isCurrent);

        if (isCurrent()) section.hidden = false;
      } catch (cause) {
        if (!isCurrent()) return;

        section.hidden = false;
        sayError(error, cause);
      }
    },
  };
}

export function createBuiltOn(root: HTMLElement): Section {
  const section = required<HTMLElement>(root, '[data-built-on]');
  const error = required<HTMLElement>(root, '[data-built-on-error]');
  const none = required<HTMLElement>(root, '[data-built-on-none]');
  const list = required<HTMLElement>(root, '[data-built-on-list]');
  const offered = required<HTMLAnchorElement>(root, '[data-offered-link]');

  required<HTMLElement>(root, '[data-built-on-add]').textContent = BUILT_ON_ADD;
  none.textContent = BUILT_ON_NONE;

  return {
    clear() {
      section.hidden = true;
      list.replaceChildren();
      error.hidden = true;
    },

    async load(repository, isCurrent) {
      // A repository copies as a library does, so Shelf's screens take it as the one acting.
      offered.href = shelfHref(repository.slug);

      try {
        const rows = builtOn(await listLibraryRepositories(repository.id));

        if (!isCurrent()) return;

        none.hidden = rows.length > 0;
        list.replaceChildren(
          ...rows.map((row) => {
            const item = cloneRoot(root, '[data-built-on-template]');
            const link = required<HTMLAnchorElement>(item, '[data-name]');
            const state = required<HTMLElement>(item, '[data-state]');
            const review = required<HTMLAnchorElement>(item, '[data-review]');

            link.textContent = row.name;
            link.href = shelfHref(repository.slug, row.id);
            required<HTMLElement>(item, '[data-line]').textContent = row.line;
            state.className = SHELF_STATE_PILL[row.state];
            state.textContent = SHELF_STATE_LABEL[row.state];
            review.hidden = !row.checkable;
            review.href = updatesHref(repository.slug, row.id);

            return item;
          }),
        );
        section.hidden = false;

        // How many updates are waiting, asked of each copy a few at a time; each fills in as its
        // answer comes.
        const queue = rows.filter((row) => row.checkable);
        const lines = new Map(
          rows.map((row, index) => [row.id, list.children[index]?.querySelector('[data-updates]')]),
        );

        await Promise.all(
          Array.from({ length: Math.min(AT_ONCE, queue.length) }, async () => {
            for (let row = queue.shift(); row; row = queue.shift()) {
              const line = lines.get(row.id);

              if (!(line instanceof HTMLElement)) continue;

              line.textContent = 'Checking for updates…';

              try {
                const updates = await getUpdates(repository.id, row.id, { fresh: true });

                if (!isCurrent()) return;

                line.textContent =
                  updates === null
                    ? 'It cannot be checked right now.'
                    : `Updates: ${countsSentence(countUpdates(updates))}`;
              } catch (cause) {
                line.textContent = describeError(cause);
              }
            }
          }),
        );
      } catch (cause) {
        if (!isCurrent()) return;

        section.hidden = false;
        sayError(error, cause);
      }
    },
  };
}

export function createActivity(root: HTMLElement): Section {
  const slot = required<HTMLElement>(root, '[data-activity-slot]');

  return {
    clear() {
      slot.replaceChildren();
      slot.hidden = true;
    },

    async load(repository, isCurrent, roster) {
      const log = cloneRoot(root, '[data-activity-log-template]');

      try {
        await renderActivityLog(
          log,
          repository,
          knownNames({ tenant: repository, campaigns: [], roster, players: [] }),
        );

        if (!isCurrent()) return;

        slot.replaceChildren(log);
        slot.hidden = false;
      } catch (cause) {
        if (!isCurrent()) return;

        const line = document.createElement('p');

        line.className = 'error-text';
        line.textContent = describeError(cause);
        slot.replaceChildren(line);
        slot.hidden = false;
      }
    },
  };
}
