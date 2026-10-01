import type { CatalogItem } from '../../lib/types';

type PrototypeNode = {
  id: string;
  title: string;
  parentIds: string[];
  childIds: string[];
};

export type PrototypeFilter = {
  // Rebuilds the tree; selections that are no longer filterable are dropped.
  updateCatalog(items: CatalogItem[]): void;
  // No selection keeps everything; several selections are OR-ed.
  apply(items: CatalogItem[]): CatalogItem[];
  destroy(): void;
};

export type PrototypeFilterOptions = {
  root: HTMLUListElement;
  branchTemplate: HTMLTemplateElement;
  leafTemplate: HTMLTemplateElement;
  signal: AbortSignal;
  onChange(): void;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Catalog filter is missing ${selector}.`);
  }

  return element;
}

function cloneTemplate<T extends Element>(template: HTMLTemplateElement): T {
  const element = template.content.firstElementChild;

  if (!element) {
    throw new Error('Catalog filter template is empty.');
  }

  return element.cloneNode(true) as T;
}

export function createPrototypeFilter(options: PrototypeFilterOptions): PrototypeFilter {
  let graph = new Map<string, PrototypeNode>();

  // A prototype can sit on several paths of the tree, so the selection is
  // keyed by id and every checkbox for that id is kept in step.
  const active = new Set<string>();
  const checkboxes = new Map<string, Set<HTMLInputElement>>();

  // Each set holds the prototype itself plus everything built on it.
  const descendantCache = new Map<string, Set<string>>();

  const byTitle = (leftId: string, rightId: string) => {
    const left = graph.get(leftId)?.title ?? '';
    const right = graph.get(rightId)?.title ?? '';

    return left.localeCompare(right, undefined, { sensitivity: 'base' });
  };

  function isFilterable(id: string): boolean {
    return (graph.get(id)?.childIds.length ?? 0) > 0;
  }

  function filterableChildren(id: string): string[] {
    return (graph.get(id)?.childIds ?? []).filter(isFilterable).sort(byTitle);
  }

  function descendantsOf(id: string): Set<string> {
    const cached = descendantCache.get(id);

    if (cached) {
      return cached;
    }

    const result = new Set<string>();
    const pending = [id];

    while (pending.length > 0) {
      const current = pending.pop();

      if (current === undefined || result.has(current)) {
        continue;
      }

      result.add(current);
      pending.push(...(graph.get(current)?.childIds ?? []));
    }

    descendantCache.set(id, result);

    return result;
  }

  function registerCheckbox(id: string, checkbox: HTMLInputElement) {
    let registered = checkboxes.get(id);

    if (!registered) {
      registered = new Set();
      checkboxes.set(id, registered);
    }

    registered.add(checkbox);
  }

  function syncCheckboxes(id: string) {
    const checked = active.has(id);

    for (const checkbox of checkboxes.get(id) ?? []) {
      checkbox.checked = checked;
    }
  }

  // seenOnPath stops a cycle from recursing forever.
  function renderNode(id: string, seenOnPath: ReadonlySet<string>): HTMLLIElement {
    const node = graph.get(id);

    if (!node) {
      throw new Error(`Catalog filter prototype ${id} is missing.`);
    }

    const children = filterableChildren(id).filter((childId) => !seenOnPath.has(childId));
    const template = children.length > 0 ? options.branchTemplate : options.leafTemplate;
    const row = cloneTemplate<HTMLLIElement>(template);
    const checkbox = required<HTMLInputElement>(row, '[data-filter-checkbox]');
    const title = required<HTMLElement>(row, '[data-filter-title]');

    // The count includes the prototype itself: ticking it shows it too.
    title.textContent = `${node.title} (${descendantsOf(id).size})`;
    checkbox.checked = active.has(id);
    registerCheckbox(id, checkbox);

    checkbox.addEventListener(
      'change',
      () => {
        if (checkbox.checked) {
          active.add(id);
        } else {
          active.delete(id);
        }

        syncCheckboxes(id);
        options.onChange();
      },
      { signal: options.signal },
    );

    if (children.length > 0) {
      const nextPath = new Set(seenOnPath).add(id);

      required<HTMLUListElement>(row, '[data-filter-children]').replaceChildren(
        ...children.map((childId) => renderNode(childId, nextPath)),
      );
    }

    return row;
  }

  function renderTree() {
    checkboxes.clear();

    // A root has no filterable parent in this catalog. A player's catalog
    // can lack a private ancestor, which then simply isn't a parent here.
    const roots = [...graph.keys()]
      .filter(isFilterable)
      .filter((id) =>
        graph
          .get(id)
          ?.parentIds.every((parentId) => !graph.has(parentId) || !isFilterable(parentId)),
      )
      .sort(byTitle);

    options.root.replaceChildren(...roots.map((id) => renderNode(id, new Set())));
  }

  function updateCatalog(items: CatalogItem[]) {
    const next = new Map<string, PrototypeNode>();

    for (const item of items) {
      next.set(item.entity_id, {
        id: item.entity_id,
        title: item.title,
        parentIds: [...item.prototype_ids],
        childIds: [],
      });
    }

    // Parents missing from the catalog are ignored.
    for (const node of next.values()) {
      for (const parentId of node.parentIds) {
        next.get(parentId)?.childIds.push(node.id);
      }
    }

    graph = next;
    descendantCache.clear();

    for (const id of [...active]) {
      if (!isFilterable(id)) {
        active.delete(id);
      }
    }

    renderTree();
  }

  function apply(items: CatalogItem[]): CatalogItem[] {
    if (active.size === 0) {
      return items;
    }

    const allowed = new Set<string>();

    for (const filterId of active) {
      for (const itemId of descendantsOf(filterId)) {
        allowed.add(itemId);
      }
    }

    return items.filter((item) => allowed.has(item.entity_id));
  }

  return {
    updateCatalog,
    apply,

    destroy() {
      options.root.replaceChildren();
      graph.clear();
      active.clear();
      checkboxes.clear();
      descendantCache.clear();
    },
  };
}
