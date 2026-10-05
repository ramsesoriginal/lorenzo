// "Add an item" on a being's board (ADR 0187): find an item in the catalog, confirm it, and
// it's made for the board's being, owned and not carried. Whether to offer it at all is
// lib/addItem.ts's `addItemStanding`; what the API makes of it is the API's.
import { type AddItemStanding, searchAddableItems } from '../../lib/addItem';
import { errorMessage } from '../../lib/errorMessage';
import { createItemInstance, deleteItemInstance } from '../../lib/items';
import { requiredIn } from '../../lib/template';
import type { CatalogItem, ItemInstance } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

export type AddItemHolder = Readonly<{ id: string; name: string }>;

export type AddItemOptions = {
  root: HTMLElement;
  tenantId: string;
  standing(holderId: string): Promise<AddItemStanding>;
  // Something was added: shows it on the board, and resolves once it's there.
  onAdded(created: ItemInstance): Promise<void>;
  // Something was taken back: the board is out of date.
  onUndone(): Promise<void>;
};

export type RenderedAddItem = {
  // Points the card at a being's board, or at none (a group's, the unowned board: null).
  show(holder: AddItemHolder | null): Promise<void>;
  destroy(): void;
};

// How long Undo stays, as the page's own banner does (ADR 0068).
const UNDO_MS = 5 * 60 * 1000;

const required = requiredIn('Add an item');

export function renderAddItem(options: AddItemOptions): RenderedAddItem {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const off = required<HTMLElement>(root, '[data-off]');
  const form = required<HTMLElement>(root, '[data-add-form]');
  const hint = required<HTMLElement>(root, '[data-hint]');
  const find = required<HTMLElement>(root, '[data-find]');
  const confirm = required<HTMLFormElement>(root, '[data-confirm]');
  const picked = required<HTMLElement>(root, '[data-picked]');
  const change = required<HTMLButtonElement>(root, '[data-change]');
  const callIt = required<HTMLInputElement>(root, '[data-call-it]');
  const add = required<HTMLButtonElement>(root, '[data-add]');
  const status = required<HTMLElement>(root, '[data-status]');
  const statusText = required<HTMLElement>(root, '[data-status-text]');
  const undo = required<HTMLButtonElement>(root, '[data-undo]');

  let holder: AddItemHolder | null = null;
  let item: CatalogItem | null = null;
  let busy = false;
  // Only the newest `show` paints, so a slow answer for a board left behind can't.
  let latest = 0;
  let undoTimer: ReturnType<typeof setTimeout> | undefined;
  let undoable: string | null = null;

  function say(text: string, failed = false) {
    statusText.textContent = text;
    status.classList.toggle('error-text', failed);
    status.hidden = !text;
    undo.hidden = true;
  }

  function forgetUndo() {
    clearTimeout(undoTimer);
    undoable = null;
    undo.hidden = true;
  }

  function offerUndo(entityId: string, text: string) {
    say(text);
    clearTimeout(undoTimer);
    undoable = entityId;
    undo.hidden = false;
    undoTimer = setTimeout(forgetUndo, UNDO_MS);
  }

  function setBusy(value: boolean) {
    busy = value;
    add.disabled = value;
    change.disabled = value;
    callIt.disabled = value;
    undo.disabled = value;
  }

  // Back to looking for something to pick.
  function reset() {
    item = null;
    confirm.hidden = true;
    find.hidden = false;
    callIt.value = '';
    search.value = '';
  }

  const catalog = renderCombobox<CatalogItem>(root, {
    search: (query) => searchAddableItems(tenantId, query),
    browseOnFocus: true,
    emptyMessage: (query) =>
      query ? `No item matches “${query}”.` : 'Nothing is in the catalog yet.',

    onPick(chosen) {
      item = chosen;
      picked.textContent = chosen.title;
      callIt.placeholder = chosen.title;
      add.textContent = `Add to ${holder?.name ?? 'them'}`;
      find.hidden = true;
      confirm.hidden = false;
      say('');
      callIt.focus();
    },

    signal,
  });
  const search = catalog.input;

  change.addEventListener(
    'click',
    () => {
      reset();
      say('');
      search.focus();
    },
    { signal },
  );

  confirm.addEventListener(
    'submit',
    async (event) => {
      event.preventDefault();

      if (busy || !item || !holder) return;

      const chosen = item;
      const to = holder;

      setBusy(true);
      forgetUndo();
      say('');

      try {
        const created = await createItemInstance(
          tenantId,
          chosen.entity_id,
          to.id,
          undefined,
          callIt.value.trim() || undefined,
        );

        // The holder may have changed while this was out: its card isn't this card now.
        if (holder === to) reset();

        await options.onAdded(created);

        if (holder === to) {
          offerUndo(created.entity_id, `Added ${created.title} to ${to.name}'s Not carried.`);
        }
      } catch (error) {
        say(errorMessage(error), true);
      } finally {
        setBusy(false);
      }
    },
    { signal },
  );

  undo.addEventListener(
    'click',
    async () => {
      const entityId = undoable;

      if (busy || !entityId) return;

      setBusy(true);

      try {
        await deleteItemInstance(tenantId, entityId);
        forgetUndo();
        say('Taken back.');
        await options.onUndone();
      } catch (error) {
        say(errorMessage(error), true);
      } finally {
        setBusy(false);
      }
    },
    { signal },
  );

  function hide() {
    root.hidden = true;
    off.hidden = true;
    form.hidden = true;
  }

  async function show(next: AddItemHolder | null) {
    const turn = ++latest;

    holder = next;
    catalog.close();
    reset();
    forgetUndo();
    say('');
    hide();

    if (!next) return;

    let standing: AddItemStanding;

    try {
      standing = await options.standing(next.id);
    } catch {
      // Not knowing isn't a reason to offer it: the card simply isn't there.
      return;
    }

    if (turn !== latest || standing === 'hidden') return;

    root.hidden = false;

    if (standing === 'off') {
      off.hidden = false;
      off.textContent = `Your GM has switched off adding items for ${next.name}.`;
      return;
    }

    hint.textContent = `Pick something from the catalog and it goes into ${next.name}'s inventory, in Not carried.`;
    form.hidden = false;
  }

  return {
    show,

    destroy() {
      clearTimeout(undoTimer);
      controller.abort();
    },
  };
}
