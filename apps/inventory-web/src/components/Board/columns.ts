import { type BoardColumn, ownerMark } from '../../lib/boardColumns';
import { columnLine, totalWeight, weightLine, weightOf, withUnit } from '../../lib/boardWeights';
import { onIntent } from '../../lib/hoverIntent';
import { fromTemplate, requiredIn } from '../../lib/template';
import type { ItemInstance } from '../../lib/types';
import { isUnsorted } from '../../lib/unsorted';
import type { DropZones } from './dragDrop';
import { ensurePlaceholder, removePlaceholder } from './placeholder';
import type { Selection } from './selection';
import type { BoardState } from './state';

const required = requiredIn('Board');

export type ColumnsOptions = {
  root: HTMLElement;
  state: BoardState;
  selection: Selection;
  drops: DropZones;
  // The board search's current, lower-cased text.
  query(): string;
  onOpenItem(item: ItemInstance, card: HTMLElement): void;
  // The card's "…" menu: what can be done with it without opening it (IN4).
  onOpenMenu(item: ItemInstance, card: HTMLElement, button: HTMLElement): void;
  // A card's item is likely to be opened next.
  onPrefetchItem(item: ItemInstance): void;
  signal: AbortSignal;
  // What the columns say about weight: the library's unit, what each container can carry, and who holds
  // the board (IN8, IN11). Read when a column is drawn and again when the limits arrive.
  weights(): {
    unit: string | null;
    limitOf(containerId: string): number | null;
    holderName: string | null;
  };
};

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function matchesSearch(item: ItemInstance, query: string): boolean {
  return !query || item.title.toLowerCase().includes(query);
}

