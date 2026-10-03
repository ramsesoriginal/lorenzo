import { itemPageHref } from '../../lib/addresses';
import { listItemsUsingPrototype } from '../../lib/items';

export type UsedByOptions = {
  // The <UsedBy /> section: hidden unless something is built on the item.
  root: HTMLElement;
  tenantId: string;
};

export type RenderedUsedBy = {
  // Lists what has the catalog item `entityId` as a prototype.
  load(entityId: string): Promise<void>;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Used by is missing ${selector}.`);
  }

  return element;
}

export function renderUsedBy(options: UsedByOptions): RenderedUsedBy {
  const { root } = options;
  const list = required<HTMLUListElement>(root, '[data-list]');
  const template = required<HTMLTemplateElement>(root, '[data-chip-template]');

  return {
    async load(entityId) {
      try {
        const items = await listItemsUsingPrototype(options.tenantId, entityId);

        list.replaceChildren(
          ...items.map((item) => {
            const chip = required<HTMLLIElement>(
              template.content.cloneNode(true) as DocumentFragment,
              'li',
            );

            const link = required<HTMLAnchorElement>(chip, '[data-name]');

            link.href = itemPageHref(options.tenantId, item);
            link.textContent = item.title;

            return chip;
          }),
        );
        root.hidden = items.length === 0;
      } catch {
        root.hidden = true;
      }
    },
  };
}
