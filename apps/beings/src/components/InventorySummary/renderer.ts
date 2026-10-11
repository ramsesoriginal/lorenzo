// A short account of what a being owns (ADR 0271): how many things, the first few by name, and a
// link to inventory-web's board for it, where it is configured. The owned-by read is the API's, and
// is refused to someone who may not see the inventory; then the section says so and stays small.

import { getOwned, summariseInventory } from '../../lib/being';
import { inventoryBoardHref } from '../../lib/entityLinks';
import { errorMessage } from '../../lib/errorMessage';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';

const required = requiredIn('Inventory summary');

export type RenderedInventorySummary = {
  load(tenantId: string, tenantAddress: string, entityId: string): Promise<void>;
};

// `root` is the <InventorySummary /> block.
export function renderInventorySummary(root: HTMLElement): RenderedInventorySummary {
  const message = required<HTMLElement>(root, '[data-message]');
  const counts = required<HTMLElement>(root, '[data-counts]');
  const list = required<HTMLUListElement>(root, '[data-list]');
  const more = required<HTMLElement>(root, '[data-more]');
  const board = required<HTMLAnchorElement>(root, '[data-board]');
  const template = required<HTMLTemplateElement>(root, '[data-item-template]');

  return {
    async load(tenantId, tenantAddress, entityId) {
      root.hidden = false;
      counts.hidden = true;
      list.hidden = true;
      more.hidden = true;
      say(message, 'Loading the inventory…');

      const href = inventoryBoardHref(tenantAddress, entityId);

      board.hidden = !href;
      if (href) board.href = href;

      try {
        const summary = summariseInventory(await getOwned(tenantId, entityId));

        say(message, '');

        if (summary.entries === 0) {
          say(message, 'Carries nothing.');
          return;
        }

        counts.hidden = false;
        counts.textContent =
          summary.pieces === summary.entries
            ? `${summary.entries} ${summary.entries === 1 ? 'item' : 'items'}`
            : `${summary.entries} items, ${summary.pieces} pieces in all`;
        list.replaceChildren(
          ...summary.top.map((item) => {
            const row = cloneTemplate<HTMLLIElement>(template, 'li');
            const quantity = required<HTMLElement>(row, '[data-quantity]');

            required<HTMLElement>(row, '[data-name]').textContent = item.name;
            quantity.hidden = item.quantity <= 1;
            quantity.textContent = `×${item.quantity}`;

            return row;
          }),
        );
        list.hidden = false;
        say(more, summary.more > 0 ? `and ${summary.more} more` : '');
      } catch (error) {
        say(message, `Couldn't load the inventory: ${errorMessage(error)}`, true);
      }
    },
  };
}