export function createColumns(options: ColumnsOptions) {
  const { root, state, selection } = options;

  // `readOnly`: in a read-only column (ADR 0131), so it isn't dragged anywhere.
  function renderCard(item: ItemInstance, readOnly: boolean): HTMLLIElement {
    const fragment = fromTemplate(root, '[data-card-template]');
    const card = required<HTMLLIElement>(fragment, 'li');
    const name = required<HTMLElement>(fragment, '[data-name]');
    const container = required<HTMLElement>(fragment, '[data-container]');
    const count = required<HTMLElement>(fragment, '[data-count]');
    const ownerMarkField = required<HTMLElement>(fragment, '[data-owner-mark]');
    const bound = required<HTMLElement>(fragment, '[data-bound]');
    const unsorted = required<HTMLElement>(fragment, '[data-unsorted]');
    const weight = required<HTMLElement>(fragment, '[data-weight]');
    const main = required<HTMLButtonElement>(fragment, '[data-open]');
    const menuButton = required<HTMLButtonElement>(fragment, '[data-menu]');

    card.draggable = !readOnly;
    card.dataset.entityId = item.entity_id;
    card.hidden = !matchesSearch(item, options.query());

    if (selection.active()) main.setAttribute('aria-pressed', 'false');

    container.hidden = !item.is_container;
    name.textContent = item.title;

    const each = weightOf(item);

    // The card's name stays its name; the weight is read in the panel and in the column's line.
    weight.setAttribute('aria-hidden', 'true');

    if (each !== null) weight.textContent = withUnit(each, options.weights().unit);
    else weight.hidden = true;

    onIntent(card, () => options.onPrefetchItem(item), options.signal);

    card.addEventListener('dragend', () => options.drops.end());
    card.addEventListener('dragstart', (event) => {
      event.dataTransfer?.setData('text/plain', item.entity_id);
      // After the browser has drawn its drag image of the card as it is.
      setTimeout(() => options.drops.start(card, item.entity_id));

      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
      }
    });

    // While selecting, a card is a toggle; otherwise it opens the item.
    const activate = () => {
      if (selection.active()) {
        selection.toggle(card);
      } else {
        options.onOpenItem(item, card);
      }
    };

    main.addEventListener('click', activate);
    menuButton.addEventListener('click', (event) => {
      event.stopPropagation();
      options.onOpenMenu(item, card, menuButton);
    });

    if (item.quantity && item.quantity > 1) {
      count.hidden = false;
      count.textContent = `×${item.quantity}`;
    }

    // Whose it is, when it isn't the board's being's own (ADR 0123).
    const mark = state.current ? ownerMark(item, state.current) : null;

    if (mark) {
      ownerMarkField.hidden = false;
      ownerMarkField.textContent = mark;
    }

    // Bound to its owner (ADR 0129).
    bound.hidden = !item.bound;

    // A placeholder the player made for something the catalog doesn't know (ADR 0238).
    unsorted.hidden = !isUnsorted(item, state.unsortedId);

    return card;
  }

  // The columns drawn, to say their weights again when the limits arrive.
  const noted = new Map<
    HTMLElement,
    { column: BoardColumn; field: HTMLElement; count: HTMLElement }
  >();

  function drawNote(column: BoardColumn, field: HTMLElement) {
    const { unit, limitOf, holderName } = options.weights();
    // Only a container column has a limit of its own; Equipped and Not carried say their weight.
    const limit = !column.fixed && column.dropTarget !== null ? limitOf(column.dropTarget) : null;
    const weight = weightLine(totalWeight(column.items), limit, unit);

    field.textContent = columnLine(column, weight, holderName);
    field.hidden = false;
  }

  function refreshNotes() {
    for (const { column, field } of noted.values()) drawNote(column, field);
  }

  // Things were moved: each is now in `target` (null: in none). The columns say it by changing their
  // words, not by being drawn again: what they hold, and where their own container now is ("In
  // Backpack", "Not carried"). False when somewhere can't be told from what is on the board (a
  // container held by someone whose things aren't shown), and then the board is drawn anew.
  function settle(moved: string[], target: string | null): boolean {
    for (const id of moved) {
      const item = state.items.get(id);

      if (item) item.container_entity_id = target;
    }

    for (const { column } of noted.values()) {
      column.items = [...state.items.values()].filter(
        (item) => (item.container_entity_id ?? 'loose') === column.key,
      );

      const container = column.fixed || !column.droppable ? undefined : state.items.get(column.key);

      if (!container) continue;

      // Up through what holds it, nearest first, to the one whose board this is, or to nothing.
      const surroundings: string[] = [];
      let at = container.container_entity_id;
      let carried = false;

      while (at) {
        if (at === state.ownerId) {
          carried = true;
          break;
        }

        const holder = state.items.get(at);

        if (!holder || surroundings.length > 32) return false;
        surroundings.push(holder.title);
        at = holder.container_entity_id;
      }

      column.carried = carried;
      column.note =
        surroundings.length > 0
          ? capitalized(surroundings.map((name) => `in ${name}`).join(', '))
          : carried
            ? null
            : 'Not carried';
    }

    for (const { column, field, count } of noted.values()) {
      count.textContent = String(column.items.length);
      drawNote(column, field);
    }

    return true;
  }

  // What "Move to…" and "Give what's inside…" offer: a column a card can be dropped into.
  function remember(column: BoardColumn) {
    if (column.droppable && column.dropTarget !== null) {
      // "Move to…" offers it under the column's own title: Equipped, not the being's name.
      state.containers.set(column.dropTarget, {
        id: column.dropTarget,
        name: column.title,
        quantity: null,
      });

      if (column.items.length > 0) state.occupied.add(column.dropTarget);
    }
  }

  // Equipped and Not carried, the two every board has, glow; a read-only column takes no
  // drops, and its cards aren't dragged (ADR 0131).
  function renderColumn(column: BoardColumn): HTMLElement {
    const fragment = fromTemplate(root, '[data-column-template]');
    const section = required<HTMLElement>(fragment, '[data-column]');
    const nameField = required<HTMLElement>(fragment, '[data-name]');
    const noteField = required<HTMLElement>(fragment, '[data-note]');
    const countField = required<HTMLElement>(fragment, '[data-column-count]');
    const readOnlyMark = required<HTMLElement>(fragment, '[data-read-only]');
    const list = required<HTMLUListElement>(fragment, '[data-items]');

    section.classList.toggle('glow-canonical', column.fixed);
    section.classList.toggle('board-column--read-only', !column.droppable);

    remember(column);

    // Named by its heading, so each column is a region a reader can find.
    nameField.id = `column-${column.key}`;
    nameField.textContent = column.title;
    section.setAttribute('aria-labelledby', nameField.id);

    countField.textContent = String(column.items.length);
    readOnlyMark.hidden = column.droppable || column.fixed;
    section.dataset.columnKey = column.key;

    // Its weight, how much room is left, and where it is: "12 of 12 lb · full · Imani has these".
    noted.set(section, { column, field: noteField, count: countField });
    drawNote(column, noteField);

    // Holding more than it lists (ADR 0130): it says so, rather than that it's empty.
    list.dataset.empty = column.contentsHidden ? 'Contents not shown.' : column.empty;

    if (column.items.length === 0) {
      ensurePlaceholder(list);
    } else {
      for (const item of column.items) {
        state.items.set(item.entity_id, item);

        if (!column.droppable) state.readOnly.add(item.entity_id);

        list.append(renderCard(item, !column.droppable));
      }

      if (column.contentsHidden) {
        // After the list, not in it: dropping a card in removes the list's placeholder.
        const hidden = document.createElement('p');

        hidden.className = 'column-empty';
        hidden.textContent = 'Other contents not shown.';
        section.append(hidden);
      }
    }

    if (column.droppable) options.drops.bind(section, list, column.dropTarget);

    return section;
  }

  const sameItem = (a: ItemInstance | undefined, b: ItemInstance) =>
    a !== undefined && JSON.stringify(a) === JSON.stringify(b);

  // A column already on the page says what the board now says: its words, and its cards, of which
  // the ones that are as they were stay as they are. False when it can't (it turned read-only, or
  // the other way about), and then it is drawn anew.
  function update(section: HTMLElement, column: BoardColumn, previous: Map<string, ItemInstance>) {
    if (section.classList.contains('board-column--read-only') === column.droppable) return false;

    const nameField = required<HTMLElement>(section, '[data-name]');
    const noteField = required<HTMLElement>(section, '[data-note]');
    const countField = required<HTMLElement>(section, '[data-column-count]');
    const list = required<HTMLUListElement>(section, '[data-items]');

    section.classList.toggle('glow-canonical', column.fixed);
    remember(column);
    nameField.textContent = column.title;
    countField.textContent = String(column.items.length);
    required<HTMLElement>(section, '[data-read-only]').hidden = column.droppable || column.fixed;
    noted.set(section, { column, field: noteField, count: countField });
    drawNote(column, noteField);
    list.dataset.empty = column.contentsHidden ? 'Contents not shown.' : column.empty;

    const have = new Map<string, HTMLElement>();

    for (const card of list.querySelectorAll<HTMLElement>(':scope > li[data-entity-id]')) {
      have.set(card.dataset.entityId ?? '', card);
    }

    removePlaceholder(list);

    column.items.forEach((item, index) => {
      state.items.set(item.entity_id, item);
      if (!column.droppable) state.readOnly.add(item.entity_id);

      let card = have.get(item.entity_id);

      if (card && !sameItem(previous.get(item.entity_id), item)) {
        card.remove();
        card = undefined;
      }

      card ??= renderCard(item, !column.droppable);
      have.delete(item.entity_id);

      if (list.children[index] !== card) list.insertBefore(card, list.children[index] ?? null);
    });

    // What is no longer in it.
    for (const card of have.values()) card.remove();
    ensurePlaceholder(list);

    section.querySelector(':scope > p.column-empty')?.remove();

    if (column.contentsHidden) {
      const hidden = document.createElement('p');

      hidden.className = 'column-empty';
      hidden.textContent = 'Other contents not shown.';
      section.append(hidden);
    }

    return true;
  }

  // The board is fetched again and the page changed to match, without drawing it anew: columns and
  // cards that are as they were are the same elements, so nothing flashes, scrolls or loses focus.
  function reconcile(
    parent: HTMLElement,
    shown: BoardColumn[],
    previous: Map<string, ItemInstance>,
  ) {
    const existing = new Map<string, HTMLElement>();

    for (const section of parent.querySelectorAll<HTMLElement>(':scope > [data-column]')) {
      existing.set(section.dataset.columnKey ?? '', section);
    }

    const sections = shown.map((column) => {
      const section = existing.get(column.key);

      existing.delete(column.key);

      if (section && update(section, column, previous)) return section;

      if (section) {
        noted.delete(section);
        section.remove();
      }

      return renderColumn(column);
    });

    for (const gone of existing.values()) {
      noted.delete(gone);
      gone.remove();
    }

    sections.forEach((section, index) => {
      if (parent.children[index] !== section) {
        parent.insertBefore(section, parent.children[index] ?? null);
      }
    });
  }

  return { renderColumn, reconcile, refreshNotes, settle, forgetColumns: () => noted.clear() };
}
