import { closeDialog, fadeOnDismiss, openDialog, openMenu } from '@lorenzo/app-shell';
import { beingNamed, unknownSlug } from '../../lib/addresses';
import { searchBeingsAndGroups } from '../../lib/beingPicker';
import { listMyCharacters } from '../../lib/characters';
import { BRANDING_CSS_URL } from '../../lib/config';
import { errorMessage } from '../../lib/errorMessage';
import { DEFAULT_GM_WORDS, gmWordsOfBeing } from '../../lib/gmTitle';
import { groupsOf } from '../../lib/groups';
import { defaultHolder, getLastHolder, type Holder, rememberHolder } from '../../lib/lastHolder';
import { requiredIn } from '../../lib/template';
import type { BeingRef, CharacterSummary } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

export type HolderPickerOptions = {
  root: HTMLElement;
  tenantId: string;
  viewerIsGm: boolean;
  // The board's name, which is the switcher (IN7): its button opens the menu, and its words say whose
  // board this is.
  switcher: HTMLButtonElement;
  title: HTMLElement;
  subtitle: HTMLElement;
  // `viewing` says whose board it is, or null for the viewer's own character.
  onViewHolder(entityId: string, viewing: string | null, name: string): void;
  onViewUnowned(viewing: string): void;
  // A link was hovered or focused: its board is likely next.
  onPrefetch(entityId: string): void;
  onError(message: string): void;
  // Nothing to show: the viewer has no character in this library.
  onNone?(): void;
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

const required = requiredIn('Holder picker');

type Entry = { holder: Holder; name: string; open: (address: boolean) => void };

export function renderHolderPicker(options: HolderPickerOptions): RenderedHolderPicker {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  // The address as it was when the page opened; later, the board puts its own into the URL.
  const params = new URLSearchParams(window.location.search);

  const dialog = required<HTMLDialogElement>(root, '[data-find-dialog]');
  const browseRawId = required<HTMLInputElement>(root, '[data-browse-raw-id]');
  const browseRawIdButton = required<HTMLButtonElement>(root, '[data-browse-raw-id-button]');

  let characters: CharacterSummary[] = [];
  const holderIds = new Set<string>();
  // Every character and group of the viewer's, and how to open its board.
  const entries: Entry[] = [];
  // What the board shows now: one of the entries, a being a GM found, or the unowned things.
  let shown: { key: string } | null = null;
  // What the campaign calls its game master, for the menu's heading (ADR 0294).
  let gmTitle = DEFAULT_GM_WORDS.title;

  fadeOnDismiss(dialog);
  required<HTMLButtonElement>(dialog, '[data-find-close]').addEventListener(
    'click',
    () => closeDialog(dialog),
    { signal },
  );

  // The board's name and what it is: "Character · what they control".
  function say(name: string, what: string, key: string) {
    shown = { key };
    void gmWordsOfBeing(tenantId, key.split(':')[1] ?? null).then((words) => {
      gmTitle = words.title;
    });
    options.title.textContent = name;
    options.subtitle.textContent = what;
    document.title = `${name} — Lorenzo Inventory`;
  }

  // Puts `holder` into the URL as ?character= or ?group=, by id.
  function addressHolder(holder: Holder) {
    const url = new URL(window.location.href);

    url.searchParams.set(holder.kind, holder.id);
    url.searchParams.delete(holder.kind === 'character' ? 'group' : 'character');
    window.history.replaceState({}, '', url);
  }

  // `address` is false when the URL already names it, perhaps by slug (ADR 0135).
  function selectCharacter(character: CharacterSummary, address = true) {
    const holder: Holder = { kind: 'character', id: character.entity_id };

    rememberHolder(tenantId, holder);

    if (address) addressHolder(holder);

    say(character.name, 'Character · what they control', `character:${character.entity_id}`);
    options.onViewHolder(character.entity_id, null, character.name);
  }

  // A group one of your characters belongs to, and what it owns (ADR 0124).
  function selectGroup(group: BeingRef, address = true) {
    const holder: Holder = { kind: 'group', id: group.entity_id };

    rememberHolder(tenantId, holder);

    if (address) addressHolder(holder);

    say(group.name, 'Group · what it holds', `group:${group.entity_id}`);
    options.onViewHolder(group.entity_id, `Viewing what ${group.name} holds.`, group.name);
  }

  function openHolder(wanted: Holder | null, address = true) {
    const entry = wanted
      ? entries.find((e) => e.holder.kind === wanted.kind && e.holder.id === wanted.id)
      : undefined;

    entry?.open(address);
  }

  // With no character or group named, the board opens the one last opened on this library,
  // else your only character (ADR 0134).
  function openDefaultHolder() {
    openHolder(
      defaultHolder(
        entries.map((e) => e.holder),
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

  async function loadGroups(mine: CharacterSummary[]) {
    const groups = await groupsOf(tenantId, mine).catch(() => []);

    for (const group of groups) {
      holderIds.add(group.entity_id);
      entries.push({
        holder: { kind: 'group', id: group.entity_id },
        name: group.name,
        open: (address) => selectGroup(group, address),
      });
    }
  }

  async function load() {
    // Looked up alongside the list, when it's a slug.
    const addressing = addressedHolder();

    try {
      const page = await listMyCharacters(tenantId);

      characters = page.items;

      for (const character of characters) holderIds.add(character.entity_id);

      if (characters.length === 0) {
        // A GM with no character of their own still opens any being's or the unowned things.
        options.title.textContent = 'Inventory';
        options.subtitle.textContent = options.viewerIsGm
          ? 'Choose whose inventory to look at.'
          : "You don't have a character in this library yet.";
        options.onNone?.();
        return;
      }

      for (const character of characters) {
        entries.push({
          holder: { kind: 'character', id: character.entity_id },
          name: character.name,
          open: (address) => selectCharacter(character, address),
        });
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
      options.onError(errorMessage(cause));
    }
  }

  // GM only: browse any being's inventory (ADR 0078: PCs, NPCs and bare beings alike) by
  // search, or by an id or slug typed in. None of the viewer's own characters is the one
  // shown then.
  function browseBeing(being: BeingRef) {
    closeDialog(dialog);
    say(being.name, 'Being · what they control', `being:${being.entity_id}`);
    options.onViewHolder(being.entity_id, `Viewing ${being.name}'s inventory.`, being.name);
  }

  function showUnowned() {
    say('Unowned things', 'What nobody owns', 'unowned');
    options.onViewUnowned('Viewing unowned items.');
  }

  // The board's name is a button: its menu lists your characters and groups and, for a GM, a way to
  // any being and to what nobody owns. With nothing to choose it still shows (IN7).
  options.switcher.addEventListener(
    'click',
    () => {
      const mine = (kind: Holder['kind']) =>
        entries
          .filter((entry) => entry.holder.kind === kind)
          .map((entry) => ({
            label: entry.name,
            icon: kind === 'group' ? 'kind-group' : 'kind-being',
            checked: shown?.key === `${kind}:${entry.holder.id}`,
            run: () => entry.open(true),
          }));
      const characterItems = mine('character');
      const groupItems = mine('group');

      options.onPrefetch(characters[0]?.entity_id ?? '');
      openMenu(
        options.switcher,
        [
          ...(characterItems.length > 0 ? [{ heading: 'My characters' }, ...characterItems] : []),
          ...(groupItems.length > 0 ? [{ heading: 'My groups' }, ...groupItems] : []),
          ...(options.viewerIsGm
            ? [
                { heading: gmTitle },
                {
                  label: 'Find any being…',
                  icon: 'search',
                  run: () => {
                    openDialog(dialog);
                    root.querySelector<HTMLInputElement>('#browse-search')?.focus();
                  },
                },
                { label: 'Unowned things', icon: 'kind-item', run: showUnowned },
              ]
            : []),
        ],
        { label: 'Whose inventory', sprite: `${BRANDING_CSS_URL}/icons.svg` },
      );
    },
    { signal },
  );

  const browse = renderCombobox<BeingRef>(dialog, {
    search: (query) => searchBeingsAndGroups(tenantId, query),
    onPick(being) {
      browse.input.value = being.name;
      browseBeing(being);
    },
    signal,
  });

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
        options.onError(errorMessage(cause));
      }
    },
    { signal },
  );

  return {
    load,
    myCharacters: () => characters,
    isMine: (entityId) => holderIds.has(entityId),

    destroy() {
      controller.abort();
    },
  };
}
