import { errorMessage } from '../../lib/errorMessage';
import { clearContainer, setContainer } from '../../lib/items';
import { moveAnywayOptions, moveOrAsk } from '../../lib/moveAnyway';
import { collectMoveTargets } from '../../lib/moveTargets';
import { splitQuestion } from '../../lib/settingDown';
import type { ItemInstance } from '../../lib/types';
import { type ActionContext, choicesPanel } from './panels';

// Move to…: the way to move a single item without dragging it. The candidates are the
// containers on the board (lib/moveTargets.ts), as Merge into… finds its own.
export function movePanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const previousContainerId = item.container_entity_id;

  // Equipping is moving into the being: Equipped is among the targets.
  const targets = collectMoveTargets(item, ctx.board.containers.values(), ctx.board.items.values());

  // Anything in a container can be set down, what's equipped too (ADR 0132).
  const inContainer = item.container_entity_id !== null;

  const panel = choicesPanel(
    ctx,
    targets.length === 0 && !inContainer
      ? 'No other container is visible on the current board.'
      : null,
  );

  async function performMove(targetId: string | null) {
    // Set down, a stack becomes single items: asked first, and then there's no Undo.
    const question = targetId === null ? splitQuestion([item]) : null;

    if (question !== null && !window.confirm(question)) return;

    panel.setDisabled(true);

    try {
      const anyway = moveAnywayOptions(ctx.viewerIsGm);

      // Into a container, it stacks with something identical already there (ADR 0133).
      let merged = false;

      if (targetId) {
        const endedUp = await moveOrAsk(
          (flags) =>
            setContainer(ctx.tenantId, item.entity_id, targetId, {
              ...flags,
              mergeIdentical: true,
            }),
          anyway,
        );

        merged = endedUp.entity_id !== item.entity_id;
      } else {
        await moveOrAsk(
          (flags) =>
            clearContainer(ctx.tenantId, item.entity_id, { ...flags, split: question !== null }),
          anyway,
        );
      }

      // What's split or merged away can't simply be put back.
      if (question === null && !merged) {
        ctx.undo.record(
          { kind: 'restore-container', entityId: item.entity_id, previousContainerId },
          `${targetId === null ? 'Set down' : 'Moved'} ${item.title}.`,
        );
      } else {
        ctx.undo.forget();
      }

      ctx.finish();
    } catch (error) {
      panel.fail(errorMessage(error));
      panel.setDisabled(false);
    }
  }

  if (inContainer) panel.addChoice('Set down', () => void performMove(null));

  for (const target of targets) panel.addChoice(target.name, () => void performMove(target.id));

  return panel.element;
}
