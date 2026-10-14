// "What people can look at", on a repository's Overview (RFC 0038 §5, ADR 0293): the Owner's choice
// of how much of the repository can be looked at before copying, and which entries they feature, in
// what order. An Owner's: nothing is asked of the API for anyone else. Every change is saved as it is
// made, since there is one thing to save and no way to leave it half done; a refusal changes nothing
// and the card reads what the API holds again.

import { ApiError } from '../../lib/apiError';
import {
  getRepositoryProfile,
  getShowcase,
  putShowcase,
  searchOwnEntries,
  setPreviewChoice,
} from '../../lib/repositories';
import {
  ADD_HINT,
  ADD_LABEL,
  ADD_NONE,
  actionLabel,
  added,
  canAdd,
  candidates,
  FEATURED_HEADING,
  FEATURED_NONE,
  featuredCount,
  LOOK_EXPLANATION,
  LOOK_HEADING,
  limitLine,
  moved,
  RELEASE_NOTE,
  refusal,
  removedAt,
  SAVED,
} from '../../lib/showcase';
import { say, sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import type {
  RepositoryProfileOut,
  ShowcaseEntryOut,
  ShowcaseOut,
  TenantSummaryOut,
} from '../../lib/types';
import {
  PREVIEW_CHOICES,
  PREVIEW_DEFAULT,
  PREVIEW_LEGEND,
  type PreviewChoice,
} from '../../lib/visibility';

const required = requiredIn('Repository');

export type ShowcaseControls = {
  clear(): void;
  // Reads the switch and the featured entries and shows the card, for an Owner.
  paint(repository: TenantSummaryOut): Promise<void>;
};

// `root` is the <Repository /> article.
export function createShowcaseControls(root: HTMLElement): ShowcaseControls {
  const card = required<HTMLElement>(root, '[data-showcase]');
  const choiceBox = required<HTMLElement>(card, '[data-showcase-choice]');
  const choiceStatus = required<HTMLElement>(card, '[data-showcase-choice-status]');
  const none = required<HTMLElement>(card, '[data-featured-none]');
  const list = required<HTMLElement>(card, '[data-featured-list]');
  const count = required<HTMLElement>(card, '[data-featured-count]');
  const search = required<HTMLInputElement>(card, '[data-featured-search]');
  const results = required<HTMLElement>(card, '[data-featured-results]');
  const addNone = required<HTMLElement>(card, '[data-featured-add-none]');
  const status = required<HTMLElement>(card, '[data-featured-status]');

  required<HTMLElement>(card, '[data-showcase-heading]').textContent = LOOK_HEADING;
  required<HTMLElement>(card, '[data-showcase-explanation]').textContent = LOOK_EXPLANATION;
  required<HTMLElement>(card, '[data-featured-heading]').textContent = FEATURED_HEADING;
  required<HTMLElement>(card, '[data-featured-search-label]').textContent = ADD_LABEL;
  required<HTMLElement>(card, '[data-featured-hint]').textContent = ADD_HINT;
  required<HTMLElement>(card, '[data-featured-release-note]').textContent = RELEASE_NOTE;
  none.textContent = FEATURED_NONE;
  addNone.textContent = ADD_NONE;

  const legend = document.createElement('legend');

  legend.textContent = PREVIEW_LEGEND;
  choiceBox.append(legend);

  const radios: Partial<Record<PreviewChoice, HTMLInputElement>> = {};

  for (const choice of PREVIEW_CHOICES) {
    const row = document.createElement('label');
    const radio = document.createElement('input');

    row.className = 'field-row';
    radio.type = 'radio';
    radio.name = 'showcase-preview';
    radio.value = choice.value;
    radio.dataset.showcaseChoice = choice.value;
    row.append(radio, choice.label);
    choiceBox.append(row);
    radios[choice.value] = radio;
  }

  let shown: TenantSummaryOut | null = null;
  let featured: ShowcaseEntryOut[] = [];
  let limit = 12;
  let saved: PreviewChoice = PREVIEW_DEFAULT;
  let busy = false;
  let searching = 0;

  function chosen(): PreviewChoice {
    for (const choice of PREVIEW_CHOICES) if (radios[choice.value]?.checked) return choice.value;

    return saved;
  }

  function setChoice(value: PreviewChoice): void {
    saved = value;

    for (const choice of PREVIEW_CHOICES) {
      const radio = radios[choice.value];

      if (radio) radio.checked = choice.value === value;
    }
  }

  function setBusy(next: boolean): void {
    busy = next;

    for (const control of card.querySelectorAll<HTMLButtonElement | HTMLInputElement>(
      '[data-featured-results] button, [data-showcase-choice] input',
    )) {
      control.disabled = next;
    }

    // The list is drawn again with each button as it should be (the first cannot go up).
    if (next) {
      for (const control of list.querySelectorAll<HTMLButtonElement>('button'))
        control.disabled = true;
    } else {
      paintList();
    }
  }

  function paintList(): void {
    list.replaceChildren(
      ...featured.map((entry, index) => {
        const item = cloneRoot(root, '[data-featured-template]');
        const up = required<HTMLButtonElement>(item, '[data-up]');
        const down = required<HTMLButtonElement>(item, '[data-down]');
        const remove = required<HTMLButtonElement>(item, '[data-remove]');

        required<HTMLElement>(item, '[data-name]').textContent = entry.name;
        up.setAttribute('aria-label', actionLabel('Move up', entry.name));
        down.setAttribute('aria-label', actionLabel('Move down', entry.name));
        remove.setAttribute('aria-label', actionLabel('Remove', entry.name));
        up.disabled = index === 0;
        down.disabled = index === featured.length - 1;
        up.addEventListener('click', () => void commit(moved(featured, index, -1)));
        down.addEventListener('click', () => void commit(moved(featured, index, 1)));
        remove.addEventListener('click', () => void commit(removedAt(featured, index)));

        return item;
      }),
    );
    none.hidden = featured.length > 0;
    count.textContent = `${featuredCount(featured.length, limit)}. ${limitLine(limit)}`;
    search.disabled = !canAdd(featured, limit);
  }

  function paintResults(found: { id: string; name: string }[]): void {
    results.replaceChildren(
      ...found.map((entry) => {
        const item = cloneRoot(root, '[data-candidate-template]');
        const add = required<HTMLButtonElement>(item, '[data-add]');

        required<HTMLElement>(item, '[data-name]').textContent = entry.name;
        add.setAttribute('aria-label', actionLabel('Add', entry.name));
        add.addEventListener('click', () => {
          search.value = '';
          paintResults([]);
          void commit(added(featured, entry, limit));
        });

        return item;
      }),
    );
  }

  // Features this list, in this order, and shows what the API holds after.
  async function commit(next: ShowcaseEntryOut[]): Promise<void> {
    const repository = shown;

    if (!repository || busy) return;

    setBusy(true);
    say(status, 'Saving…');

    try {
      const out = await putShowcase(
        repository.id,
        next.map((entry) => entry.id),
      );

      if (shown !== repository) return;

      featured = out.entries;
      limit = out.limit;
      say(status, SAVED);
    } catch (cause) {
      if (shown !== repository) return;

      if (cause instanceof ApiError && refusal(cause.problemType)) {
        say(status, refusal(cause.problemType) ?? '', true);
      } else {
        sayError(status, cause);
      }

      // Whatever the refusal was, what the API holds is what stands.
      try {
        const out = await getShowcase(repository.id, { fresh: true });

        featured = out.entries;
        limit = out.limit;
      } catch {
        // The error above is already shown.
      }
    } finally {
      if (shown === repository) setBusy(false);
      else busy = false;
    }
  }

  for (const choice of PREVIEW_CHOICES) {
    radios[choice.value]?.addEventListener('change', () => {
      const repository = shown;
      const wanted = chosen();

      if (!repository || busy || wanted === saved) return;

      setBusy(true);
      say(choiceStatus, 'Saving…');

      void (async () => {
        try {
          const profile = await setPreviewChoice(repository.id, wanted);

          if (shown !== repository) return;

          setChoice(profile.preview);
          say(choiceStatus, SAVED);
        } catch (cause) {
          if (shown !== repository) return;

          // The choice is not saved: the radios go back to what is.
          setChoice(saved);
          sayError(choiceStatus, cause);
        } finally {
          if (shown === repository) setBusy(false);
          else busy = false;
        }
      })();
    });
  }

  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  search.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void find(), 250);
  });

  async function find(): Promise<void> {
    const repository = shown;
    const word = search.value.trim();
    const turn = ++searching;

    if (!repository) return;

    addNone.hidden = true;

    if (word === '') {
      paintResults([]);

      return;
    }

    try {
      const found = await searchOwnEntries(repository.id, word, Math.min(50, 10 + featured.length));

      if (turn !== searching || shown !== repository) return;

      const open = candidates(found, featured).slice(0, 10);

      paintResults(open);
      addNone.hidden = open.length > 0;
    } catch (cause) {
      if (turn === searching && shown === repository) sayError(status, cause);
    }
  }

  return {
    clear() {
      shown = null;
      searching++;
      featured = [];
      card.hidden = true;
      list.replaceChildren();
      results.replaceChildren();
      search.value = '';
      say(status, '');
      say(choiceStatus, '');
    },

    async paint(repository) {
      shown = repository;

      // Only an Owner has it, and nothing is asked of the API for anyone else.
      if (repository.role !== 'owner') {
        card.hidden = true;

        return;
      }

      let read: [RepositoryProfileOut, ShowcaseOut];

      try {
        read = await Promise.all([
          getRepositoryProfile(repository.id, { fresh: true }),
          getShowcase(repository.id, { fresh: true }),
        ]);
      } catch {
        // A card that cannot be read is not offered; the rest of the Overview does not depend on it.
        if (shown === repository) card.hidden = true;

        return;
      }

      if (shown !== repository) return;

      const [profile, showcase] = read;

      setChoice(profile.preview);
      featured = showcase.entries;
      limit = showcase.limit;
      say(status, '');
      say(choiceStatus, '');
      search.value = '';
      results.replaceChildren();
      addNone.hidden = true;
      paintList();
      card.hidden = false;
    },
  };
}
