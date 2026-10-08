// Publishing and unpublishing a repository from Studio's Overview (ADR 0206): the buttons an Owner
// has, and the dialog that says what each will do before it does it. Nothing is asked of the API to
// change anything until the dialog's last button; what the dialog says is read fresh when it opens.

import { dialogFor, OWNER_ONLY_NOTE, type PublishMode, publishFacts } from '../../lib/publishing';
import {
  listLibraryRepositories,
  listSubscribers,
  publishRepository,
  unpublishRepository,
} from '../../lib/repositories';
import { say, sayError } from '../../lib/statusLine';
import { canChangePeople } from '../../lib/studio';
import { requiredIn } from '../../lib/template';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Repository');

export type PublishControls = {
  clear(): void;
  // Shows what this person can do about a repository in the state it is in.
  paint(repository: TenantSummaryOut, published: boolean): void;
  // A message to show the next time the controls are painted (after what was done).
  say(message: string): void;
};

// `root` is the <Repository /> article. `onDone` is called once a publish or an unpublish was made,
// for the page to read the repository again.
export function createPublishControls(root: HTMLElement, onDone: () => void): PublishControls {
  const buttons = required<HTMLElement>(root, '[data-publish-buttons]');
  const publish = required<HTMLButtonElement>(root, '[data-publish]');
  const announce = required<HTMLButtonElement>(root, '[data-announce]');
  const unpublish = required<HTMLButtonElement>(root, '[data-unpublish]');
  const ownerOnly = required<HTMLElement>(root, '[data-owner-only]');
  const status = required<HTMLElement>(root, '[data-publish-status]');
  const dialog = required<HTMLDialogElement>(root, '[data-publish-dialog]');
  const form = required<HTMLFormElement>(dialog, '[data-publish-form]');
  const title = required<HTMLElement>(dialog, '[data-dialog-title]');
  const lines = required<HTMLElement>(dialog, '[data-dialog-lines]');
  const warnings = required<HTMLElement>(dialog, '[data-dialog-warnings]');
  const warningList = required<HTMLElement>(dialog, '[data-dialog-warning-list]');
  const error = required<HTMLElement>(dialog, '[data-dialog-error]');
  const cancel = required<HTMLButtonElement>(dialog, '[data-dialog-cancel]');
  const confirm = required<HTMLButtonElement>(dialog, '[data-dialog-confirm]');

  let shown: TenantSummaryOut | null = null;
  let mode: PublishMode = 'publish';
  let pending: string | null = null;

  function item(text: string): HTMLElement {
    const li = document.createElement('li');

    li.textContent = text;

    return li;
  }

  async function open(next: PublishMode): Promise<void> {
    const repository = shown;

    if (!repository) return;

    mode = next;
    say(status, 'Checking…');

    try {
      // Read now, so that what the dialog says is what is true when it is shown.
      const [subscribers, copiedFrom] = await Promise.all([
        listSubscribers(repository.id, { fresh: true }),
        listLibraryRepositories(repository.id, { fresh: true }),
      ]);
      const content = dialogFor(next, repository.name, publishFacts(subscribers, copiedFrom));

      title.textContent = content.title;
      lines.replaceChildren(...content.lines.map(item));
      warningList.replaceChildren(...content.warnings.map(item));
      warnings.hidden = content.warnings.length === 0;
      confirm.textContent = content.confirm;
      confirm.className = next === 'unpublish' ? 'btn btn-danger' : 'btn btn-primary';
      error.hidden = true;
      confirm.disabled = false;
      say(status, '');
      dialog.showModal();
    } catch (cause) {
      sayError(status, cause);
    }
  }

  publish.addEventListener('click', () => void open('publish'));
  announce.addEventListener('click', () => void open('announce'));
  unpublish.addEventListener('click', () => void open('unpublish'));
  cancel.addEventListener('click', () => dialog.close());

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const repository = shown;

    if (!repository) return;

    confirm.disabled = true;
    error.hidden = true;

    void (async () => {
      try {
        if (mode === 'unpublish') await unpublishRepository(repository.id);
        else await publishRepository(repository.id);

        pending =
          mode === 'unpublish'
            ? 'Unpublished. It is a draft again.'
            : mode === 'publish'
              ? 'Published.'
              : 'Libraries were told.';
        dialog.close();
        onDone();
      } catch (cause) {
        confirm.disabled = false;
        sayError(error, cause);
      }
    })();
  });

  return {
    clear() {
      shown = null;
      buttons.hidden = true;
      publish.hidden = true;
      announce.hidden = true;
      unpublish.hidden = true;
      ownerOnly.hidden = true;
      say(status, '');
    },

    paint(repository, published) {
      shown = repository;

      const owner = canChangePeople(repository.role);

      buttons.hidden = !owner;
      publish.hidden = !owner || published;
      announce.hidden = !owner || !published;
      unpublish.hidden = !owner || !published;
      ownerOnly.textContent = owner ? '' : OWNER_ONLY_NOTE;
      ownerOnly.hidden = owner;

      if (pending) {
        say(status, pending);
        pending = null;
      }
    },

    say(message) {
      pending = message;
    },
  };
}
