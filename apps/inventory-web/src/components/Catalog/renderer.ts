import { renderItemForm } from '../ItemForm/renderer';

import {
  readCatalogCache,
  writeCatalogCache,
} from '../../lib/catalogCache';

import {
  deleteCatalogItem,
  getEntityDetail,
  listCatalogItems,
  listItemsUsingPrototype,
  setItemPrototypes,
  updateCatalogItem,
} from '../../lib/items';

import {
  getDescription,
  saveDescription,
} from '../../lib/information';

import {
  saveSlug,
  suggestSlug,
} from '../../lib/slugs';

import type { Renderer } from '../../lib/descriptions';
import type {
  CatalogItem,
  EntitySummary,
} from '../../lib/types';

export type RenderedPanel = {
  element: HTMLElement;
  destroy(): void;
};

export type CatalogOptions = {
  root: HTMLElement;
  tenantId: string;
  viewerId: string;
  viewerIsGm: boolean;
  showIntro: boolean;
  renderer: Renderer;

  renderInstantiate(
    item: CatalogItem,
    onDone: () => void,
  ): RenderedPanel;
};

export type RenderedCatalog = {
  reload(): Promise<void>;
  destroy(): void;
};

function required<T extends Element>(
  root: ParentNode,
  selector: string,
): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Catalog is missing ${selector}.`);
  }

  return element;
}

export function renderCatalog(
  options: CatalogOptions,
): RenderedCatalog {
  const { root } = options;

  const controller = new AbortController();
  const { signal } = controller;

  const intro =
    required<HTMLElement>(root, '[data-intro]');

  const search =
    required<HTMLInputElement>(root, '[data-search]');

  const empty =
    required<HTMLElement>(root, '[data-empty]');

  const error =
    required<HTMLElement>(root, '[data-error]');

  const list =
    required<HTMLUListElement>(root, '[data-list]');

  const rowTemplate =
    required<HTMLTemplateElement>(
      root,
      '[data-row-template]',
    );

  const skeletonTemplate =
    required<HTMLTemplateElement>(
      root,
      '[data-skeleton-template]',
    );

  intro.hidden = options.viewerIsGm;

  let requestId = 0;

  function cloneRow(): HTMLLIElement {
    return rowTemplate.content.firstElementChild!
      .cloneNode(true) as HTMLLIElement;
  }

  function cloneSkeleton(): HTMLLIElement {
    return skeletonTemplate.content.firstElementChild!
      .cloneNode(true) as HTMLLIElement;
  }

  function viewHref(
    entityId: string,
    slug?: string | null,
  ) {
    return slug
      ? `/item/?tenant=${options.tenantId}&slug=${encodeURIComponent(slug)}`
      : `/item/?tenant=${options.tenantId}&id=${entityId}`;
  }

  function renderRow(item: CatalogItem): HTMLLIElement {
    const row = cloneRow();

    const title =
      required<HTMLElement>(row, '[data-title]');

    const publicChip =
      required<HTMLElement>(row, '[data-public]');

    const view =
      required<HTMLAnchorElement>(row, '[data-view]');

    const edit =
      required<HTMLButtonElement>(row, '[data-edit]');

    const instantiate =
      required<HTMLButtonElement>(
        row,
        '[data-instantiate]',
      );

    const remove =
      required<HTMLButtonElement>(row, '[data-delete]');

    const panel =
      required<HTMLElement>(row, '[data-panel]');

    title.textContent = item.title;

    publicChip.hidden =
      !options.viewerIsGm ||
      !item.in_public_catalog;

    view.href = viewHref(item.entity_id);

    edit.hidden = !options.viewerIsGm;
    instantiate.hidden = !options.viewerIsGm;
    remove.hidden = !options.viewerIsGm;

    remove.addEventListener(
      'click',
      async () => {
        if (
          !window.confirm(
            `Delete "${item.title}"? This can't be undone.`,
          )
        ) {
          return;
        }

        remove.disabled = true;

        try {
          await deleteCatalogItem(
            options.tenantId,
            item.entity_id,
          );

          await load(search.value);
        } catch (e) {
          remove.disabled = false;

          window.alert(
            e instanceof Error ? e.message : String(e),
          );
        }
      },
      { signal },
    );

    let destroyEditForm = () => {};
    let destroyInstantiate = () => {};

    function closePanel() {
      destroyEditForm();
      destroyEditForm = () => {};

      destroyInstantiate();
      destroyInstantiate = () => {};

      panel.replaceChildren();

      edit.textContent = 'Edit';
      instantiate.textContent = 'Create instance';
    }

    edit.addEventListener(
      'click',
      async () => {
        const wasOpen =
          edit.textContent === 'Cancel';

        closePanel();

        if (wasOpen) return;

        edit.textContent = 'Cancel';
        panel.textContent = 'Loading…';

        try {
          const [entity, usedBy, info] =
            await Promise.all([
              getEntityDetail(
                options.tenantId,
                item.entity_id,
              ),

              listItemsUsingPrototype(
                options.tenantId,
                item.entity_id,
              ),

              getDescription(
                options.tenantId,
                item.entity_id,
              ),
            ]);

          const parents = new Map(
            entity.prototypes.map(
              (prototype: EntitySummary) => [
                prototype.id,
                prototype.name,
              ],
            ),
          );

          const slug =
            entity.slug ??
            (await suggestSlug(
              options.tenantId,
              item.title,
              'item',
            ).catch(() => ''));

          const rendered = renderItemForm({
            tenantId: options.tenantId,
            renderer: options.renderer,

            initial: {
              name: entity.name,
              parents,
              description: info,
              slug,
              inPublicCatalog:
                item.in_public_catalog,
              usedBy,
            },

            submitLabel: 'Save',

            onSubmit: async (values) => {
              await Promise.all([
                updateCatalogItem(
                  options.tenantId,
                  item.entity_id,
                  values.name,
                  values.inPublicCatalog,
                ),

                setItemPrototypes(
                  options.tenantId,
                  item.entity_id,
                  values.parentIds,
                ),
              ]);

              await saveDescription(
                options.tenantId,
                item.entity_id,
                info,
                values.description,
                values.name,
              );

              await saveSlug(
                options.tenantId,
                item.entity_id,
                entity.slug,
                values.slug,
              );

              closePanel();
              await load(search.value);
            },
          });

          destroyEditForm = rendered.destroy;

          panel.replaceChildren(
            rendered.element,
          );
        } catch (e) {
          panel.textContent =
            e instanceof Error
              ? e.message
              : String(e);
        }
      },
      { signal },
    );

    instantiate.addEventListener(
      'click',
      () => {
        const wasOpen =
          instantiate.textContent === 'Cancel';

        closePanel();

        if (wasOpen) return;

        instantiate.textContent = 'Cancel';

        const rendered =
          options.renderInstantiate(
            item,
            closePanel,
          );

        destroyInstantiate =
          rendered.destroy;

        panel.replaceChildren(
          rendered.element,
        );
      },
      { signal },
    );

    return row;
  }

  function renderItems(items: CatalogItem[]) {
    list.removeAttribute('aria-busy');

    if (items.length === 0) {
      empty.hidden = false;
      list.hidden = true;
      return;
    }

    empty.hidden = true;

    list.replaceChildren(
      ...items.map(renderRow),
    );

    list.hidden = false;
  }

  function renderSkeleton() {
    list.setAttribute('aria-busy', 'true');

    list.replaceChildren(
      ...Array.from(
        { length: 4 },
        () => cloneSkeleton(),
      ),
    );

    list.hidden = false;
  }

  async function load(query: string) {
    const thisRequest = ++requestId;

    error.hidden = true;

    let paintedFromCache = false;

    if (!query) {
      const cached = readCatalogCache(
        options.tenantId,
        options.viewerId,
      );

      if (cached) {
        renderItems(cached);
        paintedFromCache = true;
      }
    }

    if (!paintedFromCache) {
      renderSkeleton();
    }

    try {
      const result = await listCatalogItems(
        options.tenantId,
        query,
      );

      if (thisRequest !== requestId) {
        return;
      }

      renderItems(result);

      if (!query) {
        writeCatalogCache(
          options.tenantId,
          options.viewerId,
          result,
        );
      }
    } catch (e) {
      if (thisRequest !== requestId) {
        return;
      }

      list.removeAttribute('aria-busy');

      if (paintedFromCache) {
        return;
      }

      list.hidden = true;
      error.hidden = false;

      error.textContent =
        e instanceof Error
          ? e.message
          : String(e);
    }
  }

  let debounce:
    | ReturnType<typeof setTimeout>
    | undefined;

  search.addEventListener(
    'input',
    () => {
      clearTimeout(debounce);

      debounce = setTimeout(
        () => void load(search.value),
        300,
      );
    },
    { signal },
  );

  return {
    reload: () => load(search.value),

    destroy() {
      clearTimeout(debounce);
      controller.abort();
    },
  };
}
