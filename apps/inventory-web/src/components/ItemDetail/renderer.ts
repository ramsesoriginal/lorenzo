import { fetchAncestryTree } from '../../lib/ancestryTree';
import type { Renderer } from '../../lib/descriptions';
import { renderItemView } from '../../lib/itemView';
import { renderNotes } from '../../lib/notes';
import { withReflow } from '../../lib/reflow';
import type { CharacterSummary, ItemInstance } from '../../lib/types';
import type { BoardState } from '../Board/state';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';
import { giveContentsPanel, givePanel } from './give';
import { mergePanel } from './merge';
import { movePanel } from './move';
import type { ActionContext } from './panels';
import { splitPanel } from './split';

export type ItemDetailOptions = {
  root: HTMLDialogElement;
  tenantId: string;
  viewerIsGm: boolean;
  renderer: Renderer;
  board: BoardState;
  undo: RenderedUndoBanner;
  // The viewer's own characters: who may read an item's private notes (ADR 0113).
  myCharacters(): CharacterSummary[];
  // The board is out of date: something was given, split, merged or moved.
  onChanged(): void;
};

export type RenderedItemDetail = {
  open(item: ItemInstance, card: HTMLElement): void;
  destroy(): void;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Item detail is missing ${selector}.`);
  }

  return element;
}

export function renderItemDetail(options: ItemDetailOptions): RenderedItemDetail {
  const { root, tenantId, board } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const title = required<HTMLElement>(root, '[data-title]');
  const slug = required<HTMLElement>(root, '[data-slug]');
  const quantity = required<HTMLElement>(root, '[data-quantity]');
  const bound = required<HTMLElement>(root, '[data-bound]');
  const view = required<HTMLElement>(root, '[data-view]');
  const ancestry = required<HTMLElement>(root, '[data-ancestry]');
  const ancestryList = required<HTMLUListElement>(root, '[data-ancestry-list]');
  const notes = required<HTMLElement>(root, '[data-notes]');
  const viewLink = required<HTMLAnchorElement>(root, '[data-view-link]');
  const actionPanel = required<HTMLElement>(root, '[data-action-panel]');

  let current: ItemInstance | null = null;
  let openCard: HTMLElement | null = null;

  function close() {
    const card = openCard;

    openCard = null;
    withReflow(() => {
      root.close();
      root.style.viewTransitionName = '';

      if (card?.dataset.entityId) {
        card.style.viewTransitionName = `item-${card.dataset.entityId}`;
      }
    });
  }

  const context: ActionContext = {
    tenantId,
    viewerIsGm: options.viewerIsGm,
    board,
    undo: options.undo,
    // The panel shows the item as it was, or one that's gone, so it closes onto the board
    // as it is now.
    finish() {
      closePanels();
      close();
      options.onChanged();
    },
  };

  const actions = [
    {
      button: required<HTMLButtonElement>(root, '[data-give]'),
      label: 'Give to…',
      panel: givePanel,
    },
    {
      button: required<HTMLButtonElement>(root, '[data-give-contents]'),
      label: "Give what's inside…",
      panel: giveContentsPanel,
    },
    {
      button: required<HTMLButtonElement>(root, '[data-move]'),
      label: 'Move to…',
      panel: movePanel,
    },
    {
      button: required<HTMLButtonElement>(root, '[data-split]'),
      label: 'Split…',
      panel: splitPanel,
    },
    {
      button: required<HTMLButtonElement>(root, '[data-merge]'),
      label: 'Merge into…',
      panel: mergePanel,
    },
  ];

  const [give, giveContents, move, split] = actions.map((action) => action.button);

  function closePanels() {
    actionPanel.replaceChildren();

    for (const action of actions) action.button.textContent = action.label;
  }

  for (const action of actions) {
    action.button.addEventListener(
      'click',
      () => {
        const wasOpen = action.button.textContent === 'Cancel';

        closePanels();

        if (wasOpen || !current) return;

        action.button.textContent = 'Cancel';
        actionPanel.append(action.panel(context, current));
      },
      { signal },
    );
  }

  function populate(item: ItemInstance) {
    title.textContent = item.title;
    viewLink.href = item.slug
      ? `/item/?tenant=${tenantId}&slug=${encodeURIComponent(item.slug)}`
      : `/item/?tenant=${tenantId}&id=${item.entity_id}`;

    slug.hidden = !item.slug;
    slug.textContent = item.slug ?? '';

    const stacked = Boolean(item.quantity && item.quantity > 1);

    quantity.hidden = !stacked;
    quantity.textContent = stacked ? `×${item.quantity}` : '';

    renderItemView(view, item, { tenantId, renderer: options.renderer });

    // Its notes (ADR 0113), written by a GM or by a player whose character owns it.
    const reader = options.myCharacters().find((c) => c.entity_id === item.owner_entity_id) ?? null;

    void renderNotes(notes, {
      tenantId,
      entityId: item.entity_id,
      renderer: options.renderer,
      canWrite: options.viewerIsGm || reader !== null,
      reader,
      rowHeading: 'h4',
    });

    // Bound to its owner (ADR 0129): only a GM may give it away.
    bound.hidden = !item.bound;
    give.disabled = item.bound && !options.viewerIsGm;
    give.title = give.disabled ? "It's bound to its owner." : '';

    closePanels();
    split.disabled = !stacked;

    // Only a container the board shows something inside (ADR 0125).
    giveContents.hidden = !board.occupied.has(item.entity_id);

    // A read-only column's cards aren't moved from this board (ADR 0131).
    move.hidden = board.readOnly.has(item.entity_id);
  }

  // The full ancestry (ADR 0073) is of catalog items, not instances: the instance's own
  // direct prototype comes first (id-only, from the instance), then that item's graph. The
  // request id keeps a slow answer for an earlier item off the one now open.
  let ancestryRequest = 0;

  async function loadAncestry(item: ItemInstance) {
    const thisRequest = ++ancestryRequest;
    const directId = item.prototype_ids[0];

    if (!directId) {
      ancestry.hidden = true;
      return;
    }

    ancestry.hidden = false;

    const loading = document.createElement('li');

    loading.textContent = 'Loading…';
    ancestryList.replaceChildren(loading);

    try {
      const rootItem = await fetchAncestryTree(tenantId, directId);

      if (thisRequest !== ancestryRequest) return;

      ancestryList.replaceChildren(rootItem);
    } catch {
      if (thisRequest !== ancestryRequest) return;

      ancestry.hidden = true;
    }
  }

  required<HTMLElement>(root, '[data-close]').addEventListener('click', close, { signal });

  // Escape fires 'cancel' first: intercepting it gives Escape the animated close too.
  root.addEventListener(
    'cancel',
    (event) => {
      event.preventDefault();
      close();
    },
    { signal },
  );

  // A click on the <dialog> itself rather than something in it is a click on the backdrop.
  root.addEventListener(
    'click',
    (event) => {
      if (event.target === root) close();
    },
    { signal },
  );

  return {
    // The dialog borrows the card's view-transition-name while open and gives it back on
    // close: two elements sharing one name, one at a time, is what makes the browser morph
    // between them instead of cross-fading.
    open(item, card) {
      current = item;
      openCard = card;

      withReflow(() => {
        card.style.viewTransitionName = '';
        root.style.viewTransitionName = `item-${item.entity_id}`;
        populate(item);
        root.showModal();
      });

      void loadAncestry(item);
    },

    destroy() {
      controller.abort();
    },
  };
}
