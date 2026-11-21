import { closeDialog, fadeOnDismiss, openDialog } from '@lorenzo/app-shell';
import type { AddItemStanding } from '../../lib/addItem';
import { type Board, controlledBoard, unownedBoard } from '../../lib/boardColumns';
import { carriedWeight, shownNumber, withUnit } from '../../lib/boardWeights';
import { errorMessage } from '../../lib/errorMessage';
import type { GmWords } from '../../lib/gmTitle';
import {
  getControlledItemInstances,
  getEntityDetail,
  getUnownedItemInstances,
} from '../../lib/items';
import { statDefinitions } from '../../lib/statValues';
import { fromTemplate, requiredIn } from '../../lib/template';
import type { ControlledByResponse, ItemInstance } from '../../lib/types';
import { findUnsortedItem } from '../../lib/unsorted';
import { renderAddItem } from '../AddItem/renderer';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';
import { createColumns, matchesSearch } from './columns';
import { createDropZones } from './dragDrop';
import { createSelection } from './selection';
import { type BoardState, createBoardState } from './state';

const required = requiredIn('Board');

export type BoardOptions = {
  root: HTMLElement;
  tenantId: string;
  viewerIsGm: boolean;
  undo: RenderedUndoBanner;
  // Whether to offer adding an item to this being's inventory (ADR 0187).
  addItemStanding(holderId: string): Promise<AddItemStanding>;
  // What the being's campaigns call their game master (ADR 0294).
  addItemGmWords(holderId: string): Promise<GmWords>;
  onOpenItem(item: ItemInstance, card: HTMLElement): void;
  onOpenMenu(item: ItemInstance, card: HTMLElement, button: HTMLElement): void;
  onPrefetchItem(item: ItemInstance): void;
};

export type RenderedBoard = {
  state: BoardState;
  // A being's or a group's board: anything controlled-by accepts. `viewing` says whose it is,
  // or null when it's the viewer's own character; `name` is who or what it is. It is the one a column
  // says holds its Equipped things ("Imani holds these").
  load(entityId: string, viewing: string | null, name: string): Promise<void>;
  // GM only: unclaimed loot, nobody has owned it yet (ADR 0077).
  loadUnowned(viewing: string): Promise<void>;
  // Starts a being's request before its link is clicked.
  prefetch(entityId: string): void;
  // Shows whatever board is current again, after something changed what's on it.
  reload(): Promise<void>;
  showError(message: string): void;
  // The library's weight unit, once known.
  weightUnit(): string | null;
  destroy(): void;
};

