import { type AncestryNode, fetchAncestry } from '../../lib/ancestryTree';

export type AncestryTreeOptions = {
  // The section holding <AncestryTree />, with its heading: hidden while there's nothing to show.
  root: HTMLElement;
  tenantId: string;
};

export type RenderedAncestryTree = {
  // Shows the ancestry of the catalog item `itemId`, or hides the section for null.
  load(itemId: string | null): Promise<void>;
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

      root.hidden = false;
      list.replaceChildren(clone(loadingTemplate));

      try {
        const tree = await fetchAncestry(options.tenantId, itemId);

        if (request === latest) list.replaceChildren(renderNode(tree));
      } catch {
        if (request === latest) root.hidden = true;
      }
    },
  };
}
