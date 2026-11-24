import {
  closeDialog,
  fadeOnDismiss,
  type MenuItem,
  openDialog,
  openMenu,
} from '@lorenzo/app-shell';
import { blobUrl } from '../../lib/api';
import { ownerMark } from '../../lib/boardColumns';
import { weightOf, withUnit } from '../../lib/boardWeights';
import { BRANDING_CSS_URL } from '../../lib/config';
import type { Renderer } from '../../lib/descriptions';
import { itemPageHref } from '../../lib/entityLinks';
import { errorMessage } from '../../lib/errorMessage';
import { gmWordsOfBeing } from '../../lib/gmTitle';
import { getEntityDetail } from '../../lib/items';
import { withReflow } from '../../lib/reflow';
import { currentShell } from '../../lib/shell';
import { createStaleCache, RECENT_MS } from '../../lib/staleCache';
import { requiredIn } from '../../lib/template';
import { textHome } from '../../lib/textSources';
import type { CharacterSummary, ItemBase, ItemInstance } from '../../lib/types';
import { looksLikeAPack } from '../../lib/unpack';
import { renderAncestryTree } from '../AncestryTree/renderer';
import type { BoardState } from '../Board/state';
import { renderItemView } from '../ItemView/renderer';
import { renderNotes } from '../Notes/renderer';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';
import { giveContentsPanel, givePanel } from './give';
import { reassignPanel, removeInstance, unassign } from './gm';
import { mergePanel } from './merge';
import { moveItem, movePanel } from './move';
import type { ActionContext } from './panels';
import { splitPanel } from './split';
import { unpackPanel } from './unpack';

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
  // A catalog item, for a game master, is written in place: this fills the place (IN5).
  editor?(host: HTMLElement, item: ShownItem): { dirty(): boolean; destroy(): void };
  // The weight unit of the library, for the line under the title.
  weightUnit?(): string | null;
};

