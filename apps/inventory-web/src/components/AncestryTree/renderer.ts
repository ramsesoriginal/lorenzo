import { type AncestryNode, fetchAncestry } from '../../lib/ancestryTree';
import { createStaleCache, RECENT_MS } from '../../lib/staleCache';

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

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Ancestry tree is missing ${selector}.`);
  }

  return element;
}

export function renderAncestryTree(options: AncestryTreeOptions): RenderedAncestryTree {
  const { root } = options;

  const list = required<HTMLUListElement>(root, '[data-ancestry-list]');
  const nodeTemplate = required<HTMLTemplateElement>(root, '[data-ancestry-node-template]');
  const loadingTemplate = required<HTMLTemplateElement>(root, '[data-ancestry-loading-template]');
  const trees = createStaleCache((itemId) => fetchAncestry(options.tenantId, itemId));

  const clone = (template: HTMLTemplateElement) =>
    required<HTMLLIElement>(template.content.cloneNode(true) as DocumentFragment, 'li');

  function renderNode(node: AncestryNode): HTMLLIElement {
    const item = clone(nodeTemplate);
    const parents = required<HTMLUListElement>(item, '[data-parents]');

    required<HTMLElement>(item, '[data-name]').textContent = node.name;

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
      list.replaceChildren(shown ? renderNode(shown) : clone(loadingTemplate));

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
