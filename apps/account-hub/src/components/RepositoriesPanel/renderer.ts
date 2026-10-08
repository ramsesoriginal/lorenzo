// /repositories (ADR 0196, RFC 0036 §3): Shelf. A library's repositories as a list, and one
// repository's page: what it is, what is inside, what it is built on, and what the library has
// done with it, and the way to copy it (ADR 0201, ./wizard.ts); updating is a later slice. A page
// for a library is `?tenant=<library>`, for one of its repositories `&repository=<id>`, and for
// copying it `&copy=new` or `&copy=again`; all are plain links, so they can be opened, shared and
// gone back to.

import { onCacheRefreshed } from '../../lib/cache';
import { isEditingIn } from '../../lib/editing';
import { avatarInitial, byName, isTenantAdmin } from '../../lib/format';
import { showLorenzoScript } from '../../lib/lorenzoScript';
import {
  getCopyPlan,
  listLibraryRepositories,
  listRepositoryEntries,
  listRepositoryStatGroups,
} from '../../lib/repositories';
import {
  attachmentsSentence,
  broughtSentence,
  countsKnown,
  dayOf,
  insideCounts,
  kindLabel,
  type OutlineNode,
  outlineOf,
  parentsLine,
  readShelfLocation,
  SHELF_STATE_EXPLANATION,
  SHELF_STATE_LABEL,
  SHELF_STATE_PILL,
  type ShelfState,
  shelfHref,
  shelfState,
  sortSubscriptions,
} from '../../lib/shelf';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { listMyTenants, tenantPictureUrl } from '../../lib/tenants';
import type {
  RepositoryEntityOut,
  RepositoryStatGroupOut,
  SubscriptionOut,
  TenantSummaryOut,
} from '../../lib/types';
import { createCopyWizard } from './wizard';

const required = requiredIn('Repositories panel');

// How long a description may run on a card before it is cut: a line, not the page.
const CARD_DESCRIPTION_LENGTH = 140;

// The picture of a repository where it has one, and its first letter where it has none. The
// picture's address answers "not found" for a repository nobody uploaded one to, so the letter
// stays until the picture has actually loaded.
function showPicture(
  img: HTMLImageElement,
  initial: HTMLElement,
  repository: { id: string; name: string },
): void {
  initial.textContent = avatarInitial(repository.name);
  initial.hidden = false;
  img.hidden = true;
  img.addEventListener('load', () => {
    img.hidden = false;
    initial.hidden = true;
  });
  img.src = tenantPictureUrl(repository.id);
}

function pair(list: HTMLElement, term: string, value: string): void {
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');

  dt.textContent = term;
  dd.textContent = value;
  list.append(dt, dd);
}

function stateElement(element: HTMLElement, state: ShelfState): void {
  element.className = SHELF_STATE_PILL[state];
  element.textContent = SHELF_STATE_LABEL[state];
}

// The first line of a description, cut to a card's size.
function firstLine(text: string): string {
  const line = text.trim().split('\n', 1)[0] ?? '';

  return line.length > CARD_DESCRIPTION_LENGTH
    ? `${line.slice(0, CARD_DESCRIPTION_LENGTH - 1)}…`
    : line;
}

