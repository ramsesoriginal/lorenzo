// The copy wizard (ADR 0201, RFC 0036 §3): check first, name clashes, review, done, on the page of
// the repository being copied. Nothing is written until the last button; every step before it is
// the API's own check (the copy plan, and a copy that is made and rolled back). The choices live in
// the page, in `state`, and are sent as the API's `resolutions`.

import {
  CHOICE_LABEL,
  type Choice,
  type ChoiceAction,
  COPY_LIMITS,
  type CopyRefusal,
  choiceExplanation,
  choiceProblem,
  collisionKey,
  collisionSentence,
  copyRefusal,
  droppedSentences,
  missingSentence,
  previousSentence,
  receiptSentence,
  recommendedChoices,
  resolutionsOf,
  stepHeading,
  stepLine,
  suggestedName,
  unsettled,
  type WizardStep,
} from '../../lib/copyWizard';
import { copyRepository, getCopyPlan } from '../../lib/repositories';
import { type CopyMode, shelfHref } from '../../lib/shelf';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type {
  CollisionOut,
  CopyOut,
  CopyPlanOut,
  CopyRequest,
  SubscriptionOut,
  TenantSummaryOut,
} from '../../lib/types';

const required = requiredIn('Copy wizard');

const STEPS: WizardStep[] = ['check', 'clashes', 'review', 'done'];

type State = {
  library: TenantSummaryOut;
  subscription: SubscriptionOut;
  mode: CopyMode;
  // For a copy that is made again: what happens to the earlier copy.
  again: 'keep' | 'purge';
  plan: CopyPlanOut | null;
  collisions: CollisionOut[];
  choices: Map<string, Choice>;
  review: CopyOut | null;
  step: WizardStep;
};

export type CopyWizard = {
  // Shows the wizard for a repository. Resolves to false when it cannot be copied (or copied
  // again) from where it stands, and shows nothing, for the page to show the repository instead.
  open(
    library: TenantSummaryOut,
    subscription: SubscriptionOut,
    mode: CopyMode,
    isCurrent: () => boolean,
  ): Promise<boolean>;
  close(): void;
};

