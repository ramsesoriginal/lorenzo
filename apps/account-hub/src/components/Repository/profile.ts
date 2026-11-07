// A repository's Profile tab (RFC 0036 §4 T5, RFC 0038 §2, ADR 0385): the form an Owner edits it with,
// the same page read-only for every other member, the cover, and what people will see. The words and
// the rules are lib/profileEditor.ts's; this is the DOM around them.
//
// One form, one Save: what changed goes in a single `PATCH` (ADR 0213), so a refusal keeps none of it,
// and the API's refusals are shown next to the fields they name. Nothing is sent until Save. What is
// typed and not saved is not lost by a redraw of the page, and leaving it asks first.

import { ApiError } from '../../lib/apiError';
import { askFirst } from '../../lib/askFirst';
import { getFacets } from '../../lib/discoverApi';
import { avatarInitial } from '../../lib/format';
import { includesFacts } from '../../lib/inclusion';
import {
  addLanguages,
  addTags,
  apiProblems,
  CREDIT_NAME_MAX,
  CREDIT_ROLE_MAX,
  CREDITS_HELP,
  CREDITS_LABEL,
  CREDITS_MAX,
  capLine,
  creditKey,
  type Draft,
  draftOf,
  isChanged,
  LANGUAGES_HELP,
  LANGUAGES_LABEL,
  LANGUAGES_MAX,
  LEAVE_UNSAVED,
  LICENCE_LABEL,
  LICENCE_LINK_HELP,
  LICENCE_LINK_LABEL,
  LICENCE_NAME_LABEL,
  LICENCES,
  languageName,
  mayEditProfile,
  moved,
  NO_LICENCE_CHOICE,
  NO_LICENCE_HELP,
  NOTHING_CHANGED,
  ONLY_AN_OWNER,
  OTHER_LICENCE,
  OTHER_LICENCE_CHOICE,
  PREVIEW_HEADING,
  PREVIEW_INTRO,
  PROFILE_HEADING,
  PROFILE_INTRO,
  type Problems,
  patchOf,
  previewCard,
  previewFacts,
  problemsOf,
  REVERT_LABEL,
  SAVE_LABEL,
  SAVED,
  SAVING,
  SUMMARY_LABEL,
  SYSTEM_HELP,
  SYSTEM_LABEL,
  suggestLanguages,
  suggestValues,
  TAGS_HELP,
  TAGS_LABEL,
  TAGS_MAX,
  UNSAVED,
  usualLink,
} from '../../lib/profileEditor';
import { getRepositoryProfile, updateRepositoryProfile } from '../../lib/repositories';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { DiscoverFacetsOut, MemberProfileOut, TenantSummaryOut } from '../../lib/types';
import { paintCard } from '../Discover/card';
import { createCoverControls } from './cover';
import { bindSummaryField } from './summaryField';

const required = requiredIn('Repository');

export type ProfileControls = {
  // Empties the tab. `keepDraft` keeps what was typed and not saved, for the same repository drawn
  // again.
  clear(keepDraft: boolean): void;
  // Reads the profile and draws the tab: the form for an Owner, the reading for anyone else.
  load(repository: TenantSummaryOut, isCurrent: () => boolean): Promise<void>;
  // Whether something typed is not saved.
  isDirty(): boolean;
  // True where nothing is unsaved or the person said to leave it.
  mayLeave(): boolean | Promise<boolean>;
  // Moves the cursor to a field, or to where the cover is chosen.
  focus(target: 'summary' | 'cover'): void;
};

// The language of the reader, for the names of languages.
function readerLocales(): string[] {
  return typeof navigator !== 'undefined' && navigator.languages.length > 0
    ? [...navigator.languages]
    : ['en'];
}

function setProblem(element: HTMLElement, text: string | undefined): void {
  element.textContent = text ?? '';
  element.hidden = text === undefined;
}

