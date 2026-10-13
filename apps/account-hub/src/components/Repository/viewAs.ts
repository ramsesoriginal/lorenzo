// "See it as a subscriber" on a repository's Overview (ADR 0261): makes, opens, resets and removes
// the owner's Test library. The decisions are lib/subscriber.ts's; this binds them to the page.

import { describeError } from '../../lib/describeError';
import { copyRepository, inviteLibrary, listSubscribers } from '../../lib/repositories';
import { shelfHref } from '../../lib/shelf';
import { say, sayError } from '../../lib/statusLine';
import {
  canViewAsSubscriber,
  findTestLibrary,
  leftBehind,
  makeTestLibrary,
  REMOVE_CONFIRMATION,
  REMOVED,
  RESET_CONFIRMATION,
  RESET_DONE,
  SUBSCRIBER_EXPLANATION,
  SUBSCRIBER_HEADING,
  subscriberUnavailable,
  type TestLibrary,
  TestLibraryError,
  testLibraryLine,
} from '../../lib/subscriber';
import { requiredIn } from '../../lib/template';
import { createTenant, deleteTenant, listMyTenants } from '../../lib/tenants';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Repository');

export type ViewAs = {
  clear(): void;
  paint(repository: TenantSummaryOut, published: boolean): Promise<void>;
};

// `root` is the <Repository /> article.
export function createViewAs(root: HTMLElement, mayCreate: boolean): ViewAs {
  const buttons = required<HTMLElement>(root, '[data-subscriber-buttons]');
  const open = required<HTMLButtonElement>(root, '[data-view-as]');
  const reset = required<HTMLButtonElement>(root, '[data-reset-test]');
  const remove = required<HTMLButtonElement>(root, '[data-remove-test]');
  const line = required<HTMLElement>(root, '[data-subscriber-line]');
  const unavailable = required<HTMLElement>(root, '[data-subscriber-unavailable]');
  const status = required<HTMLElement>(root, '[data-subscriber-status]');

  required<HTMLElement>(root, '[data-subscriber-heading]').textContent = SUBSCRIBER_HEADING;
  required<HTMLElement>(root, '[data-subscriber-explanation]').textContent = SUBSCRIBER_EXPLANATION;

  let shown: TenantSummaryOut | null = null;
  let published = false;

  async function current(repository: TenantSummaryOut): Promise<TestLibrary | null> {
    const [subscribers, mine] = await Promise.all([
      listSubscribers(repository.id, { fresh: true }),
      listMyTenants('play'),
    ]);

    return findTestLibrary(repository.name, subscribers, mine.items);
  }

  function busy(on: boolean): void {
    for (const button of [open, reset, remove]) button.disabled = on;
  }

  async function repaint(repository: TenantSummaryOut): Promise<void> {
    const library = await current(repository);

    if (shown !== repository) return;

    line.textContent = testLibraryLine(library);
    line.hidden = false;
    reset.hidden = !library?.copied;
    remove.hidden = library === null;
  }

  open.addEventListener('click', async () => {
    const repository = shown;

    if (!repository) return;

    busy(true);
    say(status, 'Setting up the Test library…');

    try {
      const library =
        (await current(repository)) ??
        (await makeTestLibrary(
          {
            create: (name) => createTenant({ name }),
            invite: inviteLibrary,
            remove: deleteTenant,
          },
          repository,
        ));

      window.location.assign(shelfHref(library.slug, repository.id));
    } catch (cause) {
      busy(false);

      if (cause instanceof TestLibraryError) {
        say(
          status,
          `${describeError(cause.cause)}${cause.cleanedUp ? '' : ` ${leftBehind(cause.libraryName)}`}`,
          true,
        );
      } else {
        sayError(status, cause);
      }
    }
  });

  reset.addEventListener('click', async () => {
    const repository = shown;

    if (!repository || !window.confirm(RESET_CONFIRMATION)) return;

    busy(true);
    say(status, 'Resetting…');

    try {
      const library = await current(repository);

      if (!library) throw new Error('There is no Test library to reset.');

      await copyRepository(library.id, repository.id, { again: 'purge' });
      say(status, RESET_DONE);
      await repaint(repository);
    } catch (cause) {
      sayError(status, cause);
    } finally {
      busy(false);
    }
  });

  remove.addEventListener('click', async () => {
    const repository = shown;

    if (!repository || !window.confirm(REMOVE_CONFIRMATION)) return;

    busy(true);
    say(status, 'Removing…');

    try {
      const library = await current(repository);

      if (library) await deleteTenant(library.id);

      say(status, REMOVED);
      await repaint(repository);
    } catch (cause) {
      sayError(status, cause);
    } finally {
      busy(false);
    }
  });

  return {
    clear() {
      shown = null;
      buttons.hidden = true;
      line.hidden = true;
      unavailable.hidden = true;
      say(status, '');
    },

    async paint(repository, isPublished) {
      shown = repository;
      published = isPublished;

      const why = subscriberUnavailable(repository.role, mayCreate, published);

      unavailable.textContent = why ?? '';
      unavailable.hidden = why === null;
      buttons.hidden = !canViewAsSubscriber(repository.role, mayCreate, published);
      reset.hidden = true;
      remove.hidden = true;

      if (buttons.hidden) return;

      try {
        await repaint(repository);
      } catch (cause) {
        if (shown === repository) sayError(status, cause);
      }
    },
  };
}
