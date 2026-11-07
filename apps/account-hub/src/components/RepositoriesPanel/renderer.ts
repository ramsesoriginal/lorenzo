// /repositories (ADR 0196, RFC 0036 §3): Shelf. A library's repositories as a list, and one
// repository's page: what it is, what is inside, what it is built on, and what the library has
// done with it, the way to copy it (ADR 0201, ./wizard.ts) and its updates (ADR 0203,
// ./updatesView.ts, ./inbox.ts). A page for a library is `?tenant=<library>`, for one of its
// repositories `&repository=<id>`, for copying it `&copy=new` or `&copy=again`, and for updates
// `&updates=1` (with or without a repository, for its updates or the library's inbox); all are
// plain links, so they can be opened, shared and gone back to.

import { pageState } from '@lorenzo/app-shell';
import { onCacheRefreshed } from '../../lib/cache';
import { BRANDING_CSS_URL } from '../../lib/config';
import { copyTargets } from '../../lib/discover';
import { getStorefront } from '../../lib/discoverApi';
import { isEditingIn } from '../../lib/editing';
import { avatarInitial, byName } from '../../lib/format';
import { showLorenzoScript } from '../../lib/lorenzoScript';
import { getMe } from '../../lib/me';
import type { PreviewLevel } from '../../lib/preview';
import { librarySource } from '../../lib/previewApi';
import { releasePlace } from '../../lib/releases';
import {
  getCopyPlan,
  listLibraryRepositories,
  listRepositoryEntries,
  listRepositoryStatGroups,
} from '../../lib/repositories';
import { retiredHere } from '../../lib/retiring';
import {
  attachmentsSentence,
  broughtSentence,
  type CopySubject,
  countsKnown,
  dayOf,
  insideCounts,
  kindLabel,
  type OutlineNode,
  outlineOf,
  PROTECTED_NOTE,
  PROTECTED_PILL,
  parentsLine,
  readShelfLocation,
  SHELF_STATE_EXPLANATION,
  SHELF_STATE_LABEL,
  SHELF_STATE_PILL,
  type ShelfState,
  shelfHref,
  shelfState,
  sortSubscriptions,
  subjectOfPublic,
  subjectOfSubscription,
  updatesHref,
} from '../../lib/shelf';
import { sayError } from '../../lib/statusLine';
import { CREATE_NOT_OPEN, roleLabel, studioHref } from '../../lib/studio';
import { cloneRoot, requiredIn } from '../../lib/template';
import { canCreateTenants, isRepository } from '../../lib/tenantKind';
import { listMyTenants, tenantPictureUrl } from '../../lib/tenants';
import type {
  RepositoryEntityOut,
  RepositoryStatGroupOut,
  SubscriptionOut,
  TenantSummaryOut,
} from '../../lib/types';
import { createPreview } from '../Preview/renderer';
import { createInbox } from './inbox';
import { createUpdatesView } from './updatesView';
import { createCopyWizard } from './wizard';

const required = requiredIn('Repositories panel');

// How long a description may run on a card before it is cut: a line, not the page.
const CARD_DESCRIPTION_LENGTH = 140;

// The picture of a repository where it has one, and its first letter where it has none. It is
// fetched with the token (ADR 0300) and answers "not found" for a repository nobody uploaded one to
// (or that this person cannot see), so the letter stays until the picture has actually loaded.
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
  void tenantPictureUrl(repository.id)
    .then((url) => {
      img.src = url;
    })
    .catch(() => {
      // The letter stands.
    });
}

function pair(list: HTMLElement, term: string, value: string): void {
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');

  dt.textContent = term;
  dd.textContent = value;
  list.append(dt, dd);
}

