import type { Renderer } from '../../lib/descriptions';
import { getDescription, saveDescription } from '../../lib/information';
import {
  deleteCatalogItem,
  getEntityDetail,
  listItemsUsingPrototype,
  setItemPrototypes,
  updateCatalogItem,
} from '../../lib/items';
import { saveSlug, suggestSlug } from '../../lib/slugs';
import type { CatalogItem, EntitySummary } from '../../lib/types';
import { renderItemForm } from '../ItemForm/renderer';
import { createPrototypeFilter } from './filter';
import { createCatalogSearch } from './search';

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

  renderInstantiate(item: CatalogItem, onDone: () => void): RenderedPanel;
  onView(item: CatalogItem): void;
};

export type RenderedCatalog = {
  reload(): Promise<void>;
  destroy(): void;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Catalog is missing ${selector}.`);
  }

  return element;
}

function cloneTemplate<T extends Element>(template: HTMLTemplateElement): T {
  const element = template.content.firstElementChild;

  if (!element) {
    throw new Error('Catalog template is empty.');
  }

  return element.cloneNode(true) as T;
}

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function renderCatalog(options: CatalogOptions): RenderedCatalog {
  const { root } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const intro = required<HTMLElement>(root, '[data-intro]');
  const searchInput = required<HTMLInputElement>(root, '[data-search]');
  const filterRoot = required<HTMLUListElement>(root, '[data-filter]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const list = required<HTMLUListElement>(root, '[data-list]');
  const rowTemplate = required<HTMLTemplateElement>(root, '[data-row-template]');
  const skeletonTemplate = required<HTMLTemplateElement>(root, '[data-skeleton-template]');
  const filterBranchTemplate = required<HTMLTemplateElement>(root, '[data-filter-branch-template]');
  const filterLeafTemplate = required<HTMLTemplateElement>(root, '[data-filter-leaf-template]');

  intro.hidden = !options.showIntro;

  // What shows is the text search's result, narrowed by the ticked prototypes.
  let searchedItems: CatalogItem[] = [];

  const prototypeFilter = createPrototypeFilter({
    root: filterRoot,
    branchTemplate: filterBranchTemplate,
    leafTemplate: filterLeafTemplate,
    signal,
    onChange() {
      renderItems(prototypeFilter.apply(searchedItems));
    },
  });

  function renderRow(item: CatalogItem): HTMLLIElement {
    const row = cloneTemplate<HTMLLIElement>(rowTemplate);
    const title = required<HTMLElement>(row, '[data-title]');
    const publicChip = required<HTMLElement>(row, '[data-public]');
    const view = required<HTMLButtonElement>(row, '[data-view]');
    const edit = required<HTMLButtonElement>(row, '[data-edit]');
    const instantiate = required<HTMLButtonElement>(row, '[data-instantiate]');
    const remove = required<HTMLButtonElement>(row, '[data-delete]');
    const panel = required<HTMLElement>(row, '[data-panel]');

    title.textContent = item.title;
    publicChip.hidden = !options.viewerIsGm || !item.in_public_catalog;
    edit.hidden = !options.viewerIsGm;
    instantiate.hidden = !options.viewerIsGm;
    remove.hidden = !options.viewerIsGm;

    view.addEventListener('click', () => options.onView(item), { signal });

    remove.addEventListener(
      'click',
      async () => {
        if (!window.confirm(`Delete "${item.title}"? This can't be undone.`)) {
          return;
        }

        remove.disabled = true;

        try {
          await deleteCatalogItem(options.tenantId, item.entity_id);
          await catalogSearch.reload();
        } catch (error) {
          remove.disabled = false;
          window.alert(reason(error));
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
        const wasOpen = edit.textContent === 'Cancel';

        closePanel();

        if (wasOpen) {
          return;
        }

        edit.textContent = 'Cancel';
        panel.textContent = 'Loading…';

        try {
          const [entity, usedBy, info] = await Promise.all([
            getEntityDetail(options.tenantId, item.entity_id),
            listItemsUsingPrototype(options.tenantId, item.entity_id),
            getDescription(options.tenantId, item.entity_id),
          ]);

          const parents = new Map(
            entity.prototypes.map((prototype: EntitySummary) => [prototype.id, prototype.name]),
          );

          const slug =
            entity.slug ??
            (await suggestSlug(options.tenantId, item.title, 'item').catch(() => ''));

          const rendered = renderItemForm({
            tenantId: options.tenantId,
            renderer: options.renderer,
            initial: {
              name: entity.name,
              parents,
              description: info,
              slug,
              inPublicCatalog: item.in_public_catalog,
              usedBy,
            },
            submitLabel: 'Save',
            hideCurrentName: true,
            onSubmit: async (values) => {
              await Promise.all([
                updateCatalogItem(
                  options.tenantId,
                  item.entity_id,
                  values.name,
                  values.inPublicCatalog,
                ),
                setItemPrototypes(options.tenantId, item.entity_id, values.parentIds),
              ]);
              await saveDescription(
                options.tenantId,
                item.entity_id,
                info,
                values.description,
                values.name,
              );
              await saveSlug(options.tenantId, item.entity_id, entity.slug, values.slug);

              closePanel();
              await catalogSearch.reload();
            },
          });

          destroyEditForm = rendered.destroy;
          panel.replaceChildren(rendered.element);
        } catch (error) {
          panel.textContent = reason(error);
        }
      },
      { signal },
    );

    instantiate.addEventListener(
      'click',
      () => {
        const wasOpen = instantiate.textContent === 'Cancel';

        closePanel();

        if (wasOpen) {
          return;
        }

        instantiate.textContent = 'Cancel';

        const rendered = options.renderInstantiate(item, closePanel);

        destroyInstantiate = rendered.destroy;
        panel.replaceChildren(rendered.element);
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
    list.replaceChildren(...items.map(renderRow));
    list.hidden = false;
  }

  function renderSkeleton() {
    empty.hidden = true;
    list.setAttribute('aria-busy', 'true');
    list.replaceChildren(
      ...Array.from({ length: 4 }, () => cloneTemplate<HTMLLIElement>(skeletonTemplate)),
    );
    list.hidden = false;
  }

  const catalogSearch = createCatalogSearch({
    input: searchInput,
    tenantId: options.tenantId,
    viewerId: options.viewerId,
    signal,
    // Always the whole catalog, never just a q= result, so it can feed the filter tree.
    onCatalog(items) {
      prototypeFilter.updateCatalog(items);
    },
    onResult(items) {
      searchedItems = items;
      renderItems(prototypeFilter.apply(searchedItems));
    },
    onLoading: renderSkeleton,
    onClearError() {
      error.hidden = true;
      error.textContent = '';
    },
    onError(cause) {
      list.removeAttribute('aria-busy');
      list.hidden = true;
      empty.hidden = true;
      error.hidden = false;
      error.textContent = reason(cause);
    },
  });

  return {
    reload: catalogSearch.reload,
    destroy() {
      catalogSearch.destroy();
      prototypeFilter.destroy();
      controller.abort();
    },
  };
}