export function renderBoard(options: BoardOptions): RenderedBoard {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const columns = required<HTMLElement>(root, '[data-columns]');
  const search = required<HTMLInputElement>(root, '[data-search]');
  const carried = required<HTMLElement>(root, '[data-carried]');
  const carriedText = required<HTMLElement>(root, '[data-carried-text]');
  const carriedBar = required<HTMLElement>(root, '[data-carried-bar]');
  const addOpen = required<HTMLButtonElement>(root, '[data-add-open]');
  const addDialog = required<HTMLDialogElement>(root, '[data-add-dialog]');
  const tabs = required<HTMLElement>(root, '[data-column-tabs]');

  const state = createBoardState();

  let reloadCurrentView: (() => Promise<void>) | null = null;

  function showError(message: string) {
    error.hidden = false;
    error.textContent = message;
    window.setTimeout(() => {
      error.hidden = true;
    }, 5000);
  }

  const selection = createSelection({
    tenantId,
    state,
    columns,
    modeButton: required<HTMLButtonElement>(root, '[data-select-mode]'),
    toolbar: required<HTMLElement>(root, '[data-selection-toolbar]'),
    count: required<HTMLElement>(root, '[data-selection-count]'),
    giveButton: required<HTMLButtonElement>(root, '[data-selection-give]'),
    givePanel: required<HTMLElement>(root, '[data-selection-panel]'),
    clearButton: required<HTMLButtonElement>(root, '[data-selection-clear]'),
    onError: showError,
    onGiven: () => reloadCurrentView?.(),
  });

  const drops = createDropZones({
    tenantId,
    viewerIsGm: options.viewerIsGm,
    state,
    columns,
    selection,
    undo: options.undo,
    onError: showError,
    reload: () => reloadCurrentView?.(),
    weights: () => ({ unit, limitOf: (id) => limits.get(id) ?? null }),
  });

  // The card under the toolbar (ADR 0187). What it adds shows up on this board, and is what the
  // viewer is taken to.
  const addItem = renderAddItem({
    root: required<HTMLElement>(root, '[data-add-item]'),
    tenantId,
    standing: options.addItemStanding,
    gmWords: options.addItemGmWords,
    async onAdded(created) {
      await reloadCurrentView?.();
      reveal(created.entity_id);
    },
    onUndone: async () => reloadCurrentView?.(),
  });

  // What the columns say about weight (IN8, IN11): the library's unit, what each container can carry
  // and who holds the board. The unit and the limits are read after the columns are drawn.
  let unit: string | null = null;
  let holderName: string | null = null;
  const limits = new Map<string, number>();
  let unitLoading: Promise<{ unit: string | null; capacity: string }> | undefined;

  const { renderColumn, refreshNotes, forgetColumns } = createColumns({
    weights: () => ({ unit, limitOf: (id) => limits.get(id) ?? null, holderName }),
    root,
    state,
    selection,
    drops,
    query: () => search.value.trim().toLowerCase(),
    onOpenItem: options.onOpenItem,
    onOpenMenu: options.onOpenMenu,
    onPrefetchItem: options.onPrefetchItem,
    signal,
  });

  // A couple of fake columns and cards shaped like the real thing, without the heading,
  // while the board loads.
  function renderSkeleton() {
    columns.setAttribute('aria-busy', 'true');
    tabs.hidden = true;
    columns.replaceChildren(
      ...Array.from({ length: 2 }, () => {
        const fragment = fromTemplate(root, '[data-column-template]');
        const section = required<HTMLElement>(fragment, '[data-column]');
        const list = required<HTMLUListElement>(fragment, '[data-items]');

        required<HTMLElement>(fragment, '[data-name]').parentElement?.remove();
        fragment.querySelector('[data-note]')?.remove();

        for (let i = 0; i < 3; i++) {
          const card = document.createElement('li');

          card.className = 'item-card skeleton';
          list.append(card);
        }

        return section;
      }),
    );
  }

  // Both boards render alike: a being's or a group's (what it controls, ADR 0131) and the
  // board of unowned things (ADR 0077). Only the latter can be empty - every other board has
  // Not carried to drop onto.
  async function show(fetchBoard: () => Promise<Board>, emptyMessage: string | null) {
    state.items.clear();
    state.containers.clear();
    state.occupied.clear();
    state.readOnly.clear();
    selection.clear();
    forgetColumns();
    empty.hidden = true;
    error.hidden = true;
    carried.hidden = true;
    renderSkeleton();

    try {
      const shown = await fetchBoard();

      state.unsortedId = await unsortedLookup;
      state.current = shown;
      columns.replaceChildren();
      columns.removeAttribute('aria-busy');

      if (emptyMessage !== null && !shown.columns.some((c) => c.items.length > 0)) {
        empty.hidden = false;
        empty.textContent = emptyMessage;
        return;
      }

      // One row, in the order the listing gives.
      columns.append(...shown.columns.map(renderColumn));
      drawTabs();
      void loadWeights(shown);
    } catch (cause) {
      columns.replaceChildren();
      columns.removeAttribute('aria-busy');
      error.hidden = false;
      error.textContent = errorMessage(cause);
    }
  }

  // On a phone the board is one column at a time, with a row of their names to switch (IN2). The
  // row is drawn always and shown by the stylesheet only where the columns would not fit.
  function drawTabs(active = 0) {
    const sections = [...columns.querySelectorAll<HTMLElement>('[data-column]')];

    tabs.hidden = sections.length < 2;
    tabs.replaceChildren(
      ...sections.map((section, index) => {
        const tab = document.createElement('button');
        const name = section.querySelector('[data-name]')?.textContent ?? '';
        const count = section.querySelector('[data-column-count]')?.textContent ?? '';

        tab.type = 'button';
        tab.className = 'column-tab';
        tab.setAttribute('role', 'tab');
        tab.textContent = name;
        tab.append(' ');

        const badge = document.createElement('span');

        badge.className = 'caption';
        badge.textContent = count;
        tab.append(badge);
        tab.addEventListener('click', () => drawTabs(index), { signal });

        return tab;
      }),
    );

    sections.forEach((section, index) => {
      const on = index === active;

      section.classList.toggle('is-active', on);
      tabs.children[index]?.setAttribute('aria-selected', String(on));
    });
  }

  // The library's weight unit and what each container column can carry, then the weights said again
  // (IN8, IN11), and what the being carries against what it can (IN8). A failed read only leaves the
  // columns saying their weight without a limit.
  async function loadWeights(shown: Board) {
    unitLoading ??= statDefinitions(tenantId)
      .then((definitions) => ({
        unit:
          definitions.find(({ definition: d }) => d.role === 'weight' || d.name === 'weight')
            ?.definition.unit ?? null,
        capacity:
          definitions.find(({ definition: d }) => d.role === 'carry_capacity')?.definition.name ??
          'carry_capacity',
      }))
      .catch(() => ({ unit: null, capacity: 'carry_capacity' }));

    const loaded = await unitLoading;

    unit = loaded.unit;

    const limitOf = async (id: string): Promise<number | null> => {
      try {
        const found = (await getEntityDetail(tenantId, id)).stats.find(
          (stat) => stat.name === loaded.capacity,
        )?.value;

        return typeof found === 'number' ? found : null;
      } catch {
        return null;
      }
    };
    const containerIds = shown.columns
      .filter((column) => !column.fixed && column.dropTarget !== null)
      .map((column) => column.dropTarget as string);

    await Promise.all(
      containerIds.map(async (id) => {
        if (limits.has(id)) return;

        const limit = await limitOf(id);

        if (limit !== null) limits.set(id, limit);
      }),
    );

    if (state.current !== shown) return;

    refreshNotes();

    // The being's own carry limit, for the meter; a group or the unowned things carry nothing.
    if (!shown.holderIsBeing || shown.holderId === null) return;

    const own = await limitOf(shown.holderId);

    if (state.current !== shown) return;

    const weight = carriedWeight(shown);

    carried.hidden = false;
    carriedText.textContent =
      own === null ? withUnit(weight, unit) : `${shownNumber(weight)} of ${withUnit(own, unit)}`;
    carriedBar.hidden = own === null || own <= 0;

    const fill = carriedBar.querySelector('i');

    if (fill)
      fill.style.width = `${Math.max(0, Math.min(100, Math.round((weight / (own || 1)) * 100)))}%`;
  }

  // The library's `unsorted` item, looked up once: it marks the placeholders (ADR 0238). Not
  // finding it only means no card is marked.
  const unsortedLookup = findUnsortedItem(tenantId).catch(() => null);

  // Requests fired on hover or focus of a being's link, before the click. Taking one out
  // is one-shot: a later reload of the same being should ask again, not replay a stale answer.
  const prefetched = new Map<string, Promise<ControlledByResponse>>();

  function prefetch(entityId: string) {
    if (prefetched.has(entityId)) return;

    const request = getControlledItemInstances(tenantId, entityId);

    // An unclicked prefetch mustn't be an unhandled rejection. The map keeps the original
    // promise, so load() still sees a real failure.
    request.catch(() => {});
    prefetched.set(entityId, request);
  }

  // Whoever is looked at is reached through the same code as everyone: a fresh look at a being's
  // board offers adding to it, and a reload of the same one leaves the card as it is.
  async function load(
    entityId: string,
    viewingText: string | null,
    name: string,
    fresh = true,
  ): Promise<void> {
    reloadCurrentView = () => load(entityId, viewingText, name, false);
    state.ownerId = null;

    if (fresh) void addItem.show(null);

    holderName = name;

    const request = prefetched.get(entityId);

    prefetched.delete(entityId);

    await show(async () => {
      const shown = controlledBoard(
        await (request ?? getControlledItemInstances(tenantId, entityId)),
        entityId,
      );

      state.ownerId = shown.holderIsBeing ? shown.holderId : null;

      return shown;
    }, null);

    if (fresh && state.ownerId) void addItem.show({ id: state.ownerId, name });
  }

  async function loadUnowned(viewingText: string): Promise<void> {
    reloadCurrentView = () => loadUnowned(viewingText);
    state.ownerId = null;
    void addItem.show(null);
    holderName = null;

    await show(
      async () => unownedBoard(await getUnownedItemInstances(tenantId)),
      "There's nothing unowned right now.",
    );
  }

  // Shows a card the viewer should see: scrolled to, focused, and marked for a moment.
  function reveal(entityId: string) {
    const card = columns.querySelector<HTMLElement>(`[data-entity-id="${CSS.escape(entityId)}"]`);

    if (!card) return;

    card.classList.add('item-card--new');
    window.setTimeout(() => card.classList.remove('item-card--new'), 2500);
    card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    card.focus({ preventScroll: true });
  }

  // "Add an item" is a button that opens the card in a dialog, offered where the viewer may add (ADR 0187).
  const syncAdd = () => {
    addOpen.hidden = addItemRoot.hidden;
  };
  const addItemRoot = required<HTMLElement>(root, '[data-add-item]');

  fadeOnDismiss(addDialog);
  new MutationObserver(syncAdd).observe(addItemRoot, {
    attributes: true,
    attributeFilter: ['hidden'],
  });
  syncAdd();
  addOpen.addEventListener('click', () => openDialog(addDialog), { signal });
  required<HTMLButtonElement>(addDialog, '[data-add-close]').addEventListener(
    'click',
    () => closeDialog(addDialog),
    { signal },
  );

  search.addEventListener(
    'input',
    () => {
      const query = search.value.trim().toLowerCase();

      for (const card of columns.querySelectorAll<HTMLLIElement>('.item-card')) {
        const item = state.items.get(card.dataset.entityId ?? '');

        card.hidden = item ? !matchesSearch(item, query) : false;
      }
    },
    { signal },
  );

  return {
    state,
    load,
    loadUnowned,
    prefetch,
    reload: async () => reloadCurrentView?.(),
    showError,
    weightUnit: () => unit,

    destroy() {
      addItem.destroy();
      selection.destroy();
      controller.abort();
    },
  };
}
