import { type Board, controlledBoard, unownedBoard } from '../../lib/boardColumns';
import { getControlledItemInstances, getUnownedItemInstances } from '../../lib/items';
import type { ControlledByResponse, ItemInstance } from '../../lib/types';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';
import { createColumns, matchesSearch } from './columns';
import { fromTemplate, required } from './dom';
import { createDropZones } from './dragDrop';
import { createSelection } from './selection';
import { type BoardState, createBoardState } from './state';

export type BoardOptions = {
  root: HTMLElement;
  tenantId: string;
  viewerIsGm: boolean;
  undo: RenderedUndoBanner;
  onOpenItem(item: ItemInstance, card: HTMLElement): void;
};

export type RenderedBoard = {
  state: BoardState;
  // A being's or a group's board: anything controlled-by accepts. `viewing` says whose it is,
  // or null when it's the viewer's own character.
  load(entityId: string, viewing: string | null): Promise<void>;
  // GM only: unclaimed loot, nobody has owned it yet (ADR 0077).
  loadUnowned(viewing: string): Promise<void>;
  // Starts a being's request before its link is clicked.
  prefetch(entityId: string): void;
  // Shows whatever board is current again, after something changed what's on it.
  reload(): void;
  showError(message: string): void;
  destroy(): void;
};

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function renderBoard(options: BoardOptions): RenderedBoard {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const viewing = required<HTMLElement>(root, '[data-viewing]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const columns = required<HTMLElement>(root, '[data-columns]');
  const search = required<HTMLInputElement>(root, '[data-search]');

  const state = createBoardState();

  let reloadCurrentView: (() => void) | null = null;

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
  });

  const { renderColumn } = createColumns({
    root,
    state,
    selection,
    drops,
    query: () => search.value.trim().toLowerCase(),
    onOpenItem: options.onOpenItem,
  });

  // A couple of fake columns and cards shaped like the real thing, without the heading,
  // while the board loads.
  function renderSkeleton() {
    columns.setAttribute('aria-busy', 'true');
    columns.replaceChildren(
      ...Array.from({ length: 2 }, () => {
        const fragment = fromTemplate(root, '[data-column-template]');
        const section = required<HTMLElement>(fragment, '[data-column]');
        const list = required<HTMLUListElement>(fragment, '[data-items]');

        required<HTMLElement>(fragment, '[data-name]').parentElement?.remove();

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
    empty.hidden = true;
    error.hidden = true;
    renderSkeleton();

    try {
      const shown = await fetchBoard();

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
    } catch (cause) {
      columns.replaceChildren();
      columns.removeAttribute('aria-busy');
      error.hidden = false;
      error.textContent = reason(cause);
    }
  }

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

  async function load(entityId: string, viewingText: string | null) {
    reloadCurrentView = () => void load(entityId, viewingText);
    state.ownerId = null;
    viewing.hidden = viewingText === null;
    viewing.textContent = viewingText ?? '';

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
  }

  async function loadUnowned(viewingText: string) {
    reloadCurrentView = () => void loadUnowned(viewingText);
    state.ownerId = null;
    viewing.hidden = false;
    viewing.textContent = viewingText;

    await show(
      async () => unownedBoard(await getUnownedItemInstances(tenantId)),
      "There's nothing unowned right now.",
    );
  }

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
    reload: () => reloadCurrentView?.(),
    showError,

    destroy() {
      selection.destroy();
      controller.abort();
    },
  };
}
