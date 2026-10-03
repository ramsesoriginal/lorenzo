import { summarizeBulkResults } from '../../lib/boardLogic';
import { bulkAssignItemInstances } from '../../lib/items';
import { renderBeingPicker } from '../BeingPicker/renderer';
import { renderCheckboxField } from '../CheckboxField/renderer';
import { type BoardState, containerOf } from './state';

export type Selection = {
  // Whether cards are being picked rather than opened.
  active(): boolean;
  ids: ReadonlySet<string>;
  toggle(card: HTMLLIElement): void;
  setMode(on: boolean): void;
  clear(): void;
  destroy(): void;
};

export type SelectionOptions = {
  tenantId: string;
  state: BoardState;
  columns: HTMLElement;
  modeButton: HTMLButtonElement;
  toolbar: HTMLElement;
  count: HTMLElement;
  giveButton: HTMLButtonElement;
  givePanel: HTMLElement;
  clearButton: HTMLButtonElement;
  onError(message: string): void;
  // Something was given: the board is out of date.
  onGiven(): void;
};

const GIVE_LABEL = 'Give selected to…';

export function createSelection(options: SelectionOptions): Selection {
  const { columns, toolbar, count, giveButton, givePanel, modeButton } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const ids = new Set<string>();
  let selecting = false;

  function updateToolbar() {
    toolbar.hidden = ids.size === 0;
    count.textContent = `${ids.size} selected`;
  }

  function setCardSelected(card: HTMLLIElement, selected: boolean) {
    card.classList.toggle('item-card--selected', selected);
    card.setAttribute('aria-pressed', String(selected));

    const entityId = card.dataset.entityId;

    if (!entityId) return;

    if (selected) {
      ids.add(entityId);
    } else {
      ids.delete(entityId);
    }

    updateToolbar();
  }

  function clear() {
    for (const card of columns.querySelectorAll<HTMLLIElement>('.item-card--selected')) {
      setCardSelected(card, false);
    }

    ids.clear();
    updateToolbar();
  }

  function setMode(on: boolean) {
    selecting = on;
    modeButton.textContent = on ? 'Cancel selecting' : 'Select items';
    modeButton.setAttribute('aria-pressed', String(on));

    if (!on) clear();

    for (const card of columns.querySelectorAll('.item-card')) {
      if (on) {
        card.setAttribute('aria-pressed', 'false');
      } else {
        card.removeAttribute('aria-pressed');
      }
    }
  }

  modeButton.addEventListener('click', () => setMode(!selecting), { signal });
  options.clearButton.addEventListener('click', clear, { signal });

  // Give selected to… (bulk-assign): the same being-picker panel as every other give.
  giveButton.addEventListener(
    'click',
    () => {
      const wasOpen = giveButton.textContent === 'Cancel';

      givePanel.replaceChildren();
      giveButton.textContent = GIVE_LABEL;

      if (wasOpen || ids.size === 0) return;

      giveButton.textContent = 'Cancel';

      const selected = [...ids];
      const inContainers = selected.some((id) => {
        const item = options.state.items.get(id);

        return item ? containerOf(options.state, item) !== null : false;
      });
      const handOver = inContainers
        ? renderCheckboxField(
            'Hand them over',
            'Otherwise they stay in their containers, theirs now.',
          )
        : null;

      const panel = renderBeingPicker({
        tenantId: options.tenantId,
        async perform(being) {
          const moveToOwner = handOver?.input.checked ?? false;
          const results = await bulkAssignItemInstances(
            options.tenantId,
            selected.map((entityId) => ({
              entityId,
              ownerCharacterId: being.entity_id,
              moveToOwner,
            })),
          );

          // Never all-or-nothing (ADR 0044): when every entry failed nothing changed, so
          // throwing leaves the panel open to retry. A partial failure already changed
          // some, so it falls through to the reload instead.
          const outcome = summarizeBulkResults(results);

          if (outcome.allFailed) {
            throw new Error(`Couldn't give any of the ${selected.length} selected item(s).`);
          }

          if (outcome.failedCount > 0) {
            options.onError(`${outcome.failedCount} of ${selected.length} couldn't be given.`);

            return `Gave ${outcome.succeededCount} of ${selected.length} item(s) to ${being.name}.`;
          }

          return `Gave ${selected.length} item(s) to ${being.name}.`;
        },
        onDone() {
          givePanel.replaceChildren();
          giveButton.textContent = GIVE_LABEL;
          setMode(false);
          options.onGiven();
        },
        extraFields: handOver ? [handOver.element] : [],
      });

      givePanel.append(panel);
    },
    { signal },
  );

  return {
    active: () => selecting,
    ids,

    toggle(card) {
      setCardSelected(card, !card.classList.contains('item-card--selected'));
    },

    setMode,
    clear,

    destroy() {
      controller.abort();
    },
  };
}
