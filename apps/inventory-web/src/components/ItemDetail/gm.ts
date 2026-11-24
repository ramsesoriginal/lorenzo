import { errorMessage } from '../../lib/errorMessage';
import { deleteItemInstance, setOwner, unsetOwner } from '../../lib/items';
import { giveOrAsk } from '../../lib/moveAnyway';
import { deleteSplitQuestion, isStackRefusal } from '../../lib/settingDown';
import type { ItemInstance } from '../../lib/types';
import { renderBeingPicker } from '../BeingPicker/renderer';
import type { ActionContext } from './panels';

const anyway = (ctx: ActionContext) => ({
  canOverride: ctx.viewerIsGm,
  ask: (question: string) => window.confirm(question),
});

// Reassign…: another being owns it now, wherever it is (a game master's tool).
export function reassignPanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const previousOwnerId = item.owner_entity_id;

  return renderBeingPicker({
    tenantId: ctx.tenantId,

    async perform(being) {
      await giveOrAsk(
        (flags) => setOwner(ctx.tenantId, item.entity_id, being.entity_id, false, flags),
        anyway(ctx),
      );
      ctx.undo.record(
        { kind: 'restore-owner', entityId: item.entity_id, previousOwnerId },
        `Reassigned ${item.title} to ${being.name}.`,
      );

      return `Reassigned to ${being.name}.`;
    },

    onDone: ctx.finish,
  });
}

// Unassign: nobody owns it now.
export async function unassign(ctx: ActionContext, item: ItemInstance): Promise<void> {
  const previousOwnerId = item.owner_entity_id;

  await giveOrAsk((flags) => unsetOwner(ctx.tenantId, item.entity_id, flags), anyway(ctx));
  ctx.undo.record(
    { kind: 'restore-owner', entityId: item.entity_id, previousOwnerId },
    `Unassigned ${item.title}.`,
  );
  ctx.finish();
}

// Delete…: it is gone, so it asks first and there is no Undo (its id is simply gone).
export async function removeInstance(ctx: ActionContext, item: ItemInstance): Promise<void> {
  if (!window.confirm(`Delete "${item.title}"? This can't be undone.`)) return;

  try {
    await deleteItemInstance(ctx.tenantId, item.entity_id);
  } catch (error) {
    if (!isStackRefusal(error) || !window.confirm(deleteSplitQuestion(item.title))) {
      throw new Error(errorMessage(error));
    }

    await deleteItemInstance(ctx.tenantId, item.entity_id, { split: true });
  }

  ctx.undo.forget();
  ctx.finish();
}