// A public repository to copy into a library that holds nothing of it, from its page on Discover, or
// null for one that is not listed.
async function publicSubject(repositoryId: string): Promise<CopySubject | null> {
  const storefront = await getStorefront(repositoryId);

  return storefront ? subjectOfPublic(storefront.item) : null;
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
  // What the Owner opened for a look, on a repository's page, and the entries that open in it.
  const lookInside = createPreview(required<HTMLElement>(root, '[data-detail-view]'), {
    list: false,
  });
  let lookLevel: PreviewLevel | null = null;
  const updatesViewElement = required<HTMLElement>(root, '[data-updates-view]');
  const updatesView = createUpdatesView(root, updatesViewElement);
  const inboxViewElement = required<HTMLElement>(root, '[data-inbox-view]');
  const inbox = createInbox(root, inboxViewElement);
  const yoursSection = required<HTMLElement>(root, '[data-yours]');
  const yoursList = required<HTMLElement>(root, '[data-yours-list]');
  const yoursEmpty = required<HTMLElement>(root, '[data-yours-empty]');
  const newRepository = required<HTMLElement>(root, '[data-new-repository]');
  const usedHeading = required<HTMLElement>(root, '[data-used-heading]');
  const checkUpdates = required<HTMLElement>(listView, '[data-check-updates]');
  const inboxLink = required<HTMLAnchorElement>(listView, '[data-inbox-link]');

  const detail = {
    updatesActions: required<HTMLElement>(detailView, '[data-updates-actions]'),
    updatesLink: required<HTMLAnchorElement>(detailView, '[data-updates-link]'),
    actions: required<HTMLElement>(detailView, '[data-actions]'),
    copyLink: required<HTMLAnchorElement>(detailView, '[data-copy-link]'),
    more: required<HTMLDetailsElement>(detailView, '[data-more]'),
    copyAgainLink: required<HTMLAnchorElement>(detailView, '[data-copy-again-link]'),
    picture: required<HTMLImageElement>(detailView, '[data-picture]'),
    initial: required<HTMLElement>(detailView, '[data-initial]'),
    name: required<HTMLElement>(detailView, '[data-name]'),
    state: required<HTMLElement>(detailView, '[data-state]'),
    protectedPill: required<HTMLElement>(detailView, '[data-protected-pill]'),
    protectedNote: required<HTMLElement>(detailView, '[data-protected-note]'),
    explanation: required<HTMLElement>(detailView, '[data-explanation]'),
    retired: required<HTMLElement>(detailView, '[data-retired]'),
    retiredPill: required<HTMLElement>(detailView, '[data-retired-pill]'),
    retiredSentence: required<HTMLElement>(detailView, '[data-retired-sentence]'),
    retiredMessage: required<HTMLElement>(detailView, '[data-retired-message]'),
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

  // A library, or a repository that copies from another (ADR 0205), that the person runs. Libraries
  // first, so that is what opens when the address names none.
  const [mine, me] = await Promise.all([listMyTenants(), getMe()]);
  const libraries = copyTargets(mine.items);

  // The repositories the person works on, above the ones their libraries draw on: Studio's list, as
  // cards that open Studio. Shown with the list of this page, not with a repository's or a copy.
  const worksOn = mine.items.filter(isRepository).sort((a, b) => byName(a.name, b.name));
  const mayMake = canCreateTenants(me);
  const showYours = worksOn.length > 0 || mayMake || libraries.length === 0;

  yoursList.replaceChildren(
    ...worksOn.map((repository) => {
      const item = cloneRoot(root, '[data-yours-item-template]');
      const link = required<HTMLAnchorElement>(item, '[data-link]');

      link.textContent = repository.name;
      link.href = studioHref(repository.slug);
      required<HTMLElement>(item, '[data-role]').textContent = roleLabel(repository.role);

      return item;
    }),
  );
  yoursEmpty.hidden = worksOn.length > 0;
  required<HTMLElement>(root, '[data-create-closed]').hidden = mayMake;
  required<HTMLElement>(root, '[data-create-closed]').textContent = CREATE_NOT_OPEN;
  newRepository.hidden = !mayMake;

  // Whether that group (and the heading of the ones below it) is shown: only on this page's list.
  function landing(on: boolean): void {
    yoursSection.hidden = !(on && showYours);
    usedHeading.hidden = !(on && showYours);
  }

  if (libraries.length === 0) {
    noLibrary.hidden = false;
    landing(true);
    root.hidden = false;

    return;
  }

  librarySelect.replaceChildren(
    ...libraries.map((library) => {
      const option = document.createElement('option');

      option.value = library.id;
      option.textContent = isRepository(library) ? `${library.name} (repository)` : library.name;

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

        // Held through a public repository built on it (RFC 0051 H3, ADR 0434): a pill, and no name.
        const protectedBox = required<HTMLElement>(card, '[data-protected-card]');

        protectedBox.hidden = !subscription.protected;
        required<HTMLElement>(card, '[data-protected-pill]').textContent = PROTECTED_PILL;

        // Retired by its Owner (ADR 0384): said on the card, with the Owner's words.
        const retired = retiredHere(subscription.deprecated, subscription.copied_at !== null);
        const retiredBox = required<HTMLElement>(card, '[data-retired]');

        retiredBox.hidden = retired === null;

        if (retired) {
          required<HTMLElement>(card, '[data-retired-pill]').textContent = retired.pill;
          required<HTMLElement>(card, '[data-retired-message]').textContent = retired.message ?? '';
        }

        return card;
      }),
    );
    empty.hidden = subscriptions.length > 0;
    // Nothing offered to this library: a page state with the mascot, in words either way.
    empty.replaceChildren(
      ...(subscriptions.length === 0
        ? [
            pageState(BRANDING_CSS_URL, {
              art: 'empty-entries',
              level: 2,
              title: 'No repository offered yet',
              text: 'No repository is offered to this library yet. The owner of a repository invites a library to it; ask them to invite this one.',
              alt: 'An empty shelf',
            }),
          ]
        : []),
    );
    // The inbox checks every copy, so it is offered where there is one.
    checkUpdates.hidden = !subscriptions.some((s) => s.copied_at !== null);
    inboxLink.href = updatesHref(library.slug);
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
        // An entry opens in the dialog wherever the Owner opened something to look at.
        const look = required<HTMLButtonElement>(item, '[data-look]');

        look.hidden = lookLevel === null || lookLevel === 'off';
        look.setAttribute('aria-label', `Look at ${entry.name}`);
        look.addEventListener('click', () => void lookInside.open(entry.id));

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
    // A protected repository held through another is not looked inside: it is read only as a step of
    // the copy of the repository that brings it (ADR 0434).
    const through = subscription.protected === true;
    const canLookInside =
      !through && (state === 'not-copied' || state === 'copied' || state === 'update-announced');
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
    lookLevel = null;
    lookInside.hide();

    back.href = shelfHref(library.slug);
    showPicture(detail.picture, detail.initial, repository);
    detail.name.textContent = repository.name;
    stateElement(detail.state, state);
    detail.protectedPill.hidden = !through;
    detail.protectedPill.textContent = PROTECTED_PILL;
    detail.protectedNote.hidden = !through;
    detail.protectedNote.textContent = PROTECTED_NOTE;
    // Retired by its Owner (ADR 0384): the library keeps what it copied and its updates, cannot copy
    // it again, and reads the Owner's words. A library that never copied it is told only that.
    const retired = retiredHere(subscription.deprecated, subscription.copied_at !== null);

    detail.retired.hidden = retired === null;
    detail.explanation.textContent = SHELF_STATE_EXPLANATION[state];
    detail.explanation.hidden = retired !== null && state === 'not-copied';

    if (retired) {
      detail.retiredPill.textContent = retired.pill;
      detail.retiredSentence.textContent = retired.sentence;
      detail.retiredMessage.textContent = retired.message ?? '';
      detail.retiredMessage.hidden = retired.message === null;
    }

    // Updates: for a copy of what is still offered and published.
    detail.updatesActions.hidden = state !== 'copied' && state !== 'update-announced';
    detail.updatesLink.href = updatesHref(library.slug, repository.id);

    // Copying: a first copy of what is offered and not yet copied, another of what is copied.
    detail.actions.hidden = state !== 'not-copied' || retired !== null || through;
    detail.copyLink.href = shelfHref(library.slug, repository.id, 'new');
    detail.more.hidden = subscription.copied_at === null || retired !== null || through;
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
    // Which release it took, and which is the latest (RFC 0037): said in words, never as "up to date".
    const place = releasePlace(subscription);

    if (place?.took) pair(detail.history, 'Last updated from release', place.took);
    if (place) pair(detail.history, 'Latest release', place.latest);
    if (repository.published_at) pair(detail.history, 'Published', dayOf(repository.published_at));

    detail.brought.textContent = subscription.contributed
      ? broughtSentence(subscription.contributed)
      : '';
    detail.brought.hidden = !subscription.contributed;
    detail.historySection.hidden = detail.history.children.length === 0;

    // A retired repository has no plan to count (nothing can be copied), but its holders read it as
    // they did: its entries and stat groups, and what its Owner opened for a look.
    const browsable = Boolean(step) || (retired !== null && canLookInside);

    // What the Owner opened for a look, for a repository that can be looked inside.
    if (browsable) {
      const looking = { libraryId: library.id, repositoryId: repository.id };

      void lookInside
        .show(
          librarySource(library.id, repository.id),
          'holder',
          () => shown?.repositoryId === looking.repositoryId && turn === latest,
        )
        .then((level) => {
          lookLevel = level;
          if (entries.loaded.length > 0) paintEntries();
        });
    }

    // Entries and stat groups are read when their section is opened.
    detail.entriesSection.hidden = !browsable;
    detail.statGroupsSection.hidden = !browsable;
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
    // it stands; otherwise the repository's own page. A repository the library holds nothing of
    // is copied only if it is public (ADR 0292): Discover sends a library here for it.
    const subject =
      location.copy && wanted
        ? subjectOfSubscription(wanted, library)
        : location.copy === 'new' && location.repository
          ? await publicSubject(location.repository)
          : null;

    if (turn !== latest) return;

    if (subject && location.copy) {
      const opened = await wizard.open(library, subject, location.copy, () => turn === latest);

      if (turn !== latest) return;

      if (opened) {
        shown = null;
        updatesView.close();
        inbox.close();
        updatesViewElement.hidden = true;
        inboxViewElement.hidden = true;
        landing(false);
        listView.hidden = true;
        detailView.hidden = true;
        copyView.hidden = false;

        return;
      }
    }

    // A repository's updates, or the library's inbox, where the address asks for them: a
    // repository's only when it can be checked from where it stands.
    if (location.updates) {
      let opened = false;

      if (wanted) {
        opened = await updatesView.open(library, wanted, () => turn === latest);
      } else if (!location.repository) {
        inbox.open(library, subscriptions, () => turn === latest);
        opened = true;
      }

      if (turn !== latest) return;

      if (opened) {
        shown = null;
        wizard.close();
        copyView.hidden = true;
        listView.hidden = true;
        detailView.hidden = true;
        updatesViewElement.hidden = !wanted;
        inboxViewElement.hidden = !!wanted;
        landing(false);

        return;
      }
    }

    wizard.close();
    updatesView.close();
    inbox.close();
    copyView.hidden = true;
    updatesViewElement.hidden = true;
    inboxViewElement.hidden = true;

    if (wanted) {
      await paintDetail(library, wanted, turn);

      if (turn !== latest) return;

      landing(false);
      listView.hidden = true;
      detailView.hidden = false;
    } else {
      shown = null;
      paintCards(library, subscriptions);
      landing(true);
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
