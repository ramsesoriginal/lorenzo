// Private or public, on a repository's Overview (RFC 0036 §4 T7, RFC 0038 §7, ADR 0290): the card an
// Owner has, and the dialogs that say what making it public or private will do before it does it.
// The words and the checks are lib/visibility.ts's. Nothing is asked of the API to change anything
// until a dialog's last button; what a dialog says is read fresh when it opens, and again after a
// refusal, since a refusal means something changed.

import { ApiError } from '../../lib/apiError';
import {
  flipCheck,
  getReleasePreview,
  getRepositoryProfile,
  makePrivate,
  makePublic,
} from '../../lib/repositories';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { FlipCheckOut, TenantSummaryOut } from '../../lib/types';
import {
  type Blocker,
  changedUnderTheDialog,
  MAKE_PRIVATE_CONFIRM,
  MAKE_PUBLIC_CONFIRM,
  MAKE_PUBLIC_DONE,
  type MakePublicForm,
  madePrivateDone,
  makePrivateLines,
  makePrivateProblem,
  makePrivateQuery,
  makePrivateTitle,
  makePublicBody,
  makePublicLines,
  makePublicProblem,
  makePublicTitle,
  makePublicWarnings,
  PREVIEW_CHOICES,
  PREVIEW_DEFAULT,
  PREVIEW_LEGEND,
  PRIVATE_BLOCKERS_TITLE,
  type PreviewChoice,
  PUBLIC_BLOCKERS_TITLE,
  privateAcknowledgement,
  privateBlockers,
  publicBlockers,
  SUMMARY_HELP,
  summaryCount,
  VISIBILITY_HEADING,
  visibilityCard,
} from '../../lib/visibility';
import { createComposer } from './composer';

const required = requiredIn('Repository');

export type VisibilityControls = {
  clear(): void;
  // Reads what a switch would run into and shows the card, for an Owner where there is a switch.
  paint(repository: TenantSummaryOut): Promise<void>;
};

type Mode = 'public' | 'private';

