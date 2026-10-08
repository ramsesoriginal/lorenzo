// Publishing and unpublishing a repository from Studio's Overview (ADR 0206, 0209): the buttons an
// Owner has, and the dialog that says what each will do before it does it. A publish is a release:
// the dialog is the composer, with a label, notes and a breaking flag, and what the release will
// contain, read from the API's preview. Nothing is asked of the API to change anything until the
// dialog's last button; what the dialog says is read fresh when it opens.

import { ApiError } from '../../lib/apiError';
import { dialogFor, OWNER_ONLY_NOTE, type PublishMode, publishFacts } from '../../lib/publishing';
import {
  ACKNOWLEDGE_TEXT,
  breakingLines,
  type ComposerForm,
  composerProblem,
  contentLines,
  defaultLabel,
  descriptionsHint,
  LABEL_MAX,
  matchesSentence,
  publishBody,
  TEXT_NOT_TRACKED,
  WARNING_TITLE,
  warningLines,
} from '../../lib/releases';
import {
  getReleasePreview,
  listLibraryRepositories,
  listSubscribers,
  publishRepository,
  unpublishRepository,
} from '../../lib/repositories';
import { say, sayError } from '../../lib/statusLine';
import { canChangePeople } from '../../lib/studio';
import { requiredIn } from '../../lib/template';
import type { BreakingRowOut, TenantSummaryOut } from '../../lib/types';

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

  // The composer: what a release is called and says, and what it will contain.
  const composer = required<HTMLElement>(dialog, '[data-composer]');
  const label = required<HTMLInputElement>(dialog, '[data-composer-label]');
  const labelHelp = required<HTMLElement>(dialog, '[data-label-help]');
  const notes = required<HTMLTextAreaElement>(dialog, '[data-composer-notes]');
  const breaking = required<HTMLInputElement>(dialog, '[data-composer-breaking]');
  const matches = required<HTMLElement>(dialog, '[data-matches-line]');
  const contents = required<HTMLElement>(dialog, '[data-content-lines]');
  const hint = required<HTMLElement>(dialog, '[data-hint]');
  const notTracked = required<HTMLElement>(dialog, '[data-not-tracked]');
  const breaksBox = required<HTMLElement>(dialog, '[data-breaks-box]');
  const breaksLines = required<HTMLElement>(dialog, '[data-breaks-lines]');
  const warnsBox = required<HTMLElement>(dialog, '[data-warns-box]');
  const warnsLines = required<HTMLElement>(dialog, '[data-warns-lines]');
  const acknowledge = required<HTMLInputElement>(dialog, '[data-composer-ack]');

  required<HTMLElement>(dialog, '[data-ack-text]').textContent = ACKNOWLEDGE_TEXT;
  notTracked.textContent = TEXT_NOT_TRACKED;
  required<HTMLElement>(dialog, '[data-warns-title]').textContent = WARNING_TITLE;
  label.maxLength = LABEL_MAX;

  let shown: TenantSummaryOut | null = null;
  let mode: PublishMode = 'publish';
  let pending: string | null = null;
  // What the release would break, as the preview or the API's refusal says.
  let hits: BreakingRowOut[] = [];

  function item(text: string): HTMLElement {
    const li = document.createElement('li');

    li.textContent = text;

    return li;
  }

  function showHits(rows: BreakingRowOut[]): void {
    hits = rows;
    breaksLines.replaceChildren(...breakingLines(rows).map(item));
    breaksBox.hidden = rows.length === 0;
  }

  // What the release only says: said, never refused, nothing to acknowledge.
  function showWarnings(rows: BreakingRowOut[]): void {
    warnsLines.replaceChildren(...warningLines(rows).map(item));
    warnsBox.hidden = rows.length === 0;
  }

  function currentForm(): ComposerForm {
    return {
      label: label.value,
      notes: notes.value,
      breaking: breaking.checked,
      acknowledged: acknowledge.checked,
    };
  }

  async function open(next: PublishMode): Promise<void> {
    const repository = shown;

    if (!repository) return;

    mode = next;
    say(status, 'Checking…');

    try {
      // Read now, so that what the dialog says is what is true when it is shown.
      const [subscribers, copiedFrom, preview] = await Promise.all([
        listSubscribers(repository.id, { fresh: true }),
        listLibraryRepositories(repository.id, { fresh: true }),
        next === 'unpublish' ? null : getReleasePreview(repository.id, { fresh: true }),
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

      composer.hidden = preview === null;

      if (preview) {
        label.value = '';
        notes.value = '';
        breaking.checked = false;
        acknowledge.checked = false;
        labelHelp.textContent = `Free text, such as 1.3 or Spring errata. Left empty, it is ${defaultLabel(preview)}.`;
        matches.textContent = matchesSentence(preview);
        contents.replaceChildren(...contentLines(preview).map(item));

        const description = descriptionsHint(preview);

        hint.textContent = description ?? '';
        hint.hidden = description === null;
        showHits(preview.breaking);
        showWarnings(preview.warnings);
      }

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

    const problem = mode === 'unpublish' ? null : composerProblem(currentForm(), hits);

    if (problem) {
      sayError(error, new Error(problem));
      return;
    }

    confirm.disabled = true;
    error.hidden = true;

    void (async () => {
      try {
        if (mode === 'unpublish') await unpublishRepository(repository.id);
        else await publishRepository(repository.id, publishBody(currentForm(), hits));

        pending = mode === 'unpublish' ? 'Unpublished. It is a draft again.' : 'Release published.';
        dialog.close();
        onDone();
      } catch (cause) {
        confirm.disabled = false;

        // What the preview did not see: the API names the rows, and they have to be acknowledged.
        if (cause instanceof ApiError && cause.problemType === 'release-has-breaking-changes') {
          const rows = cause.problem.breaking_rows;

          showHits(Array.isArray(rows) ? (rows as BreakingRowOut[]) : []);
          acknowledge.checked = false;
        }

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
