// "Add an item" on a being's board (ADR 0187): find an item in the catalog, confirm it, and
// it's made for the board's being, owned and not carried. Whether to offer it at all is
// lib/addItem.ts's `addItemStanding`; what the API makes of it is the API's. When the catalog
// doesn't know it, "Not in the list" makes an unsorted item instead (ADR 0238).
import { type AddItemStanding, searchAddableItems } from '../../lib/addItem';
import { errorMessage } from '../../lib/errorMessage';
import { DEFAULT_GM_WORDS, type GmWords } from '../../lib/gmTitle';
import { createItemInstance, deleteItemInstance } from '../../lib/items';
import { currentShell } from '../../lib/shell';
import { requiredIn } from '../../lib/template';
import type { CatalogItem, ItemInstance } from '../../lib/types';
import { addUnsortedItem, findUnsortedItem, readDraft } from '../../lib/unsorted';
import { renderCombobox } from '../Combobox/renderer';

export type AddItemHolder = Readonly<{ id: string; name: string }>;

export type AddItemOptions = {
  root: HTMLElement;
  tenantId: string;
  standing(holderId: string): Promise<AddItemStanding>;
  // What the holder's campaigns call their game master (ADR 0294); "GM" when it can't be said.
  gmWords(holderId: string): Promise<GmWords>;
  // Something was added: shows it on the board, and resolves once it's there.
  onAdded(created: ItemInstance): Promise<void>;
  // Something was taken back: the board is out of date.
  onUndone(): Promise<void>;
  // Cancel was pressed: the dialog the card sits in can go.
  onCancel?(): void;
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
  const offBlock = required<HTMLElement>(root, '[data-off-block]');
  const sourceList = required<HTMLInputElement>(root, '[data-source-list]');
  const sourceFree = required<HTMLInputElement>(root, '[data-source-free]');
  const callIt = required<HTMLInputElement>(root, '[data-call-it]');
  const add = required<HTMLButtonElement>(root, '[data-add]');
  const status = required<HTMLElement>(root, '[data-status]');
  const statusText = required<HTMLElement>(root, '[data-status-text]');
  const undo = required<HTMLButtonElement>(root, '[data-undo]');
  const notListed = required<HTMLElement>(root, '[data-not-listed]');
  const matchedLater = required<HTMLElement>(root, '[data-matched-later]');
  const noUnsorted = required<HTMLElement>(root, '[data-no-unsorted]');
  const gmTitle = required<HTMLElement>(root, '[data-gm-title]');
  const unsortedForm = required<HTMLFormElement>(root, '[data-unsorted-form]');
  const unsortedName = required<HTMLInputElement>(root, '[data-unsorted-name]');
  const unsortedDescription = required<HTMLTextAreaElement>(root, '[data-unsorted-description]');
  const unsortedWeight = required<HTMLInputElement>(root, '[data-unsorted-weight]');
  const unsortedValue = required<HTMLInputElement>(root, '[data-unsorted-value]');
  const unsortedAdd = required<HTMLButtonElement>(root, '[data-unsorted-add]');

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

  let undoToast: { dismiss(): void } | null = null;

  function forgetUndo() {
    clearTimeout(undoTimer);
    undoable = null;
    undo.hidden = true;
    undoToast?.dismiss();
    undoToast = null;
  }

  function offerUndo(entityId: string, text: string) {
    say(text);
    clearTimeout(undoTimer);
    undoable = entityId;
    undo.hidden = false;
    undoTimer = setTimeout(forgetUndo, UNDO_MS);
    // The dialog may be closed by then: the shell's toast keeps the Undo within reach (IN4).
    undoToast?.dismiss();
    undoToast = currentShell()?.undoable({ title: text, undo: () => undo.click() }) ?? null;
  }

  function setBusy(value: boolean) {
    busy = value;
    add.disabled = value;
    sourceList.disabled = value;
    sourceFree.disabled = value;
    callIt.disabled = value;
    undo.disabled = value;
    unsortedAdd.disabled = value;
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
    confirm.hidden = false;
    find.hidden = false;
    sourceList.checked = true;
    matchedLater.hidden = true;
    add.disabled = item === null;
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
      search.value = chosen.title;
      callIt.placeholder = chosen.title;
      add.disabled = false;
      say('');
      callIt.focus();
    },

    signal,
  });
  const search = catalog.input;

  // Typing again after a pick is looking for another.
  search.addEventListener(
    'input',
    () => {
      if (item && search.value !== item.title) {
        item = null;
        add.disabled = true;
        callIt.placeholder = '';
      }
    },
    { signal },
  );

  // Cancel: the dialog the card sits in goes away.
  for (const button of root.querySelectorAll<HTMLButtonElement>('[data-cancel]')) {
    button.addEventListener('click', () => options.onCancel?.(), { signal });
  }

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

  // Not in the list: the form for what the catalog doesn't know; From the list: back to finding.
  sourceFree.addEventListener(
    'change',
    () => {
      const typed = search.value.trim();

      catalog.close();
      confirm.hidden = true;
      matchedLater.hidden = false;
      unsortedForm.hidden = false;
      say('');

      if (!unsortedName.value) unsortedName.value = typed;

      unsortedName.focus();
    },
    { signal },
  );

  sourceList.addEventListener(
    'change',
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
    offBlock.hidden = true;
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
    // Not knowing the words isn't a reason to hide the card: it says "GM".
    const wordsLookup = options.gmWords(next.id).catch(() => DEFAULT_GM_WORDS);

    try {
      standing = await options.standing(next.id);
    } catch {
      // Not knowing isn't a reason to offer it: the card simply isn't there.
      return;
    }

    if (turn !== latest || standing === 'hidden') return;

    const words = await wordsLookup;

    if (turn !== latest) return;

    root.hidden = false;
    matchedLater.textContent = `Your ${words.title} matches it to a catalog item later. Your name and notes stay.`;
    gmTitle.textContent = words.title;

    if (standing === 'off') {
      offBlock.hidden = false;
      off.hidden = false;
      off.textContent = `Your ${words.title} has switched off adding items for ${next.name}.`;
      return;
    }

    hint.textContent = `Pick something from the catalog and it goes into ${next.name}'s inventory, in Not carried.`;
    add.textContent = `Add to Not carried`;
    unsortedAdd.textContent = `Add to Not carried`;
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
