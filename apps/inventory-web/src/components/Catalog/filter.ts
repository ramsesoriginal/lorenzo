import type { CatalogItem } from '../../lib/types';

type PrototypeNode = {
  id: string;
  title: string;
  parentIds: string[];
  childIds: string[];
};

export type PrototypeFilter = {
  /**
   * Replace the catalog the taxonomy is built from.
   *
   * Active filters that no longer exist as filterable prototypes
   * are removed automatically.
   */
  updateCatalog(items: CatalogItem[]): void;

  /**
   * Apply the currently selected prototype filters.
   *
   * No selections = everything.
   * Multiple selections = OR.
   */
  apply(items: CatalogItem[]): CatalogItem[];

  destroy(): void;
};

export type PrototypeFilterOptions = {
  root: HTMLUListElement;
  branchTemplate: HTMLTemplateElement;
  leafTemplate: HTMLTemplateElement;
  signal: AbortSignal;

  /**
   * Runs whenever the user changes a checkbox.
   * The caller can then repaint its current search result.
   */
  onChange(): void;
};

function required<T extends Element>(
  root: ParentNode,
  selector: string,
): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Catalog filter is missing ${selector}.`);
  }

  return element;
}

function cloneTemplate<T extends Element>(
  template: HTMLTemplateElement,
): T {
  const element = template.content.firstElementChild;

  if (!element) {
    throw new Error('Catalog filter template is empty.');
  }

  return element.cloneNode(true) as T;
}

export function createPrototypeFilter(
  options: PrototypeFilterOptions,
): PrototypeFilter {
  let graph = new Map<string, PrototypeNode>();

  /*
   * A prototype can occur at several locations in the rendered DAG.
   * State therefore belongs here, keyed by entity id, rather than
   * belonging to any one checkbox.
   */
  const active = new Set<string>();

  /*
   * Transitive descendant sets are stable until updateCatalog().
   * Each contains the prototype itself as well as everything built
   * on top of it.
   */
  const descendantCache =
    new Map<string, Set<string>>();

  /*
   * One entity can be rendered along several DAG paths. Keep every
   * checkbox for it here so toggling one updates all the others.
   */
  const checkboxes =
    new Map<string, Set<HTMLInputElement>>();

  const byTitle = (
    leftId: string,
    rightId: string,
  ) => {
    const left = graph.get(leftId)?.title ?? '';
    const right = graph.get(rightId)?.title ?? '';

    return left.localeCompare(
      right,
      undefined,
      { sensitivity: 'base' },
    );
  };

  function isFilterable(id: string): boolean {
    return (graph.get(id)?.childIds.length ?? 0) > 0;
  }

  function filterableChildren(id: string): string[] {
    return (graph.get(id)?.childIds ?? [])
      .filter(isFilterable)
      .sort(byTitle);
  }

  function descendantsOf(id: string): Set<string> {
    const cached = descendantCache.get(id);

    if (cached) {
      return cached;
    }

    const result = new Set<string>();
    const pending = [id];

    while (pending.length > 0) {
      const current = pending.pop()!;

      if (result.has(current)) {
        continue;
      }

      result.add(current);

      const node = graph.get(current);

      if (node) {
        pending.push(...node.childIds);
      }
    }

    descendantCache.set(id, result);

    return result;
  }

  function registerCheckbox(
    id: string,
    checkbox: HTMLInputElement,
  ) {
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

  function renderNode(
    id: string,
    seenOnPath: ReadonlySet<string>,
  ): HTMLLIElement {
    const node = graph.get(id);

    if (!node) {
      throw new Error(
        `Catalog filter prototype ${id} is missing.`,
      );
    }

    const children =
      filterableChildren(id).filter(
        (childId) => !seenOnPath.has(childId),
      );

    const template =
      children.length > 0
        ? options.branchTemplate
        : options.leafTemplate;

    const row =
      cloneTemplate<HTMLLIElement>(template);

    const checkbox =
      required<HTMLInputElement>(
        row,
        '[data-filter-checkbox]',
      );

    const title =
      required<HTMLElement>(
        row,
        '[data-filter-title]',
      );

    /*
     * Count includes the prototype itself, because selecting the
     * prototype also shows that item itself.
     */
    const count =
      descendantsOf(id).size;

    title.textContent =
      `${node.title} (${count})`;

    checkbox.checked =
      active.has(id);

    registerCheckbox(
      id,
      checkbox,
    );

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
      const childrenElement =
        required<HTMLUListElement>(
          row,
          '[data-filter-children]',
        );

      const nextPath =
        new Set(seenOnPath);

      nextPath.add(id);

      childrenElement.replaceChildren(
        ...children.map((childId) =>
          renderNode(
            childId,
            nextPath,
          ),
        ),
      );
    }

    return row;
  }

  function renderTree() {
    checkboxes.clear();

    const filterableIds =
      [...graph.keys()].filter(isFilterable);

    /*
     * A filterable node is a root when none of its parents are
     * themselves visible/filterable nodes.
     *
     * This also handles a player catalog where a private ancestor
     * isn't part of the viewer's returned ItemOut set.
     */
    const roots =
      filterableIds
        .filter((id) => {
          const node = graph.get(id)!;

          return !node.parentIds.some(
            (parentId) =>
              graph.has(parentId) &&
              isFilterable(parentId),
          );
        })
        .sort(byTitle);

    options.root.replaceChildren(
      ...roots.map((id) =>
        renderNode(
          id,
          new Set(),
        ),
      ),
    );
  }

  function updateCatalog(
    items: CatalogItem[],
  ) {
    const next =
      new Map<string, PrototypeNode>();

    /*
     * First create every known node.
     */
    for (const item of items) {
      next.set(item.entity_id, {
        id: item.entity_id,
        title: item.title,
        parentIds: [
          ...item.prototype_ids,
        ],
        childIds: [],
      });
    }

    /*
     * Then build the reverse edges needed by the UI:
     *
     *     prototype -> items using it
     *
     * Parents not visible in this catalog are deliberately ignored.
     */
    for (const node of next.values()) {
      for (const parentId of node.parentIds) {
        next.get(parentId)?.childIds.push(
          node.id,
        );
      }
    }

    graph = next;

    descendantCache.clear();

    /*
     * Don't retain a checked category that disappeared, or one that
     * no longer has anything built on top of it.
     */
    for (const id of [...active]) {
      if (
        !graph.has(id) ||
        !isFilterable(id)
      ) {
        active.delete(id);
      }
    }

    renderTree();
  }

  function apply(
    items: CatalogItem[],
  ): CatalogItem[] {
    if (active.size === 0) {
      return items;
    }

    const allowed =
      new Set<string>();

    for (const filterId of active) {
      for (
        const itemId of
        descendantsOf(filterId)
      ) {
        allowed.add(itemId);
      }
    }

    return items.filter((item) =>
      allowed.has(item.entity_id),
    );
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
