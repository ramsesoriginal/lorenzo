import { failedEntityIds, findMergeCandidates, mergedAway } from '../../lib/boardLogic';
import { dropVerdict } from '../../lib/boardWeights';
import { errorMessage } from '../../lib/errorMessage';
import {
  bulkMoveItemInstances,
  clearContainer,
  type MoveFlags,
  setContainer,
} from '../../lib/items';
import {
  bulkMoveAnywayQuestion,
  moveAnywayOptions,
  moveOrAsk,
  overridableIds,
} from '../../lib/moveAnyway';
import { withReflow } from '../../lib/reflow';
import { splitQuestion } from '../../lib/settingDown';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';
import { ensurePlaceholder, removePlaceholder } from './placeholder';
import type { Selection } from './selection';
import type { BoardState } from './state';

export type DropZones = {
  // containerEntityId is the column's container, or null for Not carried.
  bind(column: HTMLElement, list: HTMLUListElement, containerEntityId: string | null): void;
  // A card is picked up and put down: what is dragged is dimmed, and the columns say where it would land.
  start(card: HTMLElement, entityId: string): void;
  end(): void;
};

export type DropZoneOptions = {
  tenantId: string;
  viewerIsGm: boolean;
  state: BoardState;
  columns: HTMLElement;
  selection: Selection;
  undo: RenderedUndoBanner;
  onError(message: string): void;
  reload(): void;
  // What was moved is now in the target: the columns say so in place. False when that can't be told.
  settle(moved: string[], target: string | null): boolean;
  // The library's weight unit and what a container can carry, for what a drag says (IN12).
  weights(): { unit: string | null; limitOf(containerId: string): number | null };
};

type MoveOutcome = { failedIds: Set<string>; merged: boolean };

