// "Add an item" on a being's board (ADR 0187): find an item in the catalog, confirm it, and
// it's made for the board's being, owned and not carried. Whether to offer it at all is
// lib/addItem.ts's `addItemStanding`; what the API makes of it is the API's. When the catalog
// doesn't know it, "Not in the list" makes an unsorted item instead (ADR 0238).
import { type AddItemStanding, searchAddableItems } from '../../lib/addItem';
import { errorMessage } from '../../lib/errorMessage';
import { createItemInstance, deleteItemInstance } from '../../lib/items';
import { requiredIn } from '../../lib/template';
import type { CatalogItem, ItemInstance } from '../../lib/types';
import { addUnsortedItem, findUnsortedItem, readDraft } from '../../lib/unsorted';
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
  const notListed = required<HTMLElement>(root, '[data-not-listed]');
  const openUnsorted = required<HTMLButtonElement>(root, '[data-not-listed-open]');
  const noUnsorted = required<HTMLElement>(root, '[data-no-unsorted]');
  const unsortedForm = required<HTMLFormElement>(root, '[data-unsorted-form]');
  const unsortedName = required<HTMLInputElement>(root, '[data-unsorted-name]');
  const unsortedDescription = required<HTMLTextAreaElement>(root, '[data-unsorted-description]');
  const unsortedWeight = required<HTMLInputElement>(root, '[data-unsorted-weight]');
  const unsortedValue = required<HTMLInputElement>(root, '[data-unsorted-value]');
  const unsortedAdd = required<HTMLButtonElement>(root, '[data-unsorted-add]');
  const unsortedBack = required<HTMLButtonElement>(root, '[data-unsorted-back]');

  let holder: AddItemHolder | null = null;
  let item: CatalogItem | null = null;
  let busy = false;
  // Only the newest `show` paints, so a slow answer for a board left behind can't.
  let latest = 0;
  let undoTimer: ReturnType<typeof setTimeout> | undefined;
  let undoable: string | null = null;
  // The library's `unsorted` item: null if it has none, undefined while not known (or when the
  // lookup failed, in which case the option is left out rather than guessed at).
  let unsortedId: string | null | undefined;
  let unsortedLookup: Promise<string | null> | undefined;

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
    openUnsorted.disabled = value;
    unsortedAdd.disabled = value;
    unsortedBack.disabled = value;
  }

  // Found once and kept; a failed lookup is tried again next time instead of being remembered.
  async function findUnsorted(): Promise<string | null | undefined> {
    try {
      unsortedLookup ??= findUnsortedItem(tenantId);

      return await unsortedLookup;
    } catch {
      unsortedLookup = undefined;

      return undefined;
    }
  }

  // Looking for something to pick, with the way out beside it when the library has one.
  function showFind() {
    unsortedForm.hidden = true;
    confirm.hidden = true;
    find.hidden = false;
    notListed.hidden = typeof unsortedId !== 'string';
  }

  // Back to looking for something to pick.
  function reset() {
    item = null;
    callIt.value = '';
    search.value = '';
    unsortedName.value = '';
    unsortedDescription.value = '';
    unsortedWeight.value = '';
    unsortedValue.value = '';
    showFind();
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
      notListed.hidden = true;
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

  openUnsorted.addEventListener(
    'click',
    () => {
      const typed = search.value.trim();

      catalog.close();
      find.hidden = true;
      notListed.hidden = true;
      unsortedAdd.textContent = `Add to ${holder?.name ?? 'them'}`;
      unsortedForm.hidden = false;
      say('');

      if (!unsortedName.value) unsortedName.value = typed;

      unsortedName.focus();
    },
    { signal },
  );

  unsortedBack.addEventListener(
    'click',
    () => {
      showFind();
      say('');
      search.focus();
    },
    { signal },
  );

  unsortedForm.addEventListener(
    'submit',
    async (event) => {
      event.preventDefault();

      const prototype = unsortedId;

      if (busy || !holder || typeof prototype !== 'string') return;

      const read = readDraft({
        name: unsortedName.value,
        description: unsortedDescription.value,
        weight: unsortedWeight.value,
        value: unsortedValue.value,
      });

      if (!read.ok) {
        say(read.problem, true);
        unsortedName.focus();

        return;
      }

      const to = holder;

      setBusy(true);
      forgetUndo();
      say('');

      try {
        const added = await addUnsortedItem(tenantId, prototype, to.id, read.item);

        if (holder === to) reset();

        await options.onAdded(added.instance);

        if (holder === to) {
          const lost = added.notesNotSaved.map((title) => title.toLowerCase());
          const sorry = lost.length > 0 ? ` Its ${lost.join(' and ')} couldn't be saved.` : '';

          offerUndo(
            added.instance.entity_id,
            `Added ${added.instance.title} to ${to.name}'s Not carried as an unsorted item.${sorry}`,
          );
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
    notListed.hidden = true;
    noUnsorted.hidden = true;
    unsortedForm.hidden = true;
  }

  async function show(next: AddItemHolder | null) {
    const turn = ++latest;

    holder = next;
    unsortedId = undefined;
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

    // What the library has for what the catalog doesn't (ADR 0238), once it's known.
    const found = await findUnsorted();

    if (turn !== latest) return;

    unsortedId = found;
    noUnsorted.hidden = found !== null;
    showFind();
  }

  return {
    show,

    destroy() {
      clearTimeout(undoTimer);
      controller.abort();
    },
  };
}
