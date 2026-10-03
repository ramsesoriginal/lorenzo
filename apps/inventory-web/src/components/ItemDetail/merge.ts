import { findMergeCandidates } from '../../lib/boardLogic';
import { errorMessage } from '../../lib/errorMessage';
import { mergeItemInstance } from '../../lib/items';
import type { ItemInstance } from '../../lib/types';
import { type ActionContext, choicesPanel } from './panels';

// Merge into…: the candidates are other stacks of the same item already on the board, found
// from what the page holds rather than a search. What counts as the same item is
// findMergeCandidates' (lib/boardLogic.ts): a shared title alone could merge two different
// items (ADR 0067).
export function mergePanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const candidates = findMergeCandidates(ctx.board.items.values(), item);
  const panel = choicesPanel(
    ctx,
    candidates.length === 0 ? 'No other stack of this is visible on the current board.' : null,
  );

  for (const candidate of candidates) {
    const text =
      candidate.quantity && candidate.quantity > 1
        ? `${candidate.title} ×${candidate.quantity}`
        : candidate.title;

    panel.addChoice(text, async () => {
      panel.setDisabled(true);

      try {
        const merged = await mergeItemInstance(ctx.tenantId, item.entity_id, candidate.entity_id);

        ctx.undo.record(
          {
            kind: 'undo-merge',
            intoEntityId: candidate.entity_id,
            quantity: item.quantity ?? 1,
            previousOwnerId: item.owner_entity_id,
          },
          `Merged into ${merged.title}.`,
        );
        ctx.finish();
      } catch (error) {
        panel.fail(errorMessage(error));
        panel.setDisabled(false);
      }
    });
  }

  return panel.element;
}
