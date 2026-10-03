import { failedEntityIds, mergedAway } from '../../lib/boardLogic';
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

  function bind(column: HTMLElement, list: HTMLUListElement, containerEntityId: string | null) {
    column.addEventListener('dragenter', (event) => {
      event.preventDefault();
      dragDepth.set(column, (dragDepth.get(column) ?? 0) + 1);
      column.classList.add('board-column--drop-target');
    });

    column.addEventListener('dragleave', () => {
      const depth = (dragDepth.get(column) ?? 1) - 1;

      dragDepth.set(column, depth);

      if (depth <= 0) {
        column.classList.remove('board-column--drop-target');
      }
    });

    column.addEventListener('dragover', (event) => {
      event.preventDefault();

      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
      }
    });

    column.addEventListener('drop', (event) => {
      event.preventDefault();
      dragDepth.set(column, 0);
      column.classList.remove('board-column--drop-target');

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

      withReflow(() => {
        removePlaceholder(list);
        for (const c of cardsToMove) list.append(c);
        ensurePlaceholder(sourceList);
      });

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
              withReflow(() => {
                removePlaceholder(sourceList);

                for (const c of cardsToMove) {
                  if (failedIds.has(c.dataset.entityId ?? '')) sourceList.append(c);
                }

                ensurePlaceholder(list);
              });
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
          } else if (idsToMove.some((id) => state.containers.has(id))) {
            // A container moved: its own column, and those inside it, now say where it is
            // (ADR 0134). The Undo stays.
            options.reload();
          }
        })
        .catch((error) => {
          withReflow(() => {
            removePlaceholder(sourceList);
            for (const c of cardsToMove) sourceList.append(c);
            ensurePlaceholder(list);
          });
          options.onError(errorMessage(error));
        });
    });
  }

  return { bind };
}