export function createDropZones(options: DropZoneOptions): DropZones {
  const { tenantId, state, columns, selection, undo } = options;
  const anyway = moveAnywayOptions(options.viewerIsGm);

  // dragenter and dragleave both fire while crossing child elements, so a plain "leave
  // clears the highlight" flickers: each column counts how deep the pointer is instead.
  const dragDepth = new WeakMap<HTMLElement, number>();

  const cardFor = (entityId: string) =>
    columns.querySelector<HTMLLIElement>(`.item-card[data-entity-id="${entityId}"]`);

  // The cards a move animates: each is named for the length of the transition, and nothing else is.
  const named = (cards: HTMLElement[]): [HTMLElement, string][] =>
    cards.map((card) => [card, `item-${card.dataset.entityId ?? ''}`]);

  // What is being dragged: one card, or the selection it belongs to.
  let dragged: string[] = [];
  let ghost: HTMLElement | null = null;
  let lit: HTMLElement | null = null;
  const status = () =>
    columns.closest('[data-board]')?.querySelector<HTMLElement>('[data-drag-status]') ?? null;

  function clearGhost() {
    ghost?.remove();
    ghost = null;

    if (lit) {
      lit.classList.remove('board-column--drop-target', 'board-column--refuse');
      lit = null;
    }

    const live = status();

    if (live) live.textContent = '';
  }

  // The ghost of the card in the column it is over, saying what the move makes, or why it can't (IN12).
  function showGhost(
    column: HTMLElement,
    list: HTMLUListElement,
    containerEntityId: string | null,
  ) {
    const moved = dragged.flatMap((id) => {
      const item = state.items.get(id);

      return item ? [item] : [];
    });
    const [first] = moved;

    if (!first || list === cardFor(first.entity_id)?.parentElement) return;

    const there = [
      ...list.querySelectorAll<HTMLElement>('.item-card:not(.item-card--ghost)'),
    ].flatMap((card) => {
      const item = state.items.get(card.dataset.entityId ?? '');

      return item ? [item] : [];
    });
    const { unit, limitOf } = options.weights();
    const joins = moved.length === 1 ? (findMergeCandidates(there, first)[0] ?? null) : null;
    const verdict = dropVerdict({
      moved,
      there,
      limit: containerEntityId ? limitOf(containerEntityId) : null,
      unit,
      columnName: column.querySelector('h3')?.textContent ?? 'container',
      joins,
    });
    const refused = verdict.kind === 'refuse';

    column.dataset.verdict = verdict.kind;
    column.classList.toggle('board-column--refuse', refused);

    if (!ghost) {
      ghost = document.createElement('li');
      ghost.className = 'item-card item-card--ghost';
      ghost.setAttribute('aria-hidden', 'true');
    }

    const name = document.createElement('span');
    const words = document.createElement('span');
    const title =
      moved.length > 1
        ? `${moved.length} items`
        : `${first.title}${first.quantity && first.quantity > 1 ? ` ×${first.quantity}` : ''}`;

    name.className = 'item-card-title';
    name.textContent = title;
    words.className = 'caption';
    words.textContent =
      options.viewerIsGm && refused ? `${verdict.text}; you can still move it` : verdict.text;
    ghost.replaceChildren(name, words);
    ghost.classList.toggle('item-card--ghost-refused', refused);
    ghost.classList.toggle('item-card--ghost-joins', verdict.kind === 'join');

    if (ghost.parentElement !== list) {
      removePlaceholder(list);
      list.append(ghost);
      ghost.scrollIntoView({ block: 'nearest' });
    }

    const live = status();

    if (live) live.textContent = `${title}: ${words.textContent}`;
  }

  function bind(column: HTMLElement, list: HTMLUListElement, containerEntityId: string | null) {
    column.addEventListener('dragenter', (event) => {
      event.preventDefault();
      dragDepth.set(column, (dragDepth.get(column) ?? 0) + 1);

      if (lit && lit !== column) clearGhost();

      lit = column;
      column.classList.add('board-column--drop-target');
      showGhost(column, list, containerEntityId);
    });

    column.addEventListener('dragleave', () => {
      const depth = (dragDepth.get(column) ?? 1) - 1;

      dragDepth.set(column, depth);

      if (depth <= 0) {
        column.classList.remove('board-column--drop-target', 'board-column--refuse');

        if (lit === column) clearGhost();
      }
    });

    column.addEventListener('dragover', (event) => {
      // A column that can't take it isn't a place to drop (a GM may still ask to move it anyway).
      const refused = column.dataset.verdict === 'refuse' && !options.viewerIsGm;

      if (refused) {
        if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';

        return;
      }

      event.preventDefault();

      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
      }
    });

    column.addEventListener('drop', (event) => {
      event.preventDefault();
      dragDepth.set(column, 0);
      clearGhost();
      column.classList.remove('board-column--drop-target', 'board-column--refuse');

      const entityId = event.dataTransfer?.getData('text/plain');

      if (!entityId) return;

      const card = cardFor(entityId);

      if (!card) return;

      const sourceList = card.parentElement as HTMLUListElement;

      if (sourceList === list) return;

      // Dragging a card of a selection of several moves the whole selection.
      const isBulk = selection.active() && selection.ids.has(entityId) && selection.ids.size > 1;
      const idsToMove = isBulk ? [...selection.ids] : [entityId];
      const cardsToMove = idsToMove.map(cardFor).filter((c): c is HTMLLIElement => c !== null);

      // Where it really was: a card in the owner's own column may be carried by the owner.
      const previousContainerId = state.items.get(entityId)?.container_entity_id ?? null;

      // A column with no container is Not carried, on every board: dropping there sets
      // things down (ADR 0132). Equipped names the being as its container.
      const target = containerEntityId;

      // A stack set down becomes single items: asked first, and then there's no Undo.
      const question =
        target === null
          ? splitQuestion(
              idsToMove.flatMap((id) => {
                const item = state.items.get(id);

                return item ? [item] : [];
              }),
            )
          : null;

      if (question !== null && !window.confirm(question)) return;

      const splitting = question !== null;
      const isStack = (id: string) => (state.items.get(id)?.quantity ?? 1) > 1;

      withReflow(
        () => {
          removePlaceholder(list);
          for (const c of cardsToMove) list.append(c);
          ensurePlaceholder(sourceList);
        },
        { names: named(cardsToMove) },
      );

      // The bulk endpoints are never all-or-nothing (ADR 0044/0065): each answers per entry,
      // so a partial failure moves back only the cards that failed. The single move has no
      // failedIds; it fails as a whole, in the catch below. merged: some of it stacked into
      // something identical (ADR 0133), so the board has to show it anew.
      let request: Promise<MoveOutcome>;

      if (isBulk && target) {
        const moveAll = (ids: string[], flags: MoveFlags = {}) =>
          bulkMoveItemInstances(tenantId, target, ids, { ...flags, mergeIdentical: true });

        request = moveAll(idsToMove).then(async (results) => {
          // One question for every card that didn't fit (ADR 0128).
          const anywayQuestion = options.viewerIsGm ? bulkMoveAnywayQuestion(results) : null;

          if (!anywayQuestion || !window.confirm(anywayQuestion)) {
            return { failedIds: failedEntityIds(results), merged: mergedAway(results) };
          }

          const retried = await moveAll(overridableIds(results), { override: true });
          const combined = results.map(
            (result) => retried.find((r) => r.entity_id === result.entity_id) ?? result,
          );

          return { failedIds: failedEntityIds(combined), merged: mergedAway(combined) };
        });
      } else if (isBulk) {
        // bulk-move needs a container, so setting several down is one call each, settled
        // individually: a rejection mustn't hide which of the others cleared.
        request = Promise.allSettled(
          idsToMove.map((id) => clearContainer(tenantId, id, { split: isStack(id) })),
        ).then((settled) => ({
          failedIds: new Set(
            settled.flatMap((result, i) => (result.status === 'rejected' ? [idsToMove[i]] : [])),
          ),
          merged: false,
        }));
      } else {
        request = moveOrAsk(
          (flags) =>
            target
              ? setContainer(tenantId, entityId, target, { ...flags, mergeIdentical: true })
              : clearContainer(tenantId, entityId, { ...flags, split: splitting }).then(() => null),
          anyway,
        ).then((endedUp) => ({
          failedIds: new Set<string>(),
          merged: endedUp !== null && endedUp.entity_id !== entityId,
        }));
      }

      request
        .then(({ failedIds, merged }) => {
          if (isBulk) {
            if (failedIds.size > 0) {
              withReflow(
                () => {
                  removePlaceholder(sourceList);

                  for (const c of cardsToMove) {
                    if (failedIds.has(c.dataset.entityId ?? '')) sourceList.append(c);
                  }

                  ensurePlaceholder(list);
                },
                { names: named(cardsToMove) },
              );
              options.onError(`${failedIds.size} of ${idsToMove.length} couldn't be moved.`);
            }

            // Moving several isn't undoable: that would take each one's previous state.
            selection.setMode(false);
          } else if (!splitting && !merged) {
            undo.record(
              { kind: 'restore-container', entityId, previousContainerId },
              `${target === null ? 'Set down' : 'Moved'} ${state.items.get(entityId)?.title ?? 'item'}.`,
            );
          }

          // The pieces a split made are cards of their own, and a merge made one stack of
          // two: neither can simply be put back, and the board shows them anew.
          if (splitting || merged) {
            undo.forget();
            options.reload();
          } else if (
            !options.settle(
              idsToMove.filter((id) => !failedIds.has(id)),
              target,
            )
          ) {
            // Where something is can't be told from what the board shows: it is drawn anew. The
            // Undo stays.
            options.reload();
          }
        })
        .catch((error) => {
          withReflow(
            () => {
              removePlaceholder(sourceList);
              for (const c of cardsToMove) sourceList.append(c);
              ensurePlaceholder(list);
            },
            { names: named(cardsToMove) },
          );
          options.onError(errorMessage(error));
        });
    });
  }

  return {
    bind,

    start(card, entityId) {
      const isBulk = selection.active() && selection.ids.has(entityId) && selection.ids.size > 1;

      dragged = isBulk ? [...selection.ids] : [entityId];

      // What is dragged stays where it was, dimmed.
      for (const id of dragged) cardFor(id)?.classList.add('item-card--dragging');
      card.classList.add('item-card--dragging');
    },

    end() {
      clearGhost();
      dragged = [];

      for (const card of columns.querySelectorAll('.item-card--dragging')) {
        card.classList.remove('item-card--dragging');
      }
    },
  };
}
