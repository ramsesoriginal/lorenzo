// Private or public, on a repository's Overview (RFC 0036 §4 T7, RFC 0038 §7, ADR 0290): the card an
// Owner has, and the dialogs that say what making it public or private will do before it does it.
// The words and the checks are lib/visibility.ts's. Nothing is asked of the API to change anything
// until a dialog's last button; what a dialog says is read fresh when it opens, and again after a
// refusal, since a refusal means something changed.

import { ApiError } from '../../lib/apiError';
import { storefrontHref } from '../../lib/discover';
import { BUILT_ON_CHOICES_TITLE, type BuiltOnChoice, builtOnChoices } from '../../lib/inclusion';
import {
  flipCheck,
  getReleasePreview,
  getRepositoryProfile,
  makePrivate,
  makeProtected,
  makePublic,
  updateRepositoryProfile,
} from '../../lib/repositories';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { FlipCheckOut, TenantSummaryOut } from '../../lib/types';
import {
  type Blocker,
  changedUnderTheDialog,
  type FlipMode,
  LISTED_PAGE_LINK,
  LISTED_SAVED,
  LISTED_SAVING,
  listedPatch,
  listedSwitch,
  MADE_PROTECTED_FROM_PUBLIC,
  MAKE_PRIVATE_CONFIRM,
  MAKE_PROTECTED_DONE,
  MAKE_PUBLIC_CONFIRM,
  MAKE_PUBLIC_DONE,
  type MakePublicForm,
  madePrivateDone,
  makePrivateLines,
  makePrivateProblem,
  makePrivateQuery,
  makePrivateTitle,
  makeProtectedBody,
  makeProtectedConfirm,
  makeProtectedLines,
  makeProtectedProblem,
  makeProtectedTitle,
  makeProtectedWarnings,
  makePublicBody,
  makePublicLines,
  makePublicProblem,
  makePublicTitle,
  makePublicWarnings,
  PREVIEW_CHOICES,
  PREVIEW_DEFAULT,
  PREVIEW_LEGEND,
  PRIVATE_BLOCKERS_TITLE,
  PROTECTED_BLOCKERS_TITLE,
  type PreviewChoice,
  PUBLIC_BLOCKERS_TITLE,
  privateAcknowledgement,
  privateBlockers,
  protectedAcknowledgement,
  publicBlockers,
  TERMS_LINE,
  VISIBILITY_HEADING,
  type Visibility,
  visibilityCard,
} from '../../lib/visibility';
import { createComposer } from './composer';
import { createInclusionChoice } from './inclusion';
import { bindSummaryField } from './summaryField';

const required = requiredIn('Repository');

export type VisibilityControls = {
  clear(): void;
  // Reads what a switch would run into and shows the card, for an Owner where there is a switch.
  paint(repository: TenantSummaryOut): Promise<void>;
};

type Mode = FlipMode;

