import { type AncestryNode, fetchAncestry } from '../../lib/ancestryTree';
import { itemPageHref } from '../../lib/entityLinks';
import { createStaleCache, RECENT_MS } from '../../lib/staleCache';
import { cloneTemplate, requiredIn } from '../../lib/template';

export type AncestryTreeOptions = {
  // The section holding <AncestryTree />, with its heading: hidden while there's nothing to show.
  root: HTMLElement;
  tenantId: string;
};

export type RenderedAncestryTree = {
  // Shows the ancestry of the catalog item `itemId`, or hides the section for null. What was
  // fetched before shows at once, and is redrawn only if it changed.
  load(itemId: string | null): Promise<void>;
  // Fetches it ahead of `load`.
  prefetch(itemId: string): void;
};

const required = requiredIn('Ancestry tree');

export function renderAncestryTree(options: AncestryTreeOptions): RenderedAncestryTree {
  const { root } = options;

  const list = required<HTMLUListElement>(root, '[data-ancestry-list]');
  const nodeTemplate = required<HTMLTemplateElement>(root, '[data-ancestry-node-template]');
  const loadingTemplate = required<HTMLTemplateElement>(root, '[data-ancestry-loading-template]');
  const trees = createStaleCache((itemId) => fetchAncestry(options.tenantId, itemId));

  function renderNode(node: AncestryNode): HTMLLIElement {
    const item = cloneTemplate<HTMLLIElement>(nodeTemplate, 'li');
    const parents = required<HTMLUListElement>(item, '[data-parents]');

    const link = required<HTMLAnchorElement>(item, '[data-name]');

    link.href = itemPageHref(options.tenantId, { entity_id: node.id });
    link.textContent = node.name;

    if (node.parents.length > 0) {
      parents.replaceChildren(...node.parents.map(renderNode));
    } else {
      parents.remove();
    }

    return item;
  }

  // A slow answer for an earlier item mustn't replace the one now shown.
  let latest = 0;

  return {
    async load(itemId) {
      const request = ++latest;

      if (itemId === null) {
        root.hidden = true;
        return;
      }

      const shown = trees.peek(itemId);

      root.hidden = false;
      list.replaceChildren(
        shown ? renderNode(shown) : cloneTemplate<HTMLLIElement>(loadingTemplate, 'li'),
      );

      try {
        const tree = await trees.refresh(itemId, RECENT_MS);

        if (request === latest && JSON.stringify(tree) !== JSON.stringify(shown)) {
          list.replaceChildren(renderNode(tree));
        }
      } catch {
        if (request === latest && !shown) root.hidden = true;
      }
    },

    prefetch: trees.prefetch,
  };
}