// `view` is the wizard's block in the <RepositoriesPanel />, and `panel` the panel, whose
// templates it uses.
export function createCopyWizard(panel: HTMLElement, view: HTMLElement): CopyWizard {
  const title = required<HTMLElement>(view, '[data-copy-title]');
  const heading = required<HTMLElement>(view, '[data-copy-step]');
  const error = required<HTMLElement>(view, '[data-copy-error]');
  const working = required<HTMLElement>(view, '[data-copy-working]');
  const back = required<HTMLAnchorElement>(view, '[data-copy-back]');
  const sections = Object.fromEntries(
    STEPS.map((step) => [step, required<HTMLElement>(view, `[data-step="${step}"]`)]),
  ) as Record<WizardStep, HTMLElement>;

  const check = {
    limits: required<HTMLElement>(view, '[data-limits]'),
    again: required<HTMLFieldSetElement>(view, '[data-again]'),
    againKeep: required<HTMLElement>(view, '[data-again-keep]'),
    againPurge: required<HTMLElement>(view, '[data-again-purge]'),
    bringsSection: required<HTMLElement>(view, '[data-brings-section]'),
    brings: required<HTMLElement>(view, '[data-brings]'),
    attachments: required<HTMLElement>(view, '[data-attachments]'),
    clashCount: required<HTMLElement>(view, '[data-clash-count]'),
    blocked: required<HTMLElement>(view, '[data-blocked]'),
    blockedReason: required<HTMLElement>(view, '[data-blocked-reason]'),
    missing: required<HTMLElement>(view, '[data-missing]'),
    next: required<HTMLButtonElement>(view, '[data-check-next]'),
  };
  const clashes = {
    intro: required<HTMLElement>(view, '[data-clash-intro]'),
    recommendedAll: required<HTMLButtonElement>(view, '[data-recommended-all]'),
    progress: required<HTMLElement>(view, '[data-clash-progress]'),
    list: required<HTMLElement>(view, '[data-clashes]'),
    back: required<HTMLButtonElement>(view, '[data-clashes-back]'),
    next: required<HTMLButtonElement>(view, '[data-clashes-next]'),
  };
  const review = {
    receipt: required<HTMLElement>(view, '[data-receipt]'),
    previous: required<HTMLElement>(view, '[data-previous]'),
    dropped: required<HTMLElement>(view, '[data-dropped]'),
    stepLines: required<HTMLElement>(view, '[data-step-lines]'),
    back: required<HTMLButtonElement>(view, '[data-review-back]'),
    copyNow: required<HTMLButtonElement>(view, '[data-copy-now]'),
  };
  const done = {
    receipt: required<HTMLElement>(view, '[data-done-receipt]'),
    dropped: required<HTMLElement>(view, '[data-done-dropped]'),
    open: required<HTMLAnchorElement>(view, '[data-done-open]'),
  };

  let state: State | null = null;
  // Only the newest thing asked for paints, and a button pressed twice asks once.
  let latest = 0;
  let busy = false;

  const hasClashes = () => (state?.collisions.length ?? 0) > 0;

  function say(text: string | null): void {
    error.hidden = text === null;
    error.textContent = text ?? '';
  }

  function setBusy(value: boolean, text = 'Checking…'): void {
    busy = value;
    working.textContent = text;
    working.hidden = !value;

    for (const button of view.querySelectorAll<HTMLButtonElement>('button')) {
      button.disabled = value || button.dataset.keepDisabled === 'true';
    }

    if (!value) refreshClashButtons();
  }

  function showStep(step: WizardStep): void {
    if (!state) return;

    state.step = step;

    for (const name of STEPS) sections[name].hidden = name !== step;

    heading.textContent = stepHeading(step, hasClashes());
    heading.focus();
  }

  // --- Step 1: check first ---------------------------------------------------------------

  function paintCheck(): void {
    if (!state) return;

    const { plan, mode } = state;
    const target = plan?.steps.find((s) => s.repository_id === state?.subscription.repository.id);

    check.limits.replaceChildren(
      ...COPY_LIMITS.map((limit) => {
        const item = document.createElement('li');

        item.textContent = limit;

        return item;
      }),
    );
    check.again.hidden = mode !== 'again';
    check.bringsSection.hidden = true;
    check.clashCount.hidden = true;
    check.attachments.hidden = true;
    check.blocked.hidden = true;
    check.next.hidden = false;

    if (mode === 'again') {
      check.next.textContent = 'Check first';
      return;
    }

    check.next.textContent = 'Continue';

    if (!plan || !target) {
      blocked(
        'This repository cannot be copied right now. It may have been unpublished, or your library is no longer invited to it.',
        [],
      );
      return;
    }

    if (target.already_copied) {
      blocked(
        'Your library has already copied this repository. Updates arrive through its page; to copy it afresh, use “Copy again” there.',
        [],
      );
      return;
    }

    const missing = plan.steps.filter(
      (step) => !step.already_copied && (!step.granted || !step.published),
    );

    if (missing.length > 0) {
      blocked(
        'It is built on repositories your library cannot copy yet, so nothing is counted and nothing can be copied.',
        missing.map((step) =>
          missingSentence({
            repositoryId: step.repository_id,
            name: step.name,
            granted: step.granted,
            published: step.published,
          }),
        ),
      );
      return;
    }

    check.bringsSection.hidden = false;
    check.brings.replaceChildren(
      ...plan.steps
        .filter((step) => !step.already_copied)
        .map((step) => {
          const item = document.createElement('li');

          item.textContent = stepLine(step);

          return item;
        }),
    );

    const attachments = plan.steps.reduce((total, step) => total + step.attachments, 0);

    check.attachments.textContent =
      attachments === 0
        ? ''
        : `It also adds a parent to ${attachments === 1 ? 'one entry' : `${attachments} entries`} of repositories it is built on that you have copied.`;
    check.attachments.hidden = attachments === 0;

    const count = state.collisions.length;

    check.clashCount.textContent =
      count === 0
        ? 'It clashes with no name in your library.'
        : `${count === 1 ? 'One name clashes with your library, and is not counted above.' : `${count} names clash with your library, and are not counted above.`} You choose what to do about each next, and the review counts everything.`;
    check.clashCount.hidden = false;
  }

  function blocked(reason: string, missing: string[]): void {
    check.blocked.hidden = false;
    check.blockedReason.textContent = reason;
    check.missing.replaceChildren(
      ...missing.map((sentence) => {
        const item = document.createElement('li');

        item.textContent = sentence;

        return item;
      }),
    );
    check.next.hidden = true;
  }

  // What choosing "Replace it" would remove, asked of the API when it is chosen: a copy that is
  // made and rolled back. If the names clash it cannot say yet, and the review will.
  async function paintAgainPurge(): Promise<void> {
    if (!state) return;

    const mine = state;
    const turn = ++latest;

    check.againPurge.textContent = 'Counting what this would remove…';

    try {
      const result = await copyRepository(mine.library.id, mine.subscription.repository.id, {
        dry_run: true,
        again: 'purge',
      });

      if (turn !== latest) return;

      check.againPurge.textContent = result.previous
        ? previousSentence(result.previous)
        : 'What the earlier copy created is removed first, together with what your library added to it.';
    } catch (cause) {
      if (turn !== latest) return;

      check.againPurge.textContent =
        copyRefusal(cause)?.kind === 'needs-choices'
          ? 'What this would remove is counted at the review, once the names are settled.'
          : 'What the earlier copy created is removed first, together with what your library added to it.';
    }
  }

  function chosenAgain(): 'keep' | 'purge' {
    const picked = check.again.querySelector<HTMLInputElement>('input[name="copy-again"]:checked');

    return picked?.value === 'purge' ? 'purge' : 'keep';
  }

  // --- Step 2: name clashes --------------------------------------------------------------

  function refreshClashButtons(): void {
    if (!state) return;

    const open = unsettled(state.collisions, state.choices).length;
    const total = state.collisions.length;

    clashes.progress.textContent =
      open === 0
        ? `All ${total === 1 ? 'one' : total} settled.`
        : `${total - open} of ${total} settled. Choose what to do about the rest to go on.`;
    clashes.next.disabled = busy || open > 0;
    clashes.next.dataset.keepDisabled = String(open > 0);
  }

  function paintProblem(card: HTMLElement, collision: CollisionOut): void {
    if (!state) return;

    const choice = state.choices.get(collisionKey(collision));
    const problem = required<HTMLElement>(card, '[data-problem]');
    // Only a name that was typed is complained about: an empty one is the first thing to type.
    const text =
      choice?.action === 'rename' && choice.name !== '' ? choiceProblem(collision, choice) : null;

    problem.textContent = text ?? '';
    problem.hidden = text === null;
  }

  function paintClash(collision: CollisionOut, index: number): HTMLElement {
    const mine = state as State;
    const card = cloneRoot(panel, '[data-clash-template]');
    const key = collisionKey(collision);
    const recommended = recommendedChoices([collision], mine.subscription.repository.name).get(key);
    const nameField = required<HTMLElement>(card, '[data-name-field]');
    const nameInput = required<HTMLInputElement>(card, '[data-name]');

    required<HTMLElement>(card, '[data-sentence]').textContent = collisionSentence(collision);
    required<HTMLElement>(card, '[data-name-label]').textContent =
      collision.kind === 'slug' ? 'New link name' : 'New name';

    const choices = required<HTMLElement>(card, '[data-choices]');

    for (const action of collision.choices) {
      const option = cloneRoot(panel, '[data-choice-template]');
      const radio = required<HTMLInputElement>(option, '[data-radio]');

      radio.name = `clash-${index}`;
      radio.value = action;
      radio.checked = mine.choices.get(key)?.action === action;
      required<HTMLElement>(option, '[data-label]').textContent = CHOICE_LABEL[action];
      required<HTMLElement>(option, '[data-explanation]').textContent = choiceExplanation(
        collision,
        action,
      );
      required<HTMLElement>(option, '[data-recommended]').hidden = recommended?.action !== action;
      choices.append(option);
    }

    function paintName(): void {
      const choice = mine.choices.get(key);

      nameField.hidden = choice?.action !== 'rename';
      nameInput.value = choice?.name ?? '';
    }

    card.addEventListener('change', (event) => {
      const radio = event.target as HTMLInputElement;

      if (radio.type !== 'radio') return;

      const action = radio.value as ChoiceAction;
      const known = mine.choices.get(key);

      mine.choices.set(key, {
        action,
        name: known?.name || suggestedName(collision, mine.subscription.repository.name),
      });
      paintName();
      paintProblem(card, collision);
      refreshClashButtons();

      if (action === 'rename') nameInput.focus();
    });

    nameInput.addEventListener('input', () => {
      const choice = mine.choices.get(key);

      if (choice) choice.name = nameInput.value;

      paintProblem(card, collision);
      refreshClashButtons();
    });

    paintName();
    paintProblem(card, collision);

    return card;
  }

  function paintClashes(note: string | null = null): void {
    if (!state) return;

    const count = state.collisions.length;

    clashes.intro.textContent = [
      note,
      count === 1
        ? 'One name is already in use in your library. Choose what to do about it.'
        : `${count} names are already in use in your library. Choose what to do about each.`,
    ]
      .filter(Boolean)
      .join(' ');
    clashes.list.replaceChildren(...state.collisions.map((c, index) => paintClash(c, index)));
    refreshClashButtons();
  }

  // --- Step 3 and 4: review and done -----------------------------------------------------

  function paintReceipt(result: CopyOut): void {
    if (!state) return;

    const text = receiptSentence(result, state.collisions, state.choices);
    const dropped = droppedSentences(result.steps);
    const lines = result.steps.map(stepLine);

    if (result.dry_run) {
      review.receipt.textContent = text;
      review.previous.textContent = result.previous ? previousSentence(result.previous) : '';
      review.previous.hidden = !result.previous;
      review.dropped.replaceChildren(...dropped.map(listItem));
      review.dropped.hidden = dropped.length === 0;
      review.stepLines.replaceChildren(...lines.map(listItem));
    } else {
      done.receipt.textContent = result.previous
        ? `${text} ${previousSentence(result.previous)}`
        : text;
      done.dropped.replaceChildren(...dropped.map(listItem));
      done.dropped.hidden = dropped.length === 0;
    }
  }

  function listItem(text: string): HTMLElement {
    const item = document.createElement('li');

    item.textContent = text;

    return item;
  }

  // --- Asking the API --------------------------------------------------------------------

  function request(dryRun: boolean): CopyRequest {
    const mine = state as State;
    const resolutions = resolutionsOf(mine.collisions, mine.choices);

    return {
      ...(dryRun ? { dry_run: true } : {}),
      ...(mine.mode === 'again' ? { again: mine.again } : {}),
      ...(resolutions.length > 0 ? { resolutions } : {}),
    };
  }

  // A copy the API refused, taken to the step where it is explained.
  function refused(refusal: CopyRefusal | null, cause: unknown): void {
    if (!state) return;

    switch (refusal?.kind) {
      case 'needs-choices': {
        const known = new Set(state.collisions.map(collisionKey));
        const found = refusal.collisions.filter((c) => !known.has(collisionKey(c)));

        if (found.length === 0) {
          say('Some names are still in use. Check your choices.');
          showStep(hasClashes() ? 'clashes' : 'check');
          return;
        }

        state.collisions = [...state.collisions, ...found];
        paintClashes(
          state.mode === 'again' && state.step === 'check'
            ? null
            : `Your choices brought ${found.length === 1 ? 'one more name' : `${found.length} more names`} to a clash.`,
        );
        say(null);
        showStep('clashes');
        return;
      }
      case 'needs-grants':
        paintCheck();
        blocked(
          'It is built on repositories your library cannot copy yet.',
          refusal.missing.map(missingSentence),
        );
        say(null);
        showStep('check');
        return;
      case 'already-copied':
        say(
          'Your library has already copied this repository. Updates arrive through its page; to copy it afresh, use “Copy again” there.',
        );
        return;
      case 'formula-cycle':
        say(
          `${refusal.detail || 'Merged stats would make formulas depend on each other in a loop'}. Go back, and choose Keep both for a stat you chose to use the existing one for.`,
        );
        return;
      case 'bad-choice':
        say(`${refusal.detail}. Change it, and review again.`);
        showStep(hasClashes() ? 'clashes' : 'check');
        return;
      default:
        sayError(error, cause);
    }
  }

  // Checks the copy (rolled back) or makes it. Resolves to the result, or null once a refusal has
  // been shown.
  async function ask(dryRun: boolean): Promise<CopyOut | null> {
    if (!state || busy) return null;

    const mine = state;
    const turn = ++latest;

    say(null);
    setBusy(true, dryRun ? 'Checking…' : 'Copying…');

    try {
      const result = await copyRepository(
        mine.library.id,
        mine.subscription.repository.id,
        request(dryRun),
      );

      return turn === latest ? result : null;
    } catch (cause) {
      if (turn === latest) refused(copyRefusal(cause), cause);

      return null;
    } finally {
      if (turn === latest) setBusy(false);
    }
  }

  async function toReview(): Promise<void> {
    const result = await ask(true);

    if (!state || !result) return;

    state.review = result;
    paintReceipt(result);
    showStep('review');
  }

  // --- The buttons -----------------------------------------------------------------------

  check.next.addEventListener('click', () => {
    if (!state || busy) return;

    if (state.mode === 'again') state.again = chosenAgain();

    if (state.mode === 'new' && hasClashes()) {
      paintClashes();
      say(null);
      showStep('clashes');
      return;
    }

    void toReview();
  });

  clashes.recommendedAll.addEventListener('click', () => {
    if (!state) return;

    state.choices = recommendedChoices(state.collisions, state.subscription.repository.name);
    paintClashes();
  });
  clashes.back.addEventListener('click', () => {
    say(null);
    showStep('check');
  });
  clashes.next.addEventListener('click', () => void toReview());

  review.back.addEventListener('click', () => {
    say(null);
    showStep(hasClashes() ? 'clashes' : 'check');
  });
  review.copyNow.addEventListener('click', () => {
    void (async () => {
      const result = await ask(false);

      if (!state || !result) return;

      state.review = result;
      paintReceipt(result);
      showStep('done');
    })();
  });

  check.again.addEventListener('change', () => {
    if (!state) return;

    state.again = chosenAgain();

    if (state.again === 'purge') void paintAgainPurge();
  });

  // --- Opening ---------------------------------------------------------------------------

  return {
    async open(library, subscription, mode, isCurrent) {
      const copied = subscription.copied_at !== null;
      const offered =
        subscription.granted_at !== null && subscription.repository.published_at !== null;

      // A first copy is of a repository that is offered, published and not yet copied; another
      // is of one the library has copied.
      if (mode === 'new' ? copied || !offered : !copied) return false;

      const turn = ++latest;

      state = {
        library,
        subscription,
        mode,
        again: 'keep',
        plan: null,
        collisions: [],
        choices: new Map(),
        review: null,
        step: 'check',
      };
      title.textContent =
        mode === 'again'
          ? `Copy ${subscription.repository.name} again`
          : `Copy ${subscription.repository.name}`;
      back.href = shelfHref(library.slug, subscription.repository.id);
      done.open.href = shelfHref(library.slug, subscription.repository.id);
      say(null);
      setBusy(false);

      if (mode === 'again') {
        const keep = check.again.querySelector<HTMLInputElement>('input[value="keep"]');

        if (keep) keep.checked = true;

        check.againPurge.textContent =
          'What the earlier copy created is removed first, together with what your library added to it.';
      } else {
        try {
          const plan = await getCopyPlan(library.id, subscription.repository.id, { fresh: true });

          if (turn !== latest || !isCurrent()) return true;

          state.plan = plan;
          state.collisions = plan?.collisions ?? [];
        } catch (cause) {
          if (turn !== latest || !isCurrent()) return true;

          paintCheck();
          showStep('check');
          sayError(error, cause);
          return true;
        }
      }

      paintCheck();
      showStep('check');

      return true;
    },

    close() {
      latest += 1;
      state = null;
    },
  };
}