// `root` is the <Repository /> article. `onDone` is called once a switch was made, for the page to
// read the repository again.
export function createVisibilityControls(
  root: HTMLElement,
  onDone: () => void,
  // Told what the repository is once the check was read, for what depends on it (a public one is not
  // unpublished, and the readiness list is drawn from the same read, ADR 0385).
  onKnown: (visibility: Visibility, check: FlipCheckOut, repository: TenantSummaryOut) => void,
): VisibilityControls {
  const card = required<HTMLElement>(root, '[data-visibility]');
  const state = required<HTMLElement>(card, '[data-visibility-state]');
  const explanation = required<HTMLElement>(card, '[data-visibility-explanation]');
  const button = required<HTMLButtonElement>(card, '[data-visibility-button]');
  const altButton = required<HTMLButtonElement>(card, '[data-visibility-button-alt]');
  const status = required<HTMLElement>(card, '[data-visibility-status]');
  const note = required<HTMLElement>(card, '[data-visibility-note]');
  const listed = required<HTMLElement>(card, '[data-visibility-listed]');
  const listedInput = required<HTMLInputElement>(card, '[data-visibility-listed-input]');
  const listedLabel = required<HTMLElement>(card, '[data-visibility-listed-label]');
  const listedHelp = required<HTMLElement>(card, '[data-visibility-listed-help]');
  const listedLink = required<HTMLAnchorElement>(card, '[data-visibility-listed-link]');

  const dialog = required<HTMLDialogElement>(root, '[data-visibility-dialog]');
  const form = required<HTMLFormElement>(dialog, '[data-visibility-form]');
  const title = required<HTMLElement>(dialog, '[data-vis-title]');
  const blockersBox = required<HTMLElement>(dialog, '[data-vis-blockers]');
  const blockersTitle = required<HTMLElement>(dialog, '[data-vis-blockers-title]');
  const blockerList = required<HTMLElement>(dialog, '[data-vis-blocker-list]');
  const warningsBox = required<HTMLElement>(dialog, '[data-vis-warnings]');
  const warningList = required<HTMLElement>(dialog, '[data-vis-warning-list]');
  const lines = required<HTMLElement>(dialog, '[data-vis-lines]');
  const builtOnBox = required<HTMLElement>(dialog, '[data-vis-built-on]');
  const builtOnList = required<HTMLElement>(dialog, '[data-vis-built-on-list]');
  const publicFields = required<HTMLElement>(dialog, '[data-vis-public]');
  const termsBox = required<HTMLElement>(dialog, '[data-vis-public-terms]');
  // The same field, bound by the same helper, as the Profile tab's (ADR 0385).
  const summary = bindSummaryField({
    input: required<HTMLTextAreaElement>(dialog, '[data-vis-summary]'),
    help: required<HTMLElement>(dialog, '[data-vis-summary-help]'),
    count: required<HTMLElement>(dialog, '[data-vis-summary-count]'),
  });
  const previewFieldset = required<HTMLElement>(dialog, '[data-vis-preview]');
  const terms = required<HTMLInputElement>(dialog, '[data-vis-terms]');
  const ackRow = required<HTMLElement>(dialog, '[data-vis-ack-row]');
  const ack = required<HTMLInputElement>(dialog, '[data-vis-ack]');
  const ackText = required<HTMLElement>(dialog, '[data-vis-ack-text]');
  const error = required<HTMLElement>(dialog, '[data-vis-error]');
  const cancel = required<HTMLButtonElement>(dialog, '[data-vis-cancel]');
  const confirm = required<HTMLButtonElement>(dialog, '[data-vis-confirm]');
  const composer = createComposer(dialog);

  required<HTMLElement>(card, '[data-visibility-heading]').textContent = VISIBILITY_HEADING;
  required<HTMLElement>(dialog, '[data-vis-built-on-title]').textContent = BUILT_ON_CHOICES_TITLE;
  required<HTMLElement>(dialog, '[data-vis-preview-legend]').textContent = PREVIEW_LEGEND;
  required<HTMLElement>(dialog, '[data-vis-terms-text]').textContent = TERMS_LINE;

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
  // Whether the card's button cannot be pressed at all (the repository is off Discover): the dialog
  // leaves it so when it is done.
  let cardDisabled = false;
  let altDisabled = false;
  // What each of the card's buttons starts.
  let buttonMode: Mode = 'public';
  let altMode: Mode | null = null;

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

  // One repository this one is built on, with the choice of how it is carried (ADR 0431): choosing
  // saves it, and the dialog reads what stands in the way again.
  function builtOnItem(row: BuiltOnChoice, repository: TenantSummaryOut): HTMLElement {
    const li = document.createElement('li');
    const head = document.createElement('div');
    const name = document.createElement('strong');
    const pill = document.createElement('span');

    head.className = 'row';
    name.textContent = row.name;
    pill.className = row.state === 'Public' ? 'pill pill-success' : 'pill';
    pill.textContent = row.state;
    head.append(name, pill);
    li.className = 'stack-tight';
    li.append(
      head,
      createInclusionChoice({
        repositoryId: repository.id,
        sourceId: row.id,
        name: row.name,
        inclusion: row.inclusion,
        offered: row.offered,
        notOffered: row.notOffered,
        note: row.note,
        protected: row.protected,
        public: row.public,
        editable: true,
        onSaved: () => void reread(repository),
      }),
    );

    return li;
  }

  function chosenPreview(): PreviewChoice {
    for (const choice of PREVIEW_CHOICES) if (radios[choice.value]?.checked) return choice.value;

    return PREVIEW_DEFAULT;
  }

  function currentForm(): MakePublicForm {
    return {
      ...composer.form(),
      summary: summary.value(),
      preview: chosenPreview(),
      terms: terms.checked,
    };
  }

  // What stands in the way, and what the dialog says, from a read of the API. What was typed stays.
  function paintDialog(read: FlipCheckOut, name: string): void {
    check = read;

    // Public and protected are both made over what a repository is built on, so both ask the stack
    // rule; private asks what is built on it.
    const blockers = mode === 'private' ? privateBlockers(read) : publicBlockers(read);

    blockersTitle.textContent =
      mode === 'private'
        ? PRIVATE_BLOCKERS_TITLE
        : mode === 'protected'
          ? PROTECTED_BLOCKERS_TITLE
          : PUBLIC_BLOCKERS_TITLE;
    blockerList.replaceChildren(...blockers.map(blockerItem));
    blockersBox.hidden = blockers.length === 0;
    // A release is made with the flip of a private repository, to public or to protected.
    composer.element.hidden = !(
      blockers.length === 0 &&
      (mode === 'public' || (mode === 'protected' && read.visibility === 'private'))
    );
    termsBox.hidden = mode !== 'public' || blockers.length > 0;

    if (mode === 'public' || mode === 'protected') {
      const choices = builtOnChoices(read.built_on);
      const repository = shown;

      builtOnList.replaceChildren(
        ...(repository ? choices.map((row) => builtOnItem(row, repository)) : []),
      );
      builtOnBox.hidden = choices.length === 0 || repository === null;
    }

    if (mode === 'protected') {
      const acknowledgement = protectedAcknowledgement(read);

      title.textContent = makeProtectedTitle(name);
      lines.replaceChildren(...makeProtectedLines(read, name).map(item));
      warningList.replaceChildren(...makeProtectedWarnings().map(item));
      warningsBox.hidden = false;
      publicFields.hidden = true;
      ackText.textContent = acknowledgement ?? '';
      ackRow.hidden = blockers.length > 0 || acknowledgement === null;
      confirm.textContent = makeProtectedConfirm(read.visibility as Visibility);
      confirm.className = 'btn btn-primary';
    } else if (mode === 'public') {
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
      builtOnList.replaceChildren();
      builtOnBox.hidden = true;
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
    altButton.disabled = true;
    say(status, 'Checking…');

    try {
      // Read now, so that what the dialog says is what is true when it is shown. A release is made with
      // the flip of a private repository to public or to protected; only public asks what the
      // repository says of itself.
      const [read, profile, preview] = await Promise.all([
        flipCheck(repository.id, { fresh: true }),
        next === 'public' ? getRepositoryProfile(repository.id, { fresh: true }) : null,
        next !== 'private' ? getReleasePreview(repository.id, { fresh: true }) : null,
      ]);

      if (shown !== repository) return;

      if (read.visibility === next) {
        // Somebody else already did it: say so, and show the card as it is now.
        say(status, `It is already ${next}.`);
        await paint(repository);

        return;
      }

      error.hidden = true;
      ack.checked = false;
      terms.checked = false;

      if (profile) {
        summary.set(profile.summary);
        for (const choice of PREVIEW_CHOICES) {
          const radio = radios[choice.value];

          // The Owner's earlier choice is kept, `showcase` where there is none (RFC 0038 §5).
          if (radio) radio.checked = choice.value === (profile.preview ?? PREVIEW_DEFAULT);
        }
      }

      if (preview) composer.show(preview);

      paintDialog(read, repository.name);
      say(status, '');
      dialog.showModal();
      // Making it public starts at its first field, so the dialog opens at its top; anything else at
      // Cancel.
      (mode === 'public' && !publicFields.hidden ? summary : cancel).focus();
    } catch (cause) {
      sayError(status, cause);
    } finally {
      button.disabled = cardDisabled;
      altButton.disabled = altDisabled;
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

  // Whether Discover lists it: saved at once, as the Profile tab's terms are, since nothing else waits on
  // it. What the page says after is what the API answered.
  listedInput.addEventListener('change', () => {
    const repository = shown;

    if (repository?.role !== 'owner') return;

    const wanted = listedInput.checked;

    listedInput.disabled = true;
    say(status, LISTED_SAVING);

    void (async () => {
      try {
        const profile = await updateRepositoryProfile(repository.id, listedPatch(wanted));

        if (shown !== repository) return;

        listedInput.checked = profile.listed;
        listedHelp.textContent = listedSwitch(profile.listed).help;
        if (check) check = { ...check, listed: profile.listed };
        say(status, LISTED_SAVED);
      } catch (cause) {
        if (shown !== repository) return;

        listedInput.checked = !wanted;
        sayError(status, cause);
      } finally {
        listedInput.disabled = shown !== repository;
      }
    })();
  });

  button.addEventListener('click', () => {
    if (check) void open(buttonMode);
  });
  altButton.addEventListener('click', () => {
    if (check && altMode) void open(altMode);
  });
  cancel.addEventListener('click', () => dialog.close());

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const repository = shown;
    const read = check;

    if (!repository || !read) return;

    const problem =
      mode === 'public'
        ? makePublicProblem(currentForm(), composer.hits())
        : mode === 'protected'
          ? makeProtectedProblem(composer.form(), composer.hits(), read, ack.checked)
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
        } else if (mode === 'protected') {
          await makeProtected(
            repository.id,
            makeProtectedBody(composer.form(), composer.hits(), read, ack.checked),
          );
          pending = read.visibility === 'public' ? MADE_PROTECTED_FROM_PUBLIC : MAKE_PROTECTED_DONE;
        } else {
          const done = await makePrivate(repository.id, makePrivateQuery(read, ack.checked));

          pending = madePrivateDone(done.revoked);
        }

        dialog.close();
        onDone();
      } catch (cause) {
        confirm.disabled = false;

        // What the preview did not see: the API names the rows, and they have to be acknowledged.
        if (mode !== 'private' && composer.refused(cause)) {
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
    onKnown(read.visibility as Visibility, read, repository);

    const content = visibilityCard(read, repository.role);

    card.hidden = content === null;

    if (content === null) return;

    state.className = content.visibility === 'public' ? 'pill pill-success' : 'pill';
    state.textContent = content.label;
    explanation.textContent = content.sentence;
    button.textContent = content.button;
    buttonMode = content.mode;
    cardDisabled = content.disabled;
    button.disabled = content.disabled;
    altMode = content.alt?.mode ?? null;
    altDisabled = content.alt?.disabled ?? false;
    altButton.hidden = content.alt === null;
    altButton.textContent = content.alt?.label ?? '';
    altButton.disabled = altDisabled;
    note.textContent = content.note ?? '';
    note.hidden = content.note === null;

    listed.hidden = content.listed === null;

    if (content.listed) {
      listedInput.checked = content.listed.checked;
      listedInput.disabled = false;
      listedLabel.textContent = content.listed.label;
      listedHelp.textContent = content.listed.help;
      listedLink.textContent = LISTED_PAGE_LINK;
      listedLink.href = storefrontHref(repository.id);
    }

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
      listed.hidden = true;
      say(status, '');
    },

    paint,
  };
}
