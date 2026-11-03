// Retiring a repository, on its Overview (RFC 0038 §7, ADR 0384): the notice every member reads
// while it is retired, and the Owner's card to retire it, with a dialog that says what it will do
// before it does it, and to bring it back. The words are lib/retiring.ts's. What is shown is read
// fresh, since the repository's other Owners can change it at any moment, and shows nothing where it
// cannot be read: the rest of the Overview does not depend on it.

import { ApiError } from '../../lib/apiError';
import {
  bringRepositoryBack,
  getRepositoryProfile,
  getSubscribersSummary,
  retireRepository,
} from '../../lib/repositories';
import {
  BRING_BACK_BUTTON,
  BRING_BACK_NOTE,
  messageCount,
  messageLine,
  messageProblem,
  RETIRE_BUTTON,
  RETIRE_CONFIRM,
  RETIRE_EXPLANATION,
  RETIRE_HEADING,
  RETIRE_MESSAGE_HELP,
  RETIRE_MESSAGE_LABEL,
  RETIRED_PILL,
  RETIRED_STATE,
  retireBody,
  retireCard,
  retireDialogLines,
  retireDialogTitle,
  retiredNotice,
} from '../../lib/retiring';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { DeprecatedOut, TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Repository');

export type RetiredControls = {
  clear(): void;
  paint(repository: TenantSummaryOut): Promise<void>;
};

// `root` is the <Repository /> article. `onDone` is called once it was retired or brought back, for
// the page to read the repository again.
export function createRetiredControls(root: HTMLElement, onDone: () => void): RetiredControls {
  const notice = required<HTMLElement>(root, '[data-retired]');
  const noticePill = required<HTMLElement>(notice, '[data-retired-pill]');
  const noticeTitle = required<HTMLElement>(notice, '[data-retired-title]');
  const noticeEffect = required<HTMLElement>(notice, '[data-retired-effect]');
  const noticeMessage = required<HTMLElement>(notice, '[data-retired-message]');

  const card = required<HTMLElement>(root, '[data-retire]');
  const formBox = required<HTMLElement>(card, '[data-retire-form-box]');
  const message = required<HTMLTextAreaElement>(card, '[data-retire-message]');
  const count = required<HTMLElement>(card, '[data-retire-count]');
  const retire = required<HTMLButtonElement>(card, '[data-retire-button]');
  const retiredBox = required<HTMLElement>(card, '[data-retire-retired]');
  const savedMessage = required<HTMLElement>(card, '[data-retire-saved]');
  const since = required<HTMLElement>(card, '[data-retire-since]');
  const bringBack = required<HTMLButtonElement>(card, '[data-bring-back]');
  const status = required<HTMLElement>(card, '[data-retire-status]');

  const dialog = required<HTMLDialogElement>(root, '[data-retire-dialog]');
  const form = required<HTMLFormElement>(dialog, '[data-retire-form]');
  const title = required<HTMLElement>(dialog, '[data-retire-title]');
  const lines = required<HTMLElement>(dialog, '[data-retire-lines]');
  const dialogMessage = required<HTMLElement>(dialog, '[data-retire-dialog-message]');
  const error = required<HTMLElement>(dialog, '[data-retire-error]');
  const cancel = required<HTMLButtonElement>(dialog, '[data-retire-cancel]');
  const confirm = required<HTMLButtonElement>(dialog, '[data-retire-confirm]');

  required<HTMLElement>(card, '[data-retire-heading]').textContent = RETIRE_HEADING;
  required<HTMLElement>(card, '[data-retire-explanation]').textContent = RETIRE_EXPLANATION;
  required<HTMLElement>(card, '[data-retire-label]').textContent = RETIRE_MESSAGE_LABEL;
  required<HTMLElement>(card, '[data-retire-help]').textContent = RETIRE_MESSAGE_HELP;
  required<HTMLElement>(card, '[data-retire-pill]').textContent = RETIRED_PILL;
  required<HTMLElement>(card, '[data-retire-state]').textContent = RETIRED_STATE;
  required<HTMLElement>(card, '[data-bring-back-note]').textContent = BRING_BACK_NOTE;
  retire.textContent = RETIRE_BUTTON;
  bringBack.textContent = BRING_BACK_BUTTON;
  confirm.textContent = RETIRE_CONFIRM;
  count.textContent = messageCount('');

  let shown: TenantSummaryOut | null = null;
  // What it was last read to be: set while it is retired.
  let current: DeprecatedOut | null = null;

  function paintNotice(deprecated: DeprecatedOut | null): void {
    const content = retiredNotice(deprecated);

    notice.hidden = content === null;

    if (!content) return;

    noticePill.textContent = content.pill;
    noticeTitle.textContent = content.title;
    noticeEffect.textContent = content.effect;
    noticeMessage.textContent = content.message ?? '';
    noticeMessage.hidden = content.message === null;
  }

  function paintCard(deprecated: DeprecatedOut | null): void {
    const content = retireCard(deprecated);

    formBox.hidden = content.retired;
    retiredBox.hidden = !content.retired;
    savedMessage.textContent = messageLine(content.message) ?? '';
    savedMessage.hidden = content.message === null;
    since.textContent = content.since ?? '';
  }

  message.addEventListener('input', () => {
    count.textContent = messageCount(message.value);
  });

  retire.addEventListener('click', () => {
    const repository = shown;

    if (!repository) return;

    const problem = messageProblem(message.value);

    if (problem) {
      sayError(status, new Error(problem));

      return;
    }

    void (async () => {
      retire.disabled = true;
      say(status, 'Checking…');

      try {
        // Read now, so that the number the dialog says is the number it will tell.
        const counted = await getSubscribersSummary(repository.id, { fresh: true });

        if (shown !== repository) return;

        title.textContent = retireDialogTitle(repository.name);
        lines.replaceChildren(
          ...retireDialogLines(counted.named + counted.public_copies).map((text) => {
            const li = document.createElement('li');

            li.textContent = text;

            return li;
          }),
        );

        const words = messageLine(retireBody(message.value).message ?? null);

        dialogMessage.textContent = words ?? '';
        dialogMessage.hidden = words === null;
        error.hidden = true;
        confirm.disabled = false;
        say(status, '');
        dialog.showModal();
        cancel.focus();
      } catch (cause) {
        sayError(status, cause);
      } finally {
        retire.disabled = false;
      }
    })();
  });

  cancel.addEventListener('click', () => dialog.close());

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const repository = shown;

    if (!repository) return;

    confirm.disabled = true;
    error.hidden = true;

    void (async () => {
      try {
        await retireRepository(repository.id, retireBody(message.value));
        dialog.close();
        message.value = '';
        count.textContent = messageCount('');
        onDone();
      } catch (cause) {
        confirm.disabled = false;
        sayError(error, cause);

        if (cause instanceof ApiError) {
          // Somebody else changed it meanwhile: the card says what is true now.
          void paint(repository);
        }
      }
    })();
  });

  bringBack.addEventListener('click', () => {
    const repository = shown;

    if (!repository) return;

    void (async () => {
      bringBack.disabled = true;
      say(status, 'Bringing it back…');

      try {
        await bringRepositoryBack(repository.id);
        say(status, '');
        onDone();
      } catch (cause) {
        sayError(status, cause);
      } finally {
        bringBack.disabled = false;
      }
    })();
  });

  async function paint(repository: TenantSummaryOut): Promise<void> {
    shown = repository;

    try {
      const profile = await getRepositoryProfile(repository.id, { fresh: true });

      if (shown !== repository) return;

      current = profile.deprecated ?? null;
    } catch {
      // A state that cannot be read is not shown; the Overview does not depend on it.
      if (shown === repository) {
        notice.hidden = true;
        card.hidden = true;
      }

      return;
    }

    paintNotice(current);
    // Only an Owner retires it or brings it back; everyone else reads the notice.
    card.hidden = repository.role !== 'owner';

    if (repository.role === 'owner') paintCard(current);
  }

  return {
    clear() {
      shown = null;
      current = null;
      notice.hidden = true;
      card.hidden = true;
      say(status, '');
    },

    paint,
  };
}
