import { itemPageHref } from '../../lib/addresses';
import { blobUrl } from '../../lib/api';
import type { Renderer } from '../../lib/descriptions';
import { getEntityDetail } from '../../lib/items';
import { withReflow } from '../../lib/reflow';
import { createStaleCache, RECENT_MS } from '../../lib/staleCache';
import { requiredIn } from '../../lib/template';
import type { CharacterSummary, ItemBase, ItemInstance } from '../../lib/types';
import { renderAncestryTree } from '../AncestryTree/renderer';
import type { BoardState } from '../Board/state';
import { renderItemView } from '../ItemView/renderer';
import { renderNotes } from '../Notes/renderer';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';
import { giveContentsPanel, givePanel } from './give';
import { mergePanel } from './merge';
import { movePanel } from './move';
import type { ActionContext } from './panels';
import { splitPanel } from './split';

// What the dialog shows: a catalog item, or an instance, which also has an owner, a slug and
// can be bound.
export type ShownItem = ItemBase &
  Partial<Pick<ItemInstance, 'slug' | 'owner_entity_id' | 'bound'>>;

// Give, move, split and merge act on a board's cards: they need the board, and the Undo.
export type ItemDetailBoard = {
  state: BoardState;
  undo: RenderedUndoBanner;
  // The board is out of date: something was given, split, merged or moved.
  onChanged(): void;
};

export type ItemDetailOptions = {
  root: HTMLDialogElement;
  tenantId: string;
  // What the standalone page's address names the library by.
  tenantSlug: string;
  viewerIsGm: boolean;
  renderer: Renderer;
  // The viewer's own characters: who may read an item's private notes (ADR 0113).
  myCharacters(): CharacterSummary[];
  // Without a board the dialog only shows the item.
  board?: ItemDetailBoard;
};

export type RenderedItemDetail = {
  // A board card, with the board's actions; needs `board`.
  open(item: ItemInstance, card: HTMLElement): void;
  // Just the item.
  view(item: ShownItem): void;
  // Fetches what showing the item needs, ahead of `open` or `view`.
  prefetch(item: ShownItem): void;
  destroy(): void;
};

// An instance has an owner (maybe none, but the key); a catalog item doesn't.
const isInstance = (item: ShownItem) => 'owner_entity_id' in item;

// The full ancestry (ADR 0073) is of catalog items. An instance's starts at its own direct
// prototype (id-only, from the instance), a catalog item's at itself; null if there's none.
function ancestryRoot(item: ShownItem): string | null {
  const rootId = isInstance(item) ? item.prototype_ids[0] : item.entity_id;

  return item.prototype_ids.length > 0 && rootId ? rootId : null;
}

const required = requiredIn('Item detail');

export function renderItemDetail(options: ItemDetailOptions): RenderedItemDetail {
  const { root, tenantId, board } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const title = required<HTMLElement>(root, '[data-title]');
  const quantity = required<HTMLElement>(root, '[data-quantity]');
  const bound = required<HTMLElement>(root, '[data-bound]');
  const itemView = renderItemView(required<HTMLElement>(root, '[data-view]'), {
    tenantId,
    renderer: options.renderer,
  });
  const ancestryTree = renderAncestryTree({
    root: required<HTMLElement>(root, '[data-ancestry]'),
    tenantId,
  });
  const notes = renderNotes(required<HTMLElement>(root, '[data-notes]'), {
    tenantId,
    renderer: options.renderer,
    rowHeading: 'h4',
  });
  const viewLink = required<HTMLAnchorElement>(root, '[data-view-link]');
  const actionsRegion = required<HTMLElement>(root, '[data-actions]');
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

  if (board) {
    const context: ActionContext = {
      tenantId,
      viewerIsGm: options.viewerIsGm,
      board: board.state,
      undo: board.undo,
      root,
      // The panel shows the item as it was, or one that's gone, so it closes onto the board
      // as it is now.
      finish() {
        closePanels();
        close();
        board.onChanged();
      },
    };

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
  }

  // A catalog item's slug isn't in its listing: the link goes by what was looked up before, or
  // by the id, until it's looked up.
  const slugs = createStaleCache<string | null>((entityId) =>
    getEntityDetail(tenantId, entityId).then((entity) => entity.slug),
  );
  let slugRequest = 0;

  function linkTo(item: ShownItem) {
    const hrefFor = (slug: string | null | undefined) =>
      itemPageHref(options.tenantSlug, { entity_id: item.entity_id, slug });
    const known = 'slug' in item ? item.slug : slugs.peek(item.entity_id);

    viewLink.href = hrefFor(known);

    if ('slug' in item) return;

    const request = ++slugRequest;

    slugs.refresh(item.entity_id, RECENT_MS).then(
      (slug) => {
        if (request === slugRequest && slug !== known) viewLink.href = hrefFor(slug);
      },
      () => {},
    );
  }

  function populate(item: ShownItem) {
    title.textContent = item.title;
    // A catalog item's title is marked, so which it is shows at a glance.
    title.classList.toggle('canonical-marker', !isInstance(item));
    linkTo(item);

    const stacked = Boolean(item.quantity && item.quantity > 1);

    quantity.hidden = !stacked;
    quantity.textContent = stacked ? `×${item.quantity}` : '';

    itemView.show(item);

    // Its notes (ADR 0113), written by a GM or by a player whose character owns it.
    const reader = options.myCharacters().find((c) => c.entity_id === item.owner_entity_id) ?? null;

    void notes.load(item.entity_id, { canWrite: options.viewerIsGm || reader !== null, reader });

    // Bound to its owner (ADR 0129).
    bound.hidden = !item.bound;

    actionsRegion.hidden = !board;
    closePanels();

    if (!board) return;

    // Only a GM may give a bound item away.
    give.disabled = Boolean(item.bound) && !options.viewerIsGm;
    give.title = give.disabled ? "It's bound to its owner." : '';
    split.disabled = !stacked;

    // Only a container the board shows something inside (ADR 0125).
    giveContents.hidden = !board.state.occupied.has(item.entity_id);

    // A read-only column's cards aren't moved from this board (ADR 0131).
    move.hidden = board.state.readOnly.has(item.entity_id);
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
      if (!board) throw new Error('Item detail was made without a board.');

      current = item;
      openCard = card;

      withReflow(() => {
        card.style.viewTransitionName = '';
        root.style.viewTransitionName = `item-${item.entity_id}`;
        populate(item);
        root.showModal();
      });

      void ancestryTree.load(ancestryRoot(item));
    },

    view(item) {
      current = null;
      openCard = null;

      withReflow(() => {
        populate(item);
        root.showModal();
      });

      void ancestryTree.load(ancestryRoot(item));
    },

    prefetch(item) {
      const rootId = ancestryRoot(item);

      if (rootId) ancestryTree.prefetch(rootId);

      notes.prefetch(item.entity_id);

      if (!('slug' in item)) slugs.prefetch(item.entity_id);

      // Rendering its descriptions and pictures asks for what they link to: this has the
      // answers by then.
      options.renderer(item.descriptions.map((description) => description.content)).catch(() => {});

      for (const picture of item.pictures) blobUrl(picture.url).catch(() => {});
    },

    destroy() {
      controller.abort();
    },
  };
}