// `root` is the <Repository /> article. `onSaved` is called when the profile was saved, and
// `onCoverChanged` when a cover was uploaded or removed, for what depends on them (the readiness list).
export function createProfileEditor(
  root: HTMLElement,
  hooks: { onSaved(): void; onCoverChanged(): void },
): ProfileControls {
  const panel = required<HTMLElement>(root, '[data-profile]');
  const errorLine = required<HTMLElement>(panel, '[data-profile-error]');
  const ownerOnly = required<HTMLElement>(panel, '[data-profile-owner-only]');
  const form = required<HTMLFormElement>(panel, '[data-profile-form]');
  const summaryInput = required<HTMLTextAreaElement>(form, '[data-profile-summary]');
  const licenceSelect = required<HTMLSelectElement>(form, '[data-licence]');
  const licenceOtherField = required<HTMLElement>(form, '[data-licence-other-field]');
  const licenceOther = required<HTMLInputElement>(form, '[data-licence-other]');
  const licenceLinkField = required<HTMLElement>(form, '[data-licence-link-field]');
  const licenceLink = required<HTMLInputElement>(form, '[data-licence-link]');
  const creditsList = required<HTMLElement>(form, '[data-credits-list]');
  const creditsCount = required<HTMLElement>(form, '[data-credits-count]');
  const creditAdd = required<HTMLButtonElement>(form, '[data-credit-add]');
  const tagsList = required<HTMLElement>(form, '[data-tags-list]');
  const tagInput = required<HTMLInputElement>(form, '[data-tag-input]');
  const tagAdd = required<HTMLButtonElement>(form, '[data-tag-add]');
  const tagOptions = required<HTMLElement>(form, '[data-tag-options]');
  const tagsCount = required<HTMLElement>(form, '[data-tags-count]');
  const systemInput = required<HTMLInputElement>(form, '[data-system]');
  const systemOptions = required<HTMLElement>(form, '[data-system-options]');
  const languagesList = required<HTMLElement>(form, '[data-languages-list]');
  const languageInput = required<HTMLInputElement>(form, '[data-language-input]');
  const languageAdd = required<HTMLButtonElement>(form, '[data-language-add]');
  const languageOptions = required<HTMLElement>(form, '[data-language-options]');
  const languagesCount = required<HTMLElement>(form, '[data-languages-count]');
  const save = required<HTMLButtonElement>(form, '[data-profile-save]');
  const revert = required<HTMLButtonElement>(form, '[data-profile-revert]');
  const status = required<HTMLElement>(form, '[data-profile-status]');
  const previewCardList = required<HTMLElement>(panel, '[data-preview-card]');
  const previewFactList = required<HTMLElement>(panel, '[data-preview-facts]');

  const summary = bindSummaryField({
    input: summaryInput,
    help: required<HTMLElement>(form, '[data-profile-summary-help]'),
    count: required<HTMLElement>(form, '[data-profile-summary-count]'),
  });

  required<HTMLElement>(panel, '[data-profile-heading]').textContent = PROFILE_HEADING;
  required<HTMLElement>(panel, '[data-profile-intro]').textContent = PROFILE_INTRO;
  ownerOnly.textContent = ONLY_AN_OWNER;
  required<HTMLElement>(form, '[data-summary-label]').textContent = SUMMARY_LABEL;
  required<HTMLElement>(form, '[data-licence-label]').textContent = LICENCE_LABEL;
  required<HTMLElement>(form, '[data-licence-help]').textContent = NO_LICENCE_HELP;
  required<HTMLElement>(form, '[data-licence-other-label]').textContent = LICENCE_NAME_LABEL;
  required<HTMLElement>(form, '[data-licence-link-label]').textContent = LICENCE_LINK_LABEL;
  required<HTMLElement>(form, '[data-licence-link-help]').textContent = LICENCE_LINK_HELP;
  required<HTMLElement>(form, '[data-credits-label]').textContent = CREDITS_LABEL;
  required<HTMLElement>(form, '[data-credits-help]').textContent = CREDITS_HELP;
  creditAdd.textContent = 'Add a credit';
  required<HTMLElement>(form, '[data-tags-label]').textContent = TAGS_LABEL;
  required<HTMLElement>(form, '[data-tags-help]').textContent = TAGS_HELP;
  required<HTMLElement>(form, '[data-system-label]').textContent = SYSTEM_LABEL;
  required<HTMLElement>(form, '[data-system-help]').textContent = SYSTEM_HELP;
  required<HTMLElement>(form, '[data-languages-label]').textContent = LANGUAGES_LABEL;
  required<HTMLElement>(form, '[data-languages-help]').textContent = LANGUAGES_HELP;
  required<HTMLElement>(panel, '[data-preview-heading]').textContent = PREVIEW_HEADING;
  required<HTMLElement>(panel, '[data-preview-intro]').textContent = PREVIEW_INTRO;
  save.textContent = SAVE_LABEL;
  revert.textContent = REVERT_LABEL;

  licenceSelect.replaceChildren(
    ...[
      { value: '', label: NO_LICENCE_CHOICE },
      ...LICENCES.map((licence) => ({ value: licence.label, label: licence.label })),
      { value: OTHER_LICENCE, label: OTHER_LICENCE_CHOICE },
    ].map((choice) => {
      const option = document.createElement('option');

      option.value = choice.value;
      option.textContent = choice.label;

      return option;
    }),
  );

  const locales = readerLocales();
  let shown: TenantSummaryOut | null = null;
  // What the API has, and what the form holds.
  let saved: MemberProfileOut | null = null;
  let draft: Draft | null = null;
  let owner = false;
  let problems: Problems = {};
  let facets: DiscoverFacetsOut | null = null;
  let coverUrl: string | null = null;
  let hasCover = false;
  let loaded = 0;

  const cover = createCoverControls(root, {
    shown(has, url) {
      hasCover = has;
      coverUrl = url;
      paintPreview();
    },
    changed: hooks.onCoverChanged,
  });

  // --- What is typed and not saved ---------------------------------------------------------

  function pending(): boolean {
    return tagInput.value.trim() !== '' || languageInput.value.trim() !== '';
  }

  function dirty(): boolean {
    return owner && saved !== null && draft !== null && (isChanged(saved, draft) || pending());
  }

  window.addEventListener('beforeunload', (event) => {
    if (!dirty()) return;

    event.preventDefault();
  });

  // --- Painting ----------------------------------------------------------------------------

  function paintProblems(): void {
    for (const slot of form.querySelectorAll<HTMLElement>('[data-problem]')) {
      const key = slot.dataset.problem;

      if (key) setProblem(slot, problems[key]);
    }

    const rows = [...creditsList.children];

    rows.forEach((row, index) => {
      const slots = [...row.querySelectorAll<HTMLElement>('[data-problem]')];

      (['name', 'role', 'url'] as const).forEach((part, at) => {
        const slot = slots[at];

        if (slot) setProblem(slot, problems[creditKey(index, part)]);
      });
    });
  }

  function paintStatus(): void {
    // "Saved." stays until something changes; then it says what is true.
    if (status.dataset.state === 'saved' && !dirty()) return;

    status.dataset.state = dirty() ? 'unsaved' : '';
    status.classList.remove('error-text');
    status.textContent = dirty() ? UNSAVED : '';
    status.hidden = !dirty();
  }

  function paintButtons(): void {
    const changed = dirty();

    save.disabled = !changed;
    revert.disabled = !changed;
    paintStatus();
  }

  function paintCounts(): void {
    if (!draft) return;

    creditsCount.textContent = capLine(draft.credits.length, CREDITS_MAX, 'credit', 'credits');
    creditAdd.disabled = draft.credits.length >= CREDITS_MAX;
    tagsCount.textContent = capLine(draft.tags.length, TAGS_MAX, 'tag', 'tags');
    tagAdd.disabled = draft.tags.length >= TAGS_MAX;
    languagesCount.textContent = capLine(
      draft.languages.length,
      LANGUAGES_MAX,
      'language',
      'languages',
    );
    languageAdd.disabled = draft.languages.length >= LANGUAGES_MAX;
  }

  function fillOptions(
    list: HTMLElement,
    options: readonly { value: string; label?: string }[],
  ): void {
    list.replaceChildren(
      ...options.map((entry) => {
        const option = document.createElement('option');

        option.value = entry.value;
        if (entry.label) option.label = entry.label;

        return option;
      }),
    );
  }

  // What Discover already has, offered and never required: only where the deployment has Discover.
  function paintSuggestions(): void {
    if (!draft || !facets?.enabled) {
      fillOptions(tagOptions, []);
      fillOptions(systemOptions, []);
      fillOptions(languageOptions, draft ? suggestLanguages([], draft.languages, locales) : []);

      return;
    }

    fillOptions(
      tagOptions,
      suggestValues(facets.tags, draft.tags).map((value) => ({ value })),
    );
    fillOptions(
      systemOptions,
      suggestValues(facets.systems, []).map((value) => ({ value })),
    );
    fillOptions(languageOptions, suggestLanguages(facets.languages, draft.languages, locales));
  }

  function chip(text: string, label: string, remove: () => void): HTMLElement {
    const item = cloneRoot(root, '[data-chip-template]');
    const button = required<HTMLButtonElement>(item, '[data-chip]');

    required<HTMLElement>(item, '[data-text]').textContent = text;
    button.setAttribute('aria-label', label);
    button.addEventListener('click', remove);

    return item;
  }

  function paintTags(): void {
    if (!draft) return;

    tagsList.replaceChildren(
      ...draft.tags.map((tag) =>
        chip(tag, `Remove the tag ${tag}`, () => {
          if (!draft) return;

          draft.tags = draft.tags.filter((other) => other !== tag);
          edited();
          paintTags();
          tagInput.focus();
        }),
      ),
    );
    tagsList.hidden = draft.tags.length === 0;
    paintCounts();
    paintSuggestions();
  }

  function paintLanguages(): void {
    if (!draft) return;

    languagesList.replaceChildren(
      ...draft.languages.map((code) =>
        chip(
          languageName(code, locales),
          `Remove the language ${languageName(code, locales)}`,
          () => {
            if (!draft) return;

            draft.languages = draft.languages.filter((other) => other !== code);
            edited();
            paintLanguages();
            languageInput.focus();
          },
        ),
      ),
    );
    languagesList.hidden = draft.languages.length === 0;
    paintCounts();
    paintSuggestions();
  }

  function paintLicence(): void {
    if (!draft) return;

    licenceSelect.value = draft.licence;
    licenceOtherField.hidden = draft.licence !== OTHER_LICENCE;
    licenceLinkField.hidden = draft.licence === '';
  }

  function paintCredits(): void {
    if (!draft) return;

    const credits = draft.credits;

    creditsList.replaceChildren(
      ...credits.map((credit, index) => {
        const row = cloneRoot(root, '[data-credit-template]');
        const name = required<HTMLInputElement>(row, '[data-credit-name]');
        const role = required<HTMLInputElement>(row, '[data-credit-role]');
        const url = required<HTMLInputElement>(row, '[data-credit-url]');
        const up = required<HTMLButtonElement>(row, '[data-credit-up]');
        const down = required<HTMLButtonElement>(row, '[data-credit-down]');

        row.setAttribute('role', 'group');
        row.setAttribute('aria-label', `Credit ${index + 1}`);
        required<HTMLElement>(row, '[data-name-label]').textContent = 'Name';
        required<HTMLElement>(row, '[data-role-label]').textContent = 'What they did (optional)';
        required<HTMLElement>(row, '[data-url-label]').textContent = 'Link (optional)';
        name.value = name.defaultValue = credit.name;
        role.value = role.defaultValue = credit.role;
        url.value = url.defaultValue = credit.url;
        name.maxLength = CREDIT_NAME_MAX * 2;
        role.maxLength = CREDIT_ROLE_MAX * 2;
        up.disabled = index === 0;
        down.disabled = index === credits.length - 1;

        name.addEventListener('input', () => {
          credit.name = name.value;
          edited(creditKey(index, 'name'));
        });
        role.addEventListener('input', () => {
          credit.role = role.value;
          edited(creditKey(index, 'role'));
        });
        url.addEventListener('input', () => {
          credit.url = url.value;
          edited(creditKey(index, 'url'));
        });
        up.addEventListener('click', () => {
          if (!draft) return;

          draft.credits = moved(draft.credits, index, -1);
          edited();
          paintCredits();
        });
        down.addEventListener('click', () => {
          if (!draft) return;

          draft.credits = moved(draft.credits, index, 1);
          edited();
          paintCredits();
        });
        required<HTMLButtonElement>(row, '[data-credit-remove]').addEventListener('click', () => {
          if (!draft) return;

          draft.credits = draft.credits.filter((_, at) => at !== index);
          edited();
          paintCredits();
          creditAdd.focus();
        });

        return row;
      }),
    );
    paintCounts();
    paintProblems();
  }

  // What people will see: Discover's own card for what is in the form (for an Owner) or what is saved
  // (for everyone else), with the cover, and what the repository's page adds.
  function paintPreview(): void {
    const repository = shown;
    const shownDraft = draft ?? (saved ? draftOf(saved) : null);

    if (!repository || !shownDraft) return;

    const card = paintCard(root, previewCard(repository.name, shownDraft), null);
    const picture = required<HTMLImageElement>(card, '[data-picture]');
    const initial = required<HTMLElement>(card, '[data-initial]');

    initial.textContent = avatarInitial(repository.name);
    picture.hidden = coverUrl === null || !hasCover;
    initial.hidden = !picture.hidden;
    if (coverUrl && hasCover) picture.src = coverUrl;

    previewCardList.replaceChildren(card);

    // What it says it includes comes from the release that was made, not from the form: a snapshot
    // of the names and licences as they were then (ADR 0431).
    const facts = [...previewFacts(shownDraft, locales), ...includesFacts(saved?.includes)];

    previewFactList.replaceChildren(
      ...facts.flatMap((fact) => {
        const term = document.createElement('dt');
        const value = document.createElement('dd');

        term.textContent = fact.term;

        if (fact.url) {
          const link = document.createElement('a');

          link.href = fact.url;
          link.textContent = fact.value;
          link.className = 'shelf-link';
          link.rel = 'nofollow noopener';
          link.target = '_blank';
          value.append(link);
        } else {
          value.textContent = fact.value;
        }

        return [term, value];
      }),
    );
  }

  // Draws every field from the draft, as the fields are drawn once and then typed into.
  function paintAll(): void {
    if (!draft) return;

    summary.set(draft.summary);
    paintLicence();
    licenceOther.value = licenceOther.defaultValue = draft.licenceOther;
    licenceLink.value = licenceLink.defaultValue = draft.licenceUrl;
    systemInput.value = systemInput.defaultValue = draft.system;
    tagInput.value = tagInput.defaultValue = '';
    languageInput.value = languageInput.defaultValue = '';
    paintCredits();
    paintTags();
    paintLanguages();
    paintProblems();
    paintPreview();
    paintButtons();
  }

  // A field was typed in or a list changed: what depends on the draft is drawn again, not the fields.
  // Whatever problem was shown for the field is taken back; Save finds it again if it is still true.
  function edited(key?: string): void {
    if (key) delete problems[key];
    delete problems.form;
    paintProblems();
    paintPreview();
    paintButtons();
  }

  // --- The fields --------------------------------------------------------------------------

  summary.onInput(() => {
    if (!draft) return;

    draft.summary = summary.value();
    edited('summary');
  });

  licenceSelect.addEventListener('change', () => {
    if (!draft) return;

    const before = usualLink(draft.licence);

    draft.licence = licenceSelect.value;

    // The usual link of a listed licence is offered where the link is empty or was the last one's.
    const wanted = usualLink(draft.licence);

    if (wanted && (draft.licenceUrl.trim() === '' || draft.licenceUrl === before)) {
      draft.licenceUrl = wanted;
      licenceLink.value = wanted;
    } else if (before && draft.licenceUrl === before && !wanted) {
      draft.licenceUrl = '';
      licenceLink.value = '';
    }

    paintLicence();
    delete problems.licence;
    delete problems.licenceLink;
    edited();
  });
  licenceOther.addEventListener('input', () => {
    if (!draft) return;

    draft.licenceOther = licenceOther.value;
    edited('licence');
  });
  licenceLink.addEventListener('input', () => {
    if (!draft) return;

    draft.licenceUrl = licenceLink.value;
    edited('licenceLink');
  });
  systemInput.addEventListener('input', () => {
    if (!draft) return;

    draft.system = systemInput.value;
    edited('system');
  });

  creditAdd.addEventListener('click', () => {
    if (!draft || draft.credits.length >= CREDITS_MAX) return;

    draft.credits = [...draft.credits, { name: '', role: '', url: '' }];
    edited();
    paintCredits();

    const rows = creditsList.children;

    rows[rows.length - 1]?.querySelector<HTMLInputElement>('[data-credit-name]')?.focus();
  });

  // A tag or a language typed in, added in the form the API keeps. Its refusal is said next to it.
  function takeTags(): boolean {
    if (!draft || tagInput.value.trim() === '') return true;

    const added = addTags(draft.tags, tagInput.value);

    draft.tags = added.list;

    if (added.problem) {
      problems.tags = added.problem;
      paintTags();
      paintProblems();
      paintButtons();

      return false;
    }

    tagInput.value = '';
    delete problems.tags;
    edited();
    paintTags();

    return true;
  }

  function takeLanguages(): boolean {
    if (!draft || languageInput.value.trim() === '') return true;

    const added = addLanguages(draft.languages, languageInput.value);

    draft.languages = added.list;

    if (added.problem) {
      problems.languages = added.problem;
      paintLanguages();
      paintProblems();
      paintButtons();

      return false;
    }

    languageInput.value = '';
    delete problems.languages;
    edited();
    paintLanguages();

    return true;
  }

  tagAdd.addEventListener('click', () => {
    takeTags();
    tagInput.focus();
  });
  tagInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;

    // Enter adds the tag; it does not send the form.
    event.preventDefault();
    takeTags();
  });
  tagInput.addEventListener('input', () => {
    delete problems.tags;
    paintProblems();
    paintButtons();
  });
  languageAdd.addEventListener('click', () => {
    takeLanguages();
    languageInput.focus();
  });
  languageInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;

    event.preventDefault();
    takeLanguages();
  });
  languageInput.addEventListener('input', () => {
    delete problems.languages;
    paintProblems();
    paintButtons();
  });

  // --- Revert and Save ---------------------------------------------------------------------

  revert.addEventListener('click', () => {
    if (!saved) return;

    draft = draftOf(saved);
    problems = {};
    status.dataset.state = '';
    paintAll();
  });

  // The field to put the cursor in: the first of what is wrong, in the order of the form.
  function firstProblem(): HTMLElement | null {
    const fields: [string, HTMLElement][] = [
      ['summary', summaryInput],
      ['licence', licenceOther],
      ['licenceLink', licenceLink],
    ];

    for (const [key, field] of fields) if (problems[key]) return field;

    for (const [index, row] of [...creditsList.children].entries()) {
      for (const [part, selector] of [
        ['name', '[data-credit-name]'],
        ['role', '[data-credit-role]'],
        ['url', '[data-credit-url]'],
      ] as const) {
        if (problems[creditKey(index, part)]) return row.querySelector<HTMLElement>(selector);
      }
    }

    if (problems.credits) return creditAdd;
    if (problems.tags) return tagInput;
    if (problems.system) return systemInput;
    if (problems.languages) return languageInput;

    return null;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const repository = shown;

    if (!repository || !saved || !draft || !owner) return;

    // What was typed into a list's box and not added is added, or refused, first.
    if (!takeTags() || !takeLanguages()) {
      firstProblem()?.focus();

      return;
    }

    problems = problemsOf(draft);

    if (Object.keys(problems).length > 0) {
      paintProblems();
      status.dataset.state = '';
      firstProblem()?.focus();

      return;
    }

    const patch = patchOf(saved, draft);

    if (Object.keys(patch).length === 0) {
      status.dataset.state = '';
      status.classList.remove('error-text');
      status.textContent = NOTHING_CHANGED;
      status.hidden = false;

      return;
    }

    save.disabled = true;
    revert.disabled = true;
    status.dataset.state = '';
    status.classList.remove('error-text');
    status.textContent = SAVING;
    status.hidden = false;

    void (async () => {
      try {
        const updated = await updateRepositoryProfile(repository.id, patch);

        if (shown !== repository) return;

        // What the API kept, normalised, is shown back.
        saved = updated;
        draft = draftOf(updated);
        problems = {};
        paintAll();
        status.dataset.state = 'saved';
        status.textContent = SAVED;
        status.hidden = false;
        hooks.onSaved();
      } catch (cause) {
        if (shown !== repository) return;

        problems = apiProblems(cause);
        paintProblems();
        status.dataset.state = '';
        status.hidden = true;

        const formSlot = form.querySelector<HTMLElement>('[data-problem="form"]');

        // A session that ended has its way back to login with the message.
        if (formSlot && cause instanceof ApiError && cause.status === 401)
          sayError(formSlot, cause);

        paintButtons();
        firstProblem()?.focus();
      }
    })();
  });

  // --- The tab -----------------------------------------------------------------------------

  async function loadFacets(repository: TenantSummaryOut): Promise<void> {
    try {
      const read = await getFacets();

      if (shown !== repository) return;

      facets = read;
      paintSuggestions();
    } catch {
      // Suggestions are never required: without them there are none.
    }
  }

  return {
    clear(keepDraft) {
      shown = null;
      loaded++;
      cover.clear();
      panel.hidden = true;
      errorLine.hidden = true;
      form.hidden = true;
      previewCardList.replaceChildren();
      previewFactList.replaceChildren();
      problems = {};

      if (!keepDraft) {
        saved = null;
        draft = null;
        status.dataset.state = '';
        status.hidden = true;
      }
    },

    async load(repository, isCurrent) {
      const turn = ++loaded;
      const keep = draft !== null && saved !== null && owner && isChanged(saved, draft);

      let profile: MemberProfileOut;

      try {
        profile = await getRepositoryProfile(repository.id, { fresh: true });
      } catch (cause) {
        if (!isCurrent() || turn !== loaded) return;

        shown = repository;
        panel.hidden = false;
        sayError(errorLine, cause);

        return;
      }

      if (!isCurrent() || turn !== loaded) return;

      shown = repository;
      owner = mayEditProfile(repository.role);
      saved = profile;
      // What was typed and not saved stays; anything else starts from what the API has.
      if (!keep || draft === null) draft = draftOf(profile);

      errorLine.hidden = true;
      panel.hidden = false;
      ownerOnly.hidden = owner;
      form.hidden = !owner;

      if (owner) paintAll();
      else paintPreview();

      await cover.paint(repository, profile.has_cover, owner);

      if (owner) void loadFacets(repository);
    },

    isDirty: dirty,

    mayLeave() {
      return dirty() ? askFirst(LEAVE_UNSAVED, { confirm: 'Leave', cancel: 'Keep editing' }) : true;
    },

    focus(target) {
      if (target === 'cover') {
        cover.focus();

        return;
      }

      summaryInput.scrollIntoView({ block: 'center' });
      summary.focus();
    },
  };
}
