import { beingNamed, unknownSlug } from '../../lib/addresses';
import { renderBeingSuggestions, searchBeingsAndGroups } from '../../lib/beingPicker';
import { listMyCharacters } from '../../lib/characters';
import { groupsOf } from '../../lib/groups';
import { defaultHolder, getLastHolder, type Holder, rememberHolder } from '../../lib/lastHolder';
import type { BeingRef, CharacterSummary } from '../../lib/types';

export type HolderPickerOptions = {
  root: HTMLElement;
  tenantId: string;
  viewerIsGm: boolean;
  // `viewing` says whose board it is, or null for the viewer's own character.
  onViewHolder(entityId: string, viewing: string | null): void;
  onViewUnowned(viewing: string): void;
  // A link was hovered or focused: its board is likely next.
  onPrefetch(entityId: string): void;
  onError(message: string): void;
};

export type RenderedHolderPicker = {
  // Lists the viewer's characters and their groups, and opens one.
  load(): Promise<void>;
  myCharacters(): CharacterSummary[];
  // Whether the id is one of the viewer's characters or those characters' groups: what they
  // may give things back from (ADR 0124).
  isMine(entityId: string): boolean;
  destroy(): void;
};

type PickerTab = 'characters' | 'browse' | 'unowned';

const TABS: PickerTab[] = ['characters', 'browse', 'unowned'];

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error));

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Holder picker is missing ${selector}.`);
  }

  return element;
}

export function renderHolderPicker(options: HolderPickerOptions): RenderedHolderPicker {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  // The address as it was when the page opened; later, the board puts its own into the URL.
  const params = new URLSearchParams(window.location.search);

  const tablist = required<HTMLElement>(root, '[data-tablist]');
  const loading = required<HTMLElement>(root, '[data-loading]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const strip = required<HTMLUListElement>(root, '[data-holders]');
  const holderTemplate = required<HTMLTemplateElement>(root, '[data-holder-template]');
  const browseCombobox = required<HTMLElement>(root, '[data-browse-combobox]');
  const browseSearch = required<HTMLInputElement>(root, '[data-browse-search]');
  const browseSuggestions = required<HTMLUListElement>(root, '[data-browse-suggestions]');
  const browseRawId = required<HTMLInputElement>(root, '[data-browse-raw-id]');
  const browseRawIdButton = required<HTMLButtonElement>(root, '[data-browse-raw-id-button]');

  const tabs = Object.fromEntries(
    TABS.map((tab) => [tab, required<HTMLButtonElement>(root, `[data-tab="${tab}"]`)]),
  ) as Record<PickerTab, HTMLButtonElement>;
  const panels = Object.fromEntries(
    TABS.map((tab) => [tab, required<HTMLElement>(root, `[data-panel="${tab}"]`)]),
  ) as Record<PickerTab, HTMLElement>;

  let characters: CharacterSummary[] = [];
  const holderIds = new Set<string>();

  // Every character and group in the list, and how to open its board.
  const holders: { holder: Holder; open: (address: boolean) => void }[] = [];

  // Three ways to pick whose inventory the board shows, as tabs rather than three stacked
  // sections. A player only has their characters, so for them there's no tab bar at all.
  if (options.viewerIsGm) {
    tablist.hidden = false;
    tabs.browse.hidden = false;
    tabs.unowned.hidden = false;
  }

  function selectTab(selected: PickerTab) {
    for (const tab of TABS) {
      tabs[tab].setAttribute('aria-selected', String(tab === selected));
      panels[tab].hidden = tab !== selected;
    }
  }

  // Marks `link` as the board shown, among every character and group in the list.
  function pressOnly(link: HTMLAnchorElement | null) {
    for (const el of strip.querySelectorAll('a')) {
      el.setAttribute('aria-pressed', String(el === link));
    }
  }

  // Puts `holder` into the URL as ?character= or ?group=, by id.
  function addressHolder(holder: Holder) {
    const url = new URL(window.location.href);

    url.searchParams.set(holder.kind, holder.id);
    url.searchParams.delete(holder.kind === 'character' ? 'group' : 'character');
    window.history.replaceState({}, '', url);
  }

  // `address` is false when the URL already names it, perhaps by slug (ADR 0135).
  function selectCharacter(character: CharacterSummary, link: HTMLAnchorElement, address = true) {
    const holder: Holder = { kind: 'character', id: character.entity_id };

    pressOnly(link);
    rememberHolder(tenantId, holder);

    if (address) addressHolder(holder);

    options.onViewHolder(character.entity_id, null);
  }

  // A group one of your characters belongs to, and what it owns (ADR 0124).
  function selectGroup(group: BeingRef, link: HTMLAnchorElement, address = true) {
    const holder: Holder = { kind: 'group', id: group.entity_id };

    pressOnly(link);
    rememberHolder(tenantId, holder);

    if (address) addressHolder(holder);

    options.onViewHolder(group.entity_id, `Viewing what ${group.name} holds.`);
  }

  function openHolder(wanted: Holder | null, address = true) {
    const entry = wanted
      ? holders.find((e) => e.holder.kind === wanted.kind && e.holder.id === wanted.id)
      : undefined;

    entry?.open(address);
  }

  // With no character or group named, the board opens the one last opened on this library,
  // else your only character (ADR 0134).
  function openDefaultHolder() {
    openHolder(
      defaultHolder(
        holders.map((e) => e.holder),
        getLastHolder(tenantId),
      ),
    );
  }

  // The character or group the URL names, by id or by slug (ADR 0135): undefined if it names
  // none, null if what it names isn't there.
  async function addressedHolder(): Promise<Holder | null | undefined> {
    const character = params.get('character');
    const group = params.get('group');
    const value = character ?? group;

    if (!value) return undefined;

    const named = await beingNamed(tenantId, value).catch(() => null);

    return named ? { kind: character ? 'character' : 'group', id: named.entity_id } : null;
  }

  // Adds a link to a board (?character= or ?group=) to the list, a group marked as one.
  function addHolder(
    holder: { entity_id: string; name: string },
    param: 'character' | 'group',
    select: (link: HTMLAnchorElement, address: boolean) => void,
  ) {
    const fragment = holderTemplate.content.cloneNode(true) as DocumentFragment;
    const item = required<HTMLLIElement>(fragment, 'li');
    const link = required<HTMLAnchorElement>(fragment, '[data-name]');
    const groupBadge = required<HTMLElement>(fragment, '[data-group]');

    const url = new URL(window.location.href);

    url.searchParams.set(param, holder.entity_id);
    url.searchParams.delete(param === 'character' ? 'group' : 'character');
    link.href = url.href;
    link.textContent = holder.name;
    link.setAttribute('aria-pressed', String(holder.entity_id === params.get(param)));
    link.addEventListener(
      'click',
      (event) => {
        event.preventDefault();
        select(link, true);
      },
      { signal },
    );
    link.addEventListener('mouseenter', () => options.onPrefetch(holder.entity_id), { signal });
    link.addEventListener('focus', () => options.onPrefetch(holder.entity_id), { signal });
    groupBadge.hidden = param !== 'group';

    strip.append(item);
    holders.push({
      holder: { kind: param, id: holder.entity_id },
      open: (address) => select(link, address),
    });
  }

  async function loadGroups(mine: CharacterSummary[]) {
    const groups = await groupsOf(tenantId, mine).catch(() => []);

    for (const group of groups) {
      holderIds.add(group.entity_id);
      addHolder(group, 'group', (link, address) => selectGroup(group, link, address));
    }
  }

  async function load() {
    // Looked up alongside the list, when it's a slug.
    const addressing = addressedHolder();

    try {
      const page = await listMyCharacters(tenantId);

      characters = page.items;

      for (const character of characters) holderIds.add(character.entity_id);

      loading.hidden = true;

      if (characters.length === 0) {
        empty.hidden = false;
        return;
      }

      for (const character of characters) {
        addHolder(character, 'character', (link, address) =>
          selectCharacter(character, link, address),
        );
      }

      await loadGroups(characters);

      // The URL wins, and keeps naming it as it did; otherwise the board opens one by itself
      // (ADR 0134, 0135).
      const named = await addressing;

      if (named === undefined) {
        openDefaultHolder();
      } else {
        openHolder(named, false);
      }
    } catch (cause) {
      loading.hidden = true;
      error.hidden = false;
      error.textContent = reason(cause);
    }
  }

  // GM only: browse any being's inventory (ADR 0078: PCs, NPCs and bare beings alike) by
  // search, or by an id or slug typed in. None of the viewer's own characters is the one
  // shown then.
  function browseBeing(being: BeingRef) {
    pressOnly(null);
    options.onViewHolder(being.entity_id, `Viewing ${being.name}'s inventory.`);
  }

  tabs.characters.addEventListener(
    'click',
    () => {
      selectTab('characters');

      // Back from browsing, with none of yours shown: open the one you had (ADR 0134).
      if (!strip.querySelector('a[aria-pressed="true"]')) openDefaultHolder();
    },
    { signal },
  );
  tabs.browse.addEventListener('click', () => selectTab('browse'), { signal });
  tabs.unowned.addEventListener(
    'click',
    () => {
      selectTab('unowned');
      pressOnly(null);
      options.onViewUnowned('Viewing unowned items.');
    },
    { signal },
  );

  let browseDebounce: ReturnType<typeof setTimeout> | undefined;

  browseSearch.addEventListener(
    'input',
    () => {
      clearTimeout(browseDebounce);

      const query = browseSearch.value.trim();

      if (!query) {
        browseSuggestions.hidden = true;
        browseSuggestions.replaceChildren();
        return;
      }

      browseDebounce = setTimeout(async () => {
        const { beings, groups } = await searchBeingsAndGroups(tenantId, query);

        renderBeingSuggestions(
          browseSuggestions,
          beings,
          (being) => {
            browseSearch.value = being.name;
            browseSuggestions.hidden = true;
            browseBeing(being);
          },
          groups,
        );
      }, 200);
    },
    { signal },
  );

  browseSearch.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape') browseSuggestions.hidden = true;
    },
    { signal },
  );

  document.addEventListener(
    'click',
    (event) => {
      if (!browseCombobox.contains(event.target as Node)) browseSuggestions.hidden = true;
    },
    { signal },
  );

  // An id, or a slug (ADR 0135).
  browseRawIdButton.addEventListener(
    'click',
    async () => {
      const value = browseRawId.value.trim();

      if (!value) return;

      try {
        const being = await beingNamed(tenantId, value);

        if (being) {
          browseBeing(being);
        } else {
          options.onError(unknownSlug(value));
        }
      } catch (cause) {
        options.onError(reason(cause));
      }
    },
    { signal },
  );

  return {
    load,
    myCharacters: () => characters,
    isMine: (entityId) => holderIds.has(entityId),

    destroy() {
      clearTimeout(browseDebounce);
      controller.abort();
    },
  };
}
