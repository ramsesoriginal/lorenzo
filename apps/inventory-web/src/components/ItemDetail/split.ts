import { errorMessage } from '../../lib/errorMessage';
import { splitItemInstance } from '../../lib/items';
import { say } from '../../lib/statusLine';
import type { ItemInstance } from '../../lib/types';
import { type ActionContext, splitPanelParts } from './panels';

// Split…: splits part of a stack off into a new sibling with the same owner. Only for a
// quantity above 1.
export function splitPanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const { element, input, submit, status } = splitPanelParts(
    ctx,
    `Split off how many? (of ${item.quantity})`,
    (item.quantity ?? 1) - 1,
  );

  submit.addEventListener('click', async () => {
    const quantity = Number.parseInt(input.value, 10);

    if (!Number.isFinite(quantity) || quantity < 1) return;

    submit.disabled = true;

    try {
      const splitOff = await splitItemInstance(ctx.tenantId, item.entity_id, quantity);

      ctx.undo.record(
        { kind: 'undo-split', splitOffEntityId: splitOff.entity_id, intoEntityId: item.entity_id },
        `Split off ${quantity} ${item.title}.`,
      );
      say(status, `Split off ${quantity}.`);
      window.setTimeout(ctx.finish, 1200);
    } catch (error) {
      say(status, errorMessage(error), true);
      submit.disabled = false;
    }
  });

  return element;
}
