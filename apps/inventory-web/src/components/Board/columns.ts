import { type BoardColumn, ownerMark } from '../../lib/boardColumns';
import { columnLine, totalWeight, weightLine, weightOf, withUnit } from '../../lib/boardWeights';
import { onIntent } from '../../lib/hoverIntent';
import { fromTemplate, requiredIn } from '../../lib/template';
import type { ItemInstance } from '../../lib/types';
import { isUnsorted } from '../../lib/unsorted';
import type { DropZones } from './dragDrop';
import { ensurePlaceholder } from './placeholder';
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

    card.draggable = !readOnly;
    card.dataset.entityId = item.entity_id;
    card.style.viewTransitionName = `item-${item.entity_id}`;
    card.hidden = !matchesSearch(item, options.query());

    if (selection.active()) card.setAttribute('aria-pressed', 'false');

    container.hidden = !item.is_container;
    name.textContent = item.title;

    const each = weightOf(item);

    // The card's name stays its name; the weight is read in the panel and in the column's line.
    weight.setAttribute('aria-hidden', 'true');

    if (each !== null) weight.textContent = withUnit(each, options.weights().unit);
    else weight.hidden = true;

    onIntent(card, () => options.onPrefetchItem(item), options.signal);

    card.addEventListener('dragstart', (event) => {
      event.dataTransfer?.setData('text/plain', item.entity_id);

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

    card.addEventListener('click', activate);
    card.addEventListener('keydown', (event) => {
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault(); // keeps Space from scrolling the page
        activate();
      }
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
  const noted = new Map<HTMLElement, { column: BoardColumn; field: HTMLElement }>();

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

    if (column.droppable && column.dropTarget !== null) {
      // "Move to…" offers it under the column's own title: Equipped, not the being's name.
      state.containers.set(column.dropTarget, {
        id: column.dropTarget,
        name: column.title,
        quantity: null,
      });

      if (column.items.length > 0) state.occupied.add(column.dropTarget);
    }

    // Named by its heading, so each column is a region a reader can find.
    nameField.id = `column-${column.key}`;
    nameField.textContent = column.title;
    section.setAttribute('aria-labelledby', nameField.id);

    countField.textContent = String(column.items.length);
    readOnlyMark.hidden = column.droppable || column.fixed;
    section.dataset.columnKey = column.key;

    // Its weight, how much room is left, and where it is: "12 of 12 lb · full · Imani has these".
    noted.set(section, { column, field: noteField });
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

  return { renderColumn, refreshNotes, forgetColumns: () => noted.clear() };
}
