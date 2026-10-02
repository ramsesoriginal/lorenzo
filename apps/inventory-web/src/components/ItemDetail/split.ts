import { splitItemInstance } from '../../lib/items';
import type { ItemInstance } from '../../lib/types';
import { type ActionContext, actionPanel, reason, showStatus, statusLine } from './panels';

// Split…: splits part of a stack off into a new sibling with the same owner. Only for a
// quantity above 1.
export function splitPanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const panel = actionPanel();

  const field = document.createElement('label');
  field.className = 'field';

  const label = document.createElement('span');
  label.className = 'field-label';
  label.textContent = `Split off how many? (of ${item.quantity})`;

  const input = document.createElement('input');
  input.type = 'number';
  input.className = 'text-input';
  input.min = '1';
  input.max = String((item.quantity ?? 1) - 1);

  field.append(label, input);

  const submit = document.createElement('button');
  submit.type = 'button';
  submit.textContent = 'Split';

  const status = statusLine();

  panel.append(field, submit, status);

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
      showStatus(status, `Split off ${quantity}.`, false);
      window.setTimeout(ctx.finish, 1200);
    } catch (error) {
      showStatus(status, reason(error), true);
      submit.disabled = false;
    }
  });

  return panel;
}