// `root` is the <RepositoriesPanel /> block. It is built, and shown, once; the first load's
// failure rejects, for the page to show. Moving between the list and a repository, and between
// libraries, reads the address and paints again.
export async function renderRepositoriesPanel(root: HTMLElement): Promise<void> {
  const error = required<HTMLElement>(root, '[data-error]');
  const noLibrary = required<HTMLElement>(root, '[data-no-library]');
  const picker = required<HTMLElement>(root, '[data-library-picker]');
  const librarySelect = required<HTMLSelectElement>(root, '[data-library]');
  const listView = required<HTMLElement>(root, '[data-list-view]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const list = required<HTMLElement>(root, '[data-list]');
  const detailView = required<HTMLElement>(root, '[data-detail-view]');
  const back = required<HTMLAnchorElement>(root, '[data-back]');
  const copyView = required<HTMLElement>(root, '[data-copy-view]');
  const wizard = createCopyWizard(root, copyView);

  const detail = {
    actions: required<HTMLElement>(detailView, '[data-actions]'),
    copyLink: required<HTMLAnchorElement>(detailView, '[data-copy-link]'),
    more: required<HTMLDetailsElement>(detailView, '[data-more]'),
    copyAgainLink: required<HTMLAnchorElement>(detailView, '[data-copy-again-link]'),
    picture: required<HTMLImageElement>(detailView, '[data-picture]'),
    initial: required<HTMLElement>(detailView, '[data-initial]'),
    name: required<HTMLElement>(detailView, '[data-name]'),
    state: required<HTMLElement>(detailView, '[data-state]'),
    explanation: required<HTMLElement>(detailView, '[data-explanation]'),
    description: required<HTMLElement>(detailView, '[data-description]'),
    insideSection: required<HTMLElement>(detailView, '[data-inside-section]'),
    inside: required<HTMLElement>(detailView, '[data-inside]'),
    insideUnknown: required<HTMLElement>(detailView, '[data-inside-unknown]'),
    attachments: required<HTMLElement>(detailView, '[data-attachments]'),
    builtOnSection: required<HTMLElement>(detailView, '[data-built-on-section]'),
    outline: required<HTMLElement>(detailView, '[data-outline]'),
    builtOnNone: required<HTMLElement>(detailView, '[data-built-on-none]'),
    historySection: required<HTMLElement>(detailView, '[data-history-section]'),
    history: required<HTMLElement>(detailView, '[data-history]'),
    brought: required<HTMLElement>(detailView, '[data-brought]'),
    entriesSection: required<HTMLDetailsElement>(detailView, '[data-entries-section]'),
    entrySearch: required<HTMLInputElement>(detailView, '[data-entry-search]'),
    entries: required<HTMLElement>(detailView, '[data-entries]'),
    entriesEmpty: required<HTMLElement>(detailView, '[data-entries-empty]'),
    entriesMore: required<HTMLButtonElement>(detailView, '[data-entries-more]'),
    entriesError: required<HTMLElement>(detailView, '[data-entries-error]'),
    statGroupsSection: required<HTMLDetailsElement>(detailView, '[data-stat-groups-section]'),
    statGroups: required<HTMLElement>(detailView, '[data-stat-groups]'),
    statGroupsEmpty: required<HTMLElement>(detailView, '[data-stat-groups-empty]'),
    statGroupsError: required<HTMLElement>(detailView, '[data-stat-groups-error]'),
  };

  const libraries = (await listMyTenants('play')).items
    .filter(isTenantAdmin)
    .sort((a, b) => byName(a.name, b.name));

  if (libraries.length === 0) {
    noLibrary.hidden = false;
    root.hidden = false;

    return;
  }

  librarySelect.replaceChildren(
    ...libraries.map((library) => {
      const option = document.createElement('option');

      option.value = library.id;
      option.textContent = library.name;

      return option;
    }),
  );
  picker.hidden = libraries.length === 1;

  const libraryFor = (key: string | null): TenantSummaryOut =>
    libraries.find((library) => library.slug === key || library.id === key) ?? libraries[0];

  // What the repository page's lazily loaded parts need to know about the repository on show.
  let shown: { libraryId: string; repositoryId: string } | null = null;
  const entries = { loaded: [] as RepositoryEntityOut[], page: 0, total: 0, query: '' };
  let statGroupsLoaded = false;

  // Only the newest show paints.
  let latest = 0;

  function paintCards(library: TenantSummaryOut, subscriptions: SubscriptionOut[]): void {
    list.replaceChildren(
      ...sortSubscriptions(subscriptions).map((subscription) => {
        const card = cloneRoot(root, '[data-card-template]');
        const { repository } = subscription;
        const link = required<HTMLAnchorElement>(card, '[data-link]');

        showPicture(
          required<HTMLImageElement>(card, '[data-picture]'),
          required<HTMLElement>(card, '[data-initial]'),
          repository,
        );
        link.textContent = repository.name;
        link.href = shelfHref(library.slug, repository.id);
        required<HTMLElement>(card, '[data-description]').textContent = firstLine(
          repository.description,
        );
        stateElement(required<HTMLElement>(card, '[data-state]'), shelfState(subscription));

        return card;
      }),
    );
    empty.hidden = subscriptions.length > 0;
  }

  function outlineItem(node: OutlineNode, current: boolean): HTMLElement {
    const item = cloneRoot(root, '[data-outline-node-template]');
    const box = required<HTMLElement>(item, '.outline-node');
    const state = required<HTMLElement>(item, '[data-state]');
    const hint = required<HTMLElement>(item, '[data-hint]');

    required<HTMLElement>(item, '[data-name]').textContent = node.name;
    state.textContent = node.label;
    state.className = node.state === 'copied' ? 'pill pill-success' : 'outline-state';
    if (node.state === 'invited') state.className = 'pill';
    if (node.state === 'not-invited' || node.state === 'not-published') {
      state.className = 'pill';
      box.classList.add('outline-node--muted');
    }
    if (current) box.setAttribute('aria-current', 'true');
    if (node.hint) {
      hint.textContent = node.hint;
      hint.hidden = false;
    }

    return item;
  }

  function paintEntries(): void {
    const names = new Map(entries.loaded.map((entry) => [entry.id, entry.name]));

    detail.entries.replaceChildren(
      ...entries.loaded.map((entry) => {
        const item = cloneRoot(root, '[data-entry-template]');

        required<HTMLElement>(item, '[data-name]').textContent = entry.name;
        required<HTMLElement>(item, '[data-kinds]').textContent = entry.kinds
          .map(kindLabel)
          .join(', ');
        required<HTMLElement>(item, '[data-parents]').textContent = parentsLine(entry, names) ?? '';

        return item;
      }),
    );
    detail.entriesEmpty.hidden = entries.loaded.length > 0;
    detail.entriesMore.hidden = entries.loaded.length >= entries.total;
  }

  async function loadEntries(reset: boolean): Promise<void> {
    const target = shown;

    if (!target) return;

    const query = detail.entrySearch.value.trim();

    if (reset) {
      entries.loaded = [];
      entries.page = 0;
      entries.total = 0;
      entries.query = query;
    }

    const page = entries.page + 1;

    try {
      const result = await listRepositoryEntries(target.libraryId, target.repositoryId, {
        q: entries.query,
        page,
      });

      if (shown !== target || entries.query !== query) return;

      detail.entriesError.hidden = true;
      entries.loaded.push(...result.items);
      entries.page = page;
      entries.total = result.total;
      paintEntries();
    } catch (cause) {
      sayError(detail.entriesError, cause);
    }
  }

  async function loadStatGroups(): Promise<void> {
    const target = shown;

    if (!target || statGroupsLoaded) return;

    try {
      const groups: RepositoryStatGroupOut[] = await listRepositoryStatGroups(
        target.libraryId,
        target.repositoryId,
      );

      if (shown !== target) return;

      statGroupsLoaded = true;
      detail.statGroupsError.hidden = true;
      detail.statGroups.replaceChildren(
        ...groups.map((group) => {
          const item = cloneRoot(root, '[data-stat-group-template]');

          required<HTMLElement>(item, '[data-name]').textContent = group.name;
          required<HTMLElement>(item, '[data-stats]').textContent =
            group.definitions.length === 0
              ? 'No stats'
              : group.definitions
                  .map((stat) =>
                    stat.value_type === 'enum' && stat.enum_values.length > 0
                      ? `${stat.name} (${stat.enum_values.join(', ')})`
                      : stat.name,
                  )
                  .join(', ');

          return item;
        }),
      );
      detail.statGroupsEmpty.hidden = groups.length > 0;
    } catch (cause) {
      sayError(detail.statGroupsError, cause);
    }
  }

  async function paintDetail(
    library: TenantSummaryOut,
    subscription: SubscriptionOut,
    turn: number,
  ): Promise<void> {
    const { repository } = subscription;
    const state = shelfState(subscription);
    // Only a repository that is offered and published can be looked inside.
    const canLookInside =
      state === 'not-copied' || state === 'copied' || state === 'update-announced';
    const plan = canLookInside ? await getCopyPlan(library.id, repository.id) : null;

    if (turn !== latest) return;

    shown = { libraryId: library.id, repositoryId: repository.id };
    entries.loaded = [];
    entries.page = 0;
    entries.total = 0;
    entries.query = '';
    statGroupsLoaded = false;
    detail.entrySearch.value = '';
    detail.entries.replaceChildren();
    detail.statGroups.replaceChildren();
    detail.entriesSection.open = false;
    detail.statGroupsSection.open = false;

    back.href = shelfHref(library.slug);
    showPicture(detail.picture, detail.initial, repository);
    detail.name.textContent = repository.name;
    stateElement(detail.state, state);
    detail.explanation.textContent = SHELF_STATE_EXPLANATION[state];

    // Copying: a first copy of what is offered and not yet copied, another of what is copied.
    detail.actions.hidden = state !== 'not-copied';
    detail.copyLink.href = shelfHref(library.slug, repository.id, 'new');
    detail.more.hidden = subscription.copied_at === null;
    detail.more.open = false;
    detail.copyAgainLink.href = shelfHref(library.slug, repository.id, 'again');
    showLorenzoScript(detail.description, repository.description);

    // What is inside, from the plan's step for this repository.
    const outline = plan ? outlineOf(plan, repository.id) : null;
    const step = plan?.steps.find((candidate) => candidate.repository_id === repository.id);

    detail.insideSection.hidden = !step;
    detail.inside.replaceChildren();
    detail.attachments.hidden = true;
    detail.insideUnknown.hidden = true;

    if (step && plan && countsKnown(plan, repository.id)) {
      for (const count of insideCounts(step)) pair(detail.inside, count.label, String(count.value));

      const sentence = attachmentsSentence(step.attachments);

      detail.attachments.textContent = sentence ?? '';
      detail.attachments.hidden = !sentence;
    } else if (step) {
      // The API counts nothing when a repository this one is built on is not offered to the
      // library, and counts a copy's contents once, not again: say so, never a row of zeros.
      detail.insideUnknown.textContent = step.already_copied
        ? 'Your library has copied this repository, so it is not counted again. What it took is under "Your library and this repository".'
        : 'What is inside is counted once every repository this one is built on is offered to your library.';
      detail.insideUnknown.hidden = false;
    }

    // What it is built on, as an outline: this repository first, what it builds on beneath it.
    detail.builtOnSection.hidden = !outline;
    detail.outline.replaceChildren();

    if (outline) {
      const top = outlineItem(outline.root, true);

      if (outline.builtOn.length > 0) {
        const children = document.createElement('ul');

        children.append(...outline.builtOn.map((node) => outlineItem(node, false)));
        top.append(children);
      }

      detail.outline.append(top);
      detail.builtOnNone.hidden = outline.builtOn.length > 0;
    }

    // The library's history with it.
    detail.history.replaceChildren();

    if (subscription.granted_at) pair(detail.history, 'Invited', dayOf(subscription.granted_at));
    if (subscription.copied_at) pair(detail.history, 'Copied', dayOf(subscription.copied_at));
    if (subscription.synced_at) pair(detail.history, 'Last updated', dayOf(subscription.synced_at));
    if (repository.published_at) pair(detail.history, 'Published', dayOf(repository.published_at));

    detail.brought.textContent = subscription.contributed
      ? broughtSentence(subscription.contributed)
      : '';
    detail.brought.hidden = !subscription.contributed;
    detail.historySection.hidden = detail.history.children.length === 0;

    // Entries and stat groups are read when their section is opened.
    detail.entriesSection.hidden = !step;
    detail.statGroupsSection.hidden = !step;
    detail.entriesError.hidden = true;
    detail.statGroupsError.hidden = true;
    detail.entriesEmpty.hidden = true;
    detail.entriesMore.hidden = true;
    detail.statGroupsEmpty.hidden = true;
  }

  async function show(): Promise<void> {
    const turn = ++latest;
    const location = readShelfLocation(window.location.search);
    const library = libraryFor(location.library);

    librarySelect.value = library.id;

    const subscriptions = await listLibraryRepositories(library.id);

    if (turn !== latest) return;

    const wanted = location.repository
      ? subscriptions.find(
          (s) =>
            s.repository.id === location.repository || s.repository.slug === location.repository,
        )
      : undefined;

    error.hidden = true;

    // The copy wizard, where the address asks for it and the repository can be copied from where
    // it stands; otherwise the repository's own page.
    if (wanted && location.copy) {
      const opened = await wizard.open(library, wanted, location.copy, () => turn === latest);

      if (turn !== latest) return;

      if (opened) {
        shown = null;
        listView.hidden = true;
        detailView.hidden = true;
        copyView.hidden = false;

        return;
      }
    }

    wizard.close();
    copyView.hidden = true;

    if (wanted) {
      await paintDetail(library, wanted, turn);

      if (turn !== latest) return;

      listView.hidden = true;
      detailView.hidden = false;
    } else {
      shown = null;
      paintCards(library, subscriptions);
      detailView.hidden = true;
      listView.hidden = false;
    }
  }

  async function reload(): Promise<void> {
    try {
      await show();
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // Links stay links: a modified click opens them as the browser would. A plain one moves within
  // the page and keeps the address true.
  root.addEventListener('click', (event) => {
    const link = (event.target as Element).closest<HTMLAnchorElement>('a[data-link], a[data-back]');

    if (!link || event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    event.preventDefault();
    window.history.pushState(null, '', link.href);
    void reload();
  });

  librarySelect.addEventListener('change', () => {
    window.history.pushState(null, '', shelfHref(libraryFor(librarySelect.value).slug));
    void reload();
  });

  window.addEventListener('popstate', () => void reload());

  detail.entriesSection.addEventListener('toggle', () => {
    if (detail.entriesSection.open && entries.page === 0) void loadEntries(true);
  });
  detail.statGroupsSection.addEventListener('toggle', () => {
    if (detail.statGroupsSection.open) void loadStatGroups();
  });
  detail.entriesMore.addEventListener('click', () => void loadEntries(false));

  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  detail.entrySearch.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void loadEntries(true), 250);
  });

  // A change that arrives in the background repaints the list, not a repository's page, whose
  // opened parts and search would be lost.
  onCacheRefreshed(() => {
    if (!listView.hidden && !isEditingIn(root)) void reload();
  });

  await show();
  root.hidden = false;
}
