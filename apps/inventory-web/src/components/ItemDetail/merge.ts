import { findMergeCandidates } from '../../lib/boardLogic';
import { mergeItemInstance } from '../../lib/items';
import type { ItemInstance } from '../../lib/types';
import { type ActionContext, actionPanel, note, reason, showStatus, statusLine } from './panels';

// Merge into…: the candidates are other stacks of the same item already on the board, found
// from what the page holds rather than a search. What counts as the same item is
// findMergeCandidates' (lib/boardLogic.ts): a shared title alone could merge two different
// items (ADR 0067).
export function mergePanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const panel = actionPanel();
  const candidates = findMergeCandidates(ctx.board.items.values(), item);

  if (candidates.length === 0) {
    panel.append(note('No other stack of this is visible on the current board.'));

    return panel;
  }

  const status = statusLine();
  const list = document.createElement('div');

  list.className = 'merge-candidates';

  const setDisabled = (disabled: boolean) => {
    for (const button of list.querySelectorAll('button')) button.disabled = disabled;
  };

  for (const candidate of candidates) {
    const button = document.createElement('button');

    button.type = 'button';
    button.textContent =
      candidate.quantity && candidate.quantity > 1
        ? `${candidate.title} ×${candidate.quantity}`
        : candidate.title;
    button.addEventListener('click', async () => {
      setDisabled(true);

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
        showStatus(status, reason(error), true);
        setDisabled(false);
      }
    });
    list.append(button);
  }

  panel.append(list, status);

  return panel;
}