export type RenderedItemDetail = {
  // A board card, with the board's actions; needs `board`.
  open(item: ItemInstance, card: HTMLElement, as?: 'panel' | 'sheet' | 'page'): void;
  // Just the item.
  // `as`: a sheet over the page, or beside it where the page has room for a panel (the default).
  view(item: ShownItem, as?: 'panel' | 'sheet'): void;
  // A board card's "…" menu: what can be done with it, each opening the panel on that.
  menu(item: ItemInstance, card: HTMLElement, button: HTMLElement): void;
  // The panel is open on this item.
  isOpen(): boolean;
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
  const sub = required<HTMLElement>(root, '[data-sub]');
  const editorHost = required<HTMLElement>(root, '[data-editor]');
  const viewHost = required<HTMLElement>(root, '[data-view]');
  let editor: { dirty(): boolean; destroy(): void } | null = null;

  // Leaving what is written in place, with something not saved, is refused in words.
  const mayLeave = () =>
    !editor?.dirty() ||
    window.confirm('You have changes that are not saved. Leave without saving them?');
  const dropEditor = () => {
    editor?.destroy();
    editor = null;
    editorHost.hidden = true;
    viewHost.hidden = false;
  };
  const madeFrom = required<HTMLElement>(root, '[data-made-from]');
  const madeChips = required<HTMLElement>(root, '[data-made-chips]');
  let madeRequest = 0;
  const notesRoot = required<HTMLElement>(root, '[data-notes]');
  const setDown = required<HTMLButtonElement>(root, '[data-set-down]');
  const gm = required<HTMLElement>(root, '[data-gm]');
  const gmHeading = required<HTMLElement>(root, '[data-gm-heading]');
  const reassign = required<HTMLButtonElement>(root, '[data-reassign]');
  const unassignButton = required<HTMLButtonElement>(root, '[data-unassign]');
  const remove = required<HTMLButtonElement>(root, '[data-delete]');
  const addNote = required<HTMLButtonElement>(root, '[data-add-note]');
  const viewLink = required<HTMLAnchorElement>(root, '[data-view-link]');
  const editPage = required<HTMLAnchorElement>(root, '[data-edit-page]');
  const actionsRegion = required<HTMLElement>(root, '[data-actions]');
  const actionPanel = required<HTMLElement>(root, '[data-action-panel]');

  let current: ItemInstance | null = null;
  let openCard: HTMLElement | null = null;

  // A panel beside the board on a wide screen, a side sheet on a tablet, the page on a phone (IN3).
  const wide = window.matchMedia('(min-width: 1100px)');
  const tablet = window.matchMedia('(min-width: 721px)');
  const modeNow = () => (wide.matches ? 'panel' : tablet.matches ? 'sheet' : 'page');

  const markOpen = (card: HTMLElement | null) => {
    for (const other of document.querySelectorAll('.item-card--open')) {
      other.classList.remove('item-card--open');
    }

    card?.classList.add('item-card--open');
  };

  function close() {
    if (!mayLeave()) return;

    dropEditor();

    const card = openCard;

    openCard = null;
    markOpen(null);

    if (!root.matches(':modal')) {
      root.close();

      return;
    }

    withReflow(
      () => {
        root.close();

        if (card?.dataset.entityId) card.style.viewTransitionName = `item-${card.dataset.entityId}`;
      },
      {
        names: [[root, `item-${current?.entity_id ?? ''}`]],
        after: () => {
          if (card) card.style.viewTransitionName = '';
        },
      },
    );
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
    {
      button: required<HTMLButtonElement>(root, '[data-unpack]'),
      label: 'Unpack…',
      panel: unpackPanel,
    },
    { button: reassign, label: 'Reassign…', panel: reassignPanel },
  ];

  const [give, giveContents, move, split, , unpack] = actions.map((action) => action.button);

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

    setDown.addEventListener(
      'click',
      () => {
        const item = current;

        if (!item) return;

        moveItem(context, item, null).catch((error) =>
          currentShell()?.toast({
            kind: 'error',
            title: `Couldn’t set down ${item.title}`,
            text: errorMessage(error),
          }),
        );
      },
      { signal },
    );

    const failed = (title: string) => (error: unknown) =>
      currentShell()?.toast({ kind: 'error', title, text: errorMessage(error) });

    unassignButton.addEventListener(
      'click',
      () => {
        if (current) unassign(context, current).catch(failed(`Couldn’t unassign ${current.title}`));
      },
      { signal },
    );
    remove.addEventListener(
      'click',
      () => {
        if (current) {
          removeInstance(context, current).catch(failed(`Couldn’t delete ${current.title}`));
        }
      },
      { signal },
    );

    for (const action of actions) {
      action.button.addEventListener(
        'click',
        () => {
          // Unpacking asks in a dialog of its own: what it will make, and that the pack goes.
          if (action.button === unpack && current) {
            openUnpackDialog(context, current);

            return;
          }

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

  function openUnpackDialog(context: ActionContext, item: ItemInstance) {
    const dialog = document.createElement('dialog');
    const cancel = document.createElement('button');
    const row = document.createElement('div');
    const heading = document.createElement('h3');
    const finish = () => {
      closeDialog(dialog);
      setTimeout(() => dialog.remove(), 600);
      context.finish();
    };

    dialog.className = 'unpack-dialog';
    dialog.setAttribute('aria-labelledby', 'unpack-dialog-title');
    heading.id = 'unpack-dialog-title';
    heading.textContent = `Unpack ${item.title}?`;
    cancel.type = 'button';
    cancel.className = 'btn btn-secondary';
    cancel.textContent = 'Cancel';
    cancel.addEventListener('click', () => {
      closeDialog(dialog);
      setTimeout(() => dialog.remove(), 600);
    });
    row.className = 'dialog-actions';
    row.append(cancel);

    const body = unpackPanel({ ...context, finish }, item);

    // Cancel and Unpack sit together at the foot, as drawn.
    const submit = body.querySelector<HTMLButtonElement>('[data-submit]');

    if (submit) {
      submit.className = 'btn btn-primary';
      row.append(submit);
    }

    dialog.append(heading, body, row);
    document.body.append(dialog);
    fadeOnDismiss(dialog);
    openDialog(dialog);
  }

  // The same note form the Notes section has, one tap from the actions.
  addNote.addEventListener(
    'click',
    () => {
      const add = notesRoot.querySelector<HTMLButtonElement>('[data-add]');

      if (!add || add.hidden) return;

      add.click();
      add.scrollIntoView({ block: 'nearest' });
    },
    { signal },
  );

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
    editPage.href = viewLink.href;

    if ('slug' in item) return;

    const request = ++slugRequest;

    slugs.refresh(item.entity_id, RECENT_MS).then(
      (slug) => {
        if (request === slugRequest && slug !== known) {
          viewLink.href = hrefFor(slug);
          editPage.href = viewLink.href;
        }
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

    // A game master writes a catalog item in place; everyone else reads it.
    dropEditor();

    if (options.editor && !isInstance(item)) {
      viewHost.hidden = true;
      editorHost.hidden = false;
      editor = options.editor(editorHost, item);
    }

    // Its notes (ADR 0113), written by a GM or by a player whose character owns it.
    const reader = options.myCharacters().find((c) => c.entity_id === item.owner_entity_id) ?? null;

    void notes.load(item.entity_id, {
      canWrite: options.viewerIsGm || reader !== null,
      reader,
      ownerId: item.owner_entity_id ?? null,
    });

    // Bound to its owner (ADR 0129).
    bound.hidden = !item.bound;

    sub.textContent = subtitle(item);

    // What it is made from, by name: the items it comes from (the shell's chips, as drawn).
    const request = ++madeRequest;

    madeFrom.hidden = true;
    getEntityDetail(tenantId, item.entity_id).then(
      (entity) => {
        if (request !== madeRequest || entity.prototypes.length === 0) return;

        madeChips.replaceChildren(
          ...entity.prototypes.map((prototype) => {
            const chip = document.createElement('li');

            chip.className = 'chip';
            chip.textContent = prototype.name;

            return chip;
          }),
        );
        madeFrom.hidden = false;
      },
      () => {},
    );
    addNote.hidden = !(options.viewerIsGm || reader !== null);
    applyActions(item);
  }

  // What the line under the title says: how many, its weight, where it is, and whose.
  function subtitle(item: ShownItem): string {
    const parts: string[] = [];
    const stacked = Boolean(item.quantity && item.quantity > 1);

    if (isInstance(item)) parts.push(stacked ? `${item.quantity} together` : 'One');

    const each = weightOf(item);

    if (each !== null) parts.push(withUnit(each, options.weightUnit?.() ?? null));

    if (board && isInstance(item)) {
      const holder = (item as ItemInstance).container_entity_id;
      const where = holder ? board.state.items.get(holder)?.title : null;

      if (where) parts.push(where);

      const mark = board.state.current
        ? ownerMark(item as ItemInstance, board.state.current)
        : null;

      if (mark) parts.push(mark);
    }

    return parts.join(' · ');
  }

  // Which actions this item has: the panel and the card's menu say the same.
  function applyActions(item: ShownItem) {
    const stacked = Boolean(item.quantity && item.quantity > 1);
    const noteWriter = options.myCharacters().some((c) => c.entity_id === item.owner_entity_id);

    addNote.hidden = !(options.viewerIsGm || noteWriter);
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

    // A game master's tools, for an instance on a board (ADR 0294 for what they are called).
    gm.hidden = !options.viewerIsGm || !isInstance(item);
    unassignButton.hidden = !item.owner_entity_id;

    if (!gm.hidden) {
      void gmWordsOfBeing(options.tenantId, item.owner_entity_id ?? null).then((words) => {
        gmHeading.textContent = words.title;
      });
    }

    // Anything in a container can be set down, what's equipped too (ADR 0132).
    setDown.hidden = move.hidden || !('container_entity_id' in item && item.container_entity_id);

    // A pack is unpacked for its owner, one at a time, from a column you can act in (ADR 0189).
    // Whether it really is one is the API's dry run to say.
    unpack.hidden = !isInstance(item) || !looksLikeAPack(item.descriptions) || move.hidden;
    unpack.disabled = !item.owner_entity_id || stacked;
    unpack.title = !item.owner_entity_id
      ? 'It has no owner to unpack it for.'
      : stacked
        ? 'Split one off to unpack it.'
        : '';
  }

  for (const button of root.querySelectorAll('[data-close]')) {
    button.addEventListener('click', close, { signal });
  }

  // Escape fires 'cancel' first: intercepting it gives Escape the animated close too.
  root.addEventListener(
    'cancel',
    (event) => {
      event.preventDefault();
      close();
    },
    { signal },
  );

  // A panel isn't modal, so Escape reaches it as a key, not as 'cancel'.
  root.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape' && !root.matches(':modal')) close();
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

  function openItem(item: ItemInstance, card: HTMLElement, as?: 'panel' | 'sheet' | 'page') {
    if (!board) throw new Error('Item detail was made without a board.');

    const mode = as ?? modeNow();

    // On a phone an item is its page.
    if (mode === 'page') {
      linkTo(item);
      window.location.assign(viewLink.href);

      return;
    }

    current = item;
    openCard = card;
    markOpen(card);

    if (mode === 'panel') {
      populate(item);

      if (!root.open) root.show();
      else if (root.matches(':modal')) {
        root.close();
        root.show();
      }
    } else {
      // The sheet borrows the card's view-transition-name while open and gives it back on
      // close: two elements sharing one name, one at a time, is what makes the browser morph
      // between them instead of cross-fading.
      withReflow(() => {
        card.style.viewTransitionName = '';
        root.style.viewTransitionName = `item-${item.entity_id}`;
        populate(item);
        root.showModal();
      });
    }

    void ancestryTree.load(ancestryRoot(item));
  }

  return {
    open: openItem,

    view(item, as) {
      if (!mayLeave()) return;

      current = null;
      openCard = null;
      markOpen(null);

      const mode = as ?? (modeNow() === 'panel' ? 'panel' : 'sheet');

      if (mode === 'panel') {
        populate(item);

        if (root.open && root.matches(':modal')) root.close();

        if (!root.open) root.show();
      } else {
        withReflow(() => {
          populate(item);

          if (root.open) root.close();

          root.showModal();
        });
      }

      void ancestryTree.load(ancestryRoot(item));
    },

    // The card's "…" menu: Open, then whatever this item can have done to it. Each opens the panel (a
    // sheet on a phone) with that action's form ready.
    menu(item, card, button) {
      if (!board) return;

      applyActions(item);

      const open = (act?: HTMLButtonElement) => {
        openItem(item, card, modeNow() === 'page' ? 'sheet' : undefined);
        act?.click();
      };
      const entries: MenuItem[] = [
        { label: 'Open', icon: 'kind-item', run: () => openItem(item, card) },
      ];

      const add = (action: HTMLButtonElement | undefined, icon: string, danger = false): void => {
        if (!action || action.hidden || action.disabled) return;

        entries.push({
          label: action.textContent?.trim() ?? '',
          icon,
          ...(danger ? { danger } : {}),
          run: () => open(action),
        });
      };

      add(move, 'move');
      add(give, 'give');
      add(setDown, 'down');
      add(addNote, 'edit');
      add(giveContents, 'give');
      add(split, 'split');
      add(actions[4]?.button, 'merge-items');
      add(unpack, 'unpack');

      // A game master's: only where the panel has them for this item.
      if (!gm.hidden) {
        entries.push({ separator: true });
        add(reassign, 'reassign');
        add(unassignButton, 'unassign');
        add(remove, 'delete', true);
      }

      openMenu(button, entries, {
        label: `Actions for ${item.title}`,
        sprite: `${BRANDING_CSS_URL}/icons.svg`,
      });
    },

    isOpen: () => root.open,

    prefetch(item) {
      const rootId = ancestryRoot(item);

      if (rootId) ancestryTree.prefetch(rootId);

      notes.prefetch(item.entity_id);

      if (!('slug' in item)) slugs.prefetch(item.entity_id);

      // Rendering its descriptions and pictures asks for what they link to: this has the
      // answers by then.
      options
        .renderer(
          item.descriptions.map((description) => description.content),
          item.descriptions.map((description) => textHome(description, item.entity_id)),
        )
        .catch(() => {});

      for (const picture of item.pictures) blobUrl(picture.url).catch(() => {});
    },

    destroy() {
      controller.abort();
    },
  };
}
