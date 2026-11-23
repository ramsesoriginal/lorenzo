import { failedEntityIds, findMergeCandidates, summarizeBulkResults } from '../../lib/boardLogic';
import { errorMessage } from '../../lib/errorMessage';
import { bulkAssignItemInstances, bulkMoveItemInstances, mergeItemInstance } from '../../lib/items';
import { bulkMoveAnywayQuestion, overridableIds } from '../../lib/moveAnyway';
import { collectMoveTargets } from '../../lib/moveTargets';
import type { ItemInstance } from '../../lib/types';
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
  moveButton: HTMLButtonElement;
  mergeButton: HTMLButtonElement;
  viewerIsGm: boolean;
  givePanel: HTMLElement;
  clearButton: HTMLButtonElement;
  onError(message: string): void;
  // Something was given: the board is out of date.
  onGiven(): void;
  // Something was moved or merged: the board is out of date.
  onChanged(): void;
};

const GIVE_LABEL = 'Give…';
const MOVE_LABEL = 'Move to…';

export function createSelection(options: SelectionOptions): Selection {
  const { columns, toolbar, count, giveButton, givePanel, modeButton } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const ids = new Set<string>();
  let selecting = false;

  // The selected stacks that are all of one item: what Merge joins into the first.
  function mergeable(): ItemInstance[] {
    const chosen = [...ids].flatMap((id) => {
      const item = options.state.items.get(id);

      return item ? [item] : [];
    });
    const [first] = chosen;

    if (!first) return [];

    return [first, ...findMergeCandidates(chosen, first)];
  }

  function updateToolbar() {
    toolbar.hidden = ids.size === 0;
    count.textContent = `${ids.size} ${ids.size === 1 ? 'card' : 'cards'} selected`;
    options.mergeButton.disabled = mergeable().length < 2;
    options.mergeButton.title = options.mergeButton.disabled
      ? 'Select two or more stacks of the same item.'
      : '';
  }

  function setCardSelected(card: HTMLLIElement, selected: boolean) {
    card.classList.toggle('item-card--selected', selected);
    card.querySelector('.item-card-main')?.setAttribute('aria-pressed', String(selected));

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
    const label = modeButton.querySelector('[data-select-label]');

    if (label) label.textContent = on ? 'Cancel selecting' : 'Select';
    modeButton.setAttribute('aria-pressed', String(on));

    if (!on) clear();

    columns.classList.toggle('is-selecting', on);

    for (const main of columns.querySelectorAll('.item-card-main')) {
      if (on) {
        main.setAttribute('aria-pressed', 'false');
      } else {
        main.removeAttribute('aria-pressed');
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

  // Move to…: into a container on the board, all of them, as dragging a selection does.
  options.moveButton.addEventListener(
    'click',
    () => {
      const wasOpen = options.moveButton.textContent === 'Cancel';

      givePanel.replaceChildren();
      giveButton.textContent = GIVE_LABEL;
      options.moveButton.textContent = MOVE_LABEL;

      if (wasOpen || ids.size === 0) return;

      options.moveButton.textContent = 'Cancel';

      const selected = [...ids];
      const items = [...options.state.items.values()];
      // A container every selected card could go into.
      const targets = selected
        .map((id) => options.state.items.get(id))
        .filter((item): item is ItemInstance => item !== undefined)
        .map(
          (item) =>
            new Map(
              collectMoveTargets(item, options.state.containers.values(), items).map((t) => [
                t.id,
                t.name,
              ]),
            ),
        )
        .reduce<Map<string, string>>(
          (common, next, i) =>
            i === 0 ? next : new Map([...common].filter(([id]) => next.has(id))),
          new Map(),
        );
      const panel = document.createElement('div');
      const status = document.createElement('p');

      panel.className = 'merge-candidates';
      status.className = 'error-text';
      status.hidden = true;

      if (targets.size === 0) {
        status.hidden = false;
        status.textContent = 'No container on the board takes all of them.';
      }

      async function moveInto(target: string) {
        try {
          const moveAll = (flags: { override?: boolean } = {}) =>
            bulkMoveItemInstances(options.tenantId, target, selected, {
              ...flags,
              mergeIdentical: true,
            });
          let results = await moveAll();
          const question = options.viewerIsGm ? bulkMoveAnywayQuestion(results) : null;

          if (question && window.confirm(question)) {
            const retried = await moveAll({ override: true });

            results = results.map(
              (result) => retried.find((r) => r.entity_id === result.entity_id) ?? result,
            );
          }

          const failed = failedEntityIds(results).size;

          if (failed === selected.length) throw new Error('None of them could be moved.');

          if (failed > 0) options.onError(`${failed} of ${selected.length} couldn't be moved.`);

          givePanel.replaceChildren();
          options.moveButton.textContent = MOVE_LABEL;
          setMode(false);
          options.onChanged();
        } catch (error) {
          status.hidden = false;
          status.textContent = errorMessage(error);
        }
      }

      for (const [id, name] of targets) {
        const choice = document.createElement('button');

        choice.type = 'button';
        choice.className = 'btn btn-secondary';
        choice.textContent = name;
        choice.addEventListener('click', () => void moveInto(id));
        panel.append(choice);
      }

      givePanel.append(panel, status);
    },
    { signal },
  );

  // Merge: stacks of one item become the first of them, the others added to it.
  options.mergeButton.addEventListener(
    'click',
    async () => {
      const [into, ...others] = mergeable();

      if (!into || others.length === 0) return;

      options.mergeButton.disabled = true;

      try {
        for (const other of others) {
          await mergeItemInstance(options.tenantId, other.entity_id, into.entity_id);
        }

        setMode(false);
        options.onChanged();
      } catch (error) {
        options.onError(errorMessage(error));
        updateToolbar();
      }
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