// `root` is the <Repository /> article. `onDone` is called once a switch was made, for the page to
// read the repository again.
export function createVisibilityControls(
  root: HTMLElement,
  onDone: () => void,
): VisibilityControls {
  const card = required<HTMLElement>(root, '[data-visibility]');
  const state = required<HTMLElement>(card, '[data-visibility-state]');
  const explanation = required<HTMLElement>(card, '[data-visibility-explanation]');
  const button = required<HTMLButtonElement>(card, '[data-visibility-button]');
  const status = required<HTMLElement>(card, '[data-visibility-status]');

  const dialog = required<HTMLDialogElement>(root, '[data-visibility-dialog]');
  const form = required<HTMLFormElement>(dialog, '[data-visibility-form]');
  const title = required<HTMLElement>(dialog, '[data-vis-title]');
  const blockersBox = required<HTMLElement>(dialog, '[data-vis-blockers]');
  const blockersTitle = required<HTMLElement>(dialog, '[data-vis-blockers-title]');
  const blockerList = required<HTMLElement>(dialog, '[data-vis-blocker-list]');
  const warningsBox = required<HTMLElement>(dialog, '[data-vis-warnings]');
  const warningList = required<HTMLElement>(dialog, '[data-vis-warning-list]');
  const lines = required<HTMLElement>(dialog, '[data-vis-lines]');
  const publicFields = required<HTMLElement>(dialog, '[data-vis-public]');
  const summary = required<HTMLTextAreaElement>(dialog, '[data-vis-summary]');
  const summaryCountLine = required<HTMLElement>(dialog, '[data-vis-summary-count]');
  const previewFieldset = required<HTMLElement>(dialog, '[data-vis-preview]');
  const ackRow = required<HTMLElement>(dialog, '[data-vis-ack-row]');
  const ack = required<HTMLInputElement>(dialog, '[data-vis-ack]');
  const ackText = required<HTMLElement>(dialog, '[data-vis-ack-text]');
  const error = required<HTMLElement>(dialog, '[data-vis-error]');
  const cancel = required<HTMLButtonElement>(dialog, '[data-vis-cancel]');
  const confirm = required<HTMLButtonElement>(dialog, '[data-vis-confirm]');
  const composer = createComposer(dialog);

  required<HTMLElement>(card, '[data-visibility-heading]').textContent = VISIBILITY_HEADING;
  required<HTMLElement>(dialog, '[data-vis-summary-help]').textContent = SUMMARY_HELP;
  required<HTMLElement>(dialog, '[data-vis-preview-legend]').textContent = PREVIEW_LEGEND;

  // The three plain-language choices of what people may look at before they copy it.
  const radios: Partial<Record<PreviewChoice, HTMLInputElement>> = {};

  for (const choice of PREVIEW_CHOICES) {
    const row = document.createElement('label');
    const radio = document.createElement('input');

    row.className = 'field-row';
    radio.type = 'radio';
    radio.name = 'visibility-preview';
    radio.value = choice.value;
    radio.dataset.visPreviewChoice = choice.value;
    row.append(radio, choice.label);
    previewFieldset.append(row);
    radios[choice.value] = radio;
  }

  let shown: TenantSummaryOut | null = null;
  let mode: Mode = 'public';
  // What the dialog was last read to say: what it decides is sent against.
  let check: FlipCheckOut | null = null;
  let pending: string | null = null;

  function item(text: string): HTMLElement {
    const li = document.createElement('li');

    li.textContent = text;

    return li;
  }

  function blockerItem(blocker: Blocker): HTMLElement {
    const li = item(blocker.text);

    if (blocker.link) {
      const link = document.createElement('a');

      link.className = 'shelf-link';
      link.href = blocker.link.href;
      link.textContent = blocker.link.label;
      li.append(' ', link);
    }

    return li;
  }

  function chosenPreview(): PreviewChoice {
    for (const choice of PREVIEW_CHOICES) if (radios[choice.value]?.checked) return choice.value;

    return PREVIEW_DEFAULT;
  }

  function currentForm(): MakePublicForm {
    return { ...composer.form(), summary: summary.value, preview: chosenPreview() };
  }

  // What stands in the way, and what the dialog says, from a read of the API. What was typed stays.
  function paintDialog(read: FlipCheckOut, name: string): void {
    check = read;

    const blockers = mode === 'public' ? publicBlockers(read) : privateBlockers(read);

    blockersTitle.textContent = mode === 'public' ? PUBLIC_BLOCKERS_TITLE : PRIVATE_BLOCKERS_TITLE;
    blockerList.replaceChildren(...blockers.map(blockerItem));
    blockersBox.hidden = blockers.length === 0;

    if (mode === 'public') {
      title.textContent = makePublicTitle(name);
      lines.replaceChildren(...makePublicLines(read, name).map(item));
      warningList.replaceChildren(...makePublicWarnings().map(item));
      warningsBox.hidden = false;
      publicFields.hidden = blockers.length > 0;
      ackRow.hidden = true;
      confirm.textContent = MAKE_PUBLIC_CONFIRM;
      confirm.className = 'btn btn-primary';
    } else {
      const acknowledgement = privateAcknowledgement(read);

      title.textContent = makePrivateTitle(name);
      lines.replaceChildren(...(blockers.length > 0 ? [] : makePrivateLines(read)).map(item));
      warningList.replaceChildren();
      warningsBox.hidden = true;
      publicFields.hidden = true;
      ackText.textContent = acknowledgement ?? '';
      ackRow.hidden = blockers.length > 0 || acknowledgement === null;
      confirm.textContent = MAKE_PRIVATE_CONFIRM;
      confirm.className = 'btn btn-danger';
    }

    confirm.disabled = blockers.length > 0;
  }

  async function open(next: Mode): Promise<void> {
    const repository = shown;

    if (!repository) return;

    mode = next;
    button.disabled = true;
    say(status, 'Checking…');

    try {
      // Read now, so that what the dialog says is what is true when it is shown.
      const [read, profile, preview] = await Promise.all([
        flipCheck(repository.id, { fresh: true }),
        next === 'public' ? getRepositoryProfile(repository.id, { fresh: true }) : null,
        next === 'public' ? getReleasePreview(repository.id, { fresh: true }) : null,
      ]);

      if (shown !== repository) return;

      if ((next === 'public') === (read.visibility === 'public')) {
        // Somebody else already did it: say so, and show the card as it is now.
        say(status, next === 'public' ? 'It is already public.' : 'It is already private.');
        await paint(repository);

        return;
      }

      error.hidden = true;
      ack.checked = false;

      if (profile && preview) {
        summary.value = profile.summary;
        summaryCountLine.textContent = summaryCount(summary.value);
        for (const choice of PREVIEW_CHOICES) {
          const radio = radios[choice.value];

          // The Owner's earlier choice is kept, `showcase` where there is none (RFC 0038 §5).
          if (radio) radio.checked = choice.value === (profile.preview ?? PREVIEW_DEFAULT);
        }
        composer.show(preview);
        composer.element.hidden = false;
      }

      paintDialog(read, repository.name);
      say(status, '');
      dialog.showModal();
      // Making it public starts at its first field, so the dialog opens at its top; anything else at
      // Cancel.
      (mode === 'public' && !publicFields.hidden ? summary : cancel).focus();
    } catch (cause) {
      sayError(status, cause);
    } finally {
      button.disabled = false;
    }
  }

  // After a refusal that means something changed (a repository it is built on went private, a
  // library copied it), the dialog says what is true now and stays open.
  async function reread(repository: TenantSummaryOut): Promise<void> {
    try {
      paintDialog(await flipCheck(repository.id, { fresh: true }), repository.name);
      ack.checked = false;
    } catch {
      // The refusal is already shown; a second failure adds nothing to say.
    }
  }

  button.addEventListener('click', () => {
    if (check) void open(check.visibility === 'public' ? 'private' : 'public');
  });
  cancel.addEventListener('click', () => dialog.close());
  summary.addEventListener('input', () => {
    summaryCountLine.textContent = summaryCount(summary.value);
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const repository = shown;
    const read = check;

    if (!repository || !read) return;

    const problem =
      mode === 'public'
        ? makePublicProblem(currentForm(), composer.hits())
        : makePrivateProblem(read, ack.checked);

    if (problem) {
      sayError(error, new Error(problem));
      return;
    }

    confirm.disabled = true;
    error.hidden = true;

    void (async () => {
      try {
        if (mode === 'public') {
          await makePublic(repository.id, makePublicBody(currentForm(), composer.hits()));
          pending = MAKE_PUBLIC_DONE;
        } else {
          const done = await makePrivate(repository.id, makePrivateQuery(read, ack.checked));

          pending = madePrivateDone(done.revoked);
        }

        dialog.close();
        onDone();
      } catch (cause) {
        confirm.disabled = false;

        // What the preview did not see: the API names the rows, and they have to be acknowledged.
        if (mode === 'public' && composer.refused(cause)) {
          sayError(error, cause);

          return;
        }

        sayError(error, cause);

        if (cause instanceof ApiError && changedUnderTheDialog(cause.problemType)) {
          await reread(repository);
        }
      }
    })();
  });

  async function paint(repository: TenantSummaryOut): Promise<void> {
    shown = repository;

    // Only an Owner has the switch, and nothing is asked of the API for anyone else.
    if (repository.role !== 'owner') {
      card.hidden = true;

      return;
    }

    let read: FlipCheckOut;

    try {
      read = await flipCheck(repository.id, { fresh: true });
    } catch {
      // A switch that cannot be read is not offered; the rest of the Overview does not depend on it.
      card.hidden = true;

      return;
    }

    if (shown !== repository) return;

    check = read;

    const content = visibilityCard(read, repository.role);

    card.hidden = content === null;

    if (content === null) return;

    state.className = content.visibility === 'public' ? 'pill pill-success' : 'pill';
    state.textContent = content.label;
    explanation.textContent = content.sentence;
    button.textContent = content.button;

    if (pending) {
      say(status, pending);
      pending = null;
    }
  }

  return {
    clear() {
      shown = null;
      check = null;
      card.hidden = true;
      say(status, '');
    },

    paint,
  };
}
