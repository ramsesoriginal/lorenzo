import { type MenuItem, openMenu } from '@lorenzo/app-shell';
import { BRANDING_CSS_URL } from '../../lib/config';
import type { Renderer } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import { onIntent } from '../../lib/hoverIntent';
import { getDescription, saveDescription } from '../../lib/information';
import {
  countMadeByItem,
  deleteCatalogItem,
  getEntityDetail,
  listItemsUsingPrototype,
  setItemPrototypes,
  updateCatalogItem,
} from '../../lib/items';
import { saveSlug, suggestSlug } from '../../lib/slugs';
import { cloneTemplate, requiredIn } from '../../lib/template';
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
  // What the campaigns call their game master, for the pill on what only they see (ADR 0294).
  gmWords: { title: string };

  renderInstantiate(item: CatalogItem, onDone: () => void): RenderedPanel;
  onView(item: CatalogItem): void;
  // A row's View is likely to be clicked next.
  onPrefetch(item: CatalogItem): void;
};

export type RenderedCatalog = {
  reload(): Promise<void>;
  destroy(): void;
};

const required = requiredIn('Catalog');

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

  // The names of the catalog's items, for what each is made from.
  const titles = new Map<string, string>();

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

  // "3 made": read once, and said on every row that is there.
  let madeCounts: Map<string, number> | null = null;

  function paintMade(field: HTMLElement, entityId: string) {
    if (!madeCounts) return;

    const count = madeCounts.get(entityId) ?? 0;

    field.textContent = `${count} made`;
    field.hidden = false;
  }

  function loadMade() {
    countMadeByItem(options.tenantId).then(
      (counts) => {
        madeCounts = counts;

        for (const row of list.querySelectorAll<HTMLElement>('.catalog-row')) {
          const field = row.querySelector<HTMLElement>('[data-made]');

          if (field && row.dataset.entityId) paintMade(field, row.dataset.entityId);
        }
      },
      () => {},
    );
  }

  function renderRow(item: CatalogItem): HTMLLIElement {
    const row = cloneTemplate<HTMLLIElement>(rowTemplate);
    const title = required<HTMLElement>(row, '[data-title]');
    const publicChip = required<HTMLElement>(row, '[data-public]');
    const gmOnly = required<HTMLElement>(row, '[data-gm-only]');
    const kind = required<HTMLElement>(row, '[data-kind]');
    const made = required<HTMLElement>(row, '[data-made]');
    const view = required<HTMLButtonElement>(row, '[data-view]');
    const menu = required<HTMLButtonElement>(row, '[data-menu]');
    const panel = required<HTMLElement>(row, '[data-panel]');

    title.textContent = item.title;
    publicChip.hidden = !options.viewerIsGm || !item.in_public_catalog;
    gmOnly.hidden = !options.viewerIsGm || item.in_public_catalog;
    required<HTMLElement>(gmOnly, '[data-gm-only-label]').textContent =
      `${options.gmWords.title} only`;
    // What it is made from, by name: the line under its title.
    kind.textContent = item.prototype_ids
      .map((id) => titles.get(id))
      .filter((name): name is string => Boolean(name))
      .join(', ');
    kind.hidden = kind.textContent === '';
    menu.setAttribute('aria-describedby', '');
    menu.removeAttribute('aria-describedby');

    row.dataset.entityId = item.entity_id;
    paintMade(made, item.entity_id);

    view.addEventListener(
      'click',
      () => {
        for (const other of list.querySelectorAll('.catalog-row--open')) {
          other.classList.remove('catalog-row--open');
        }

        row.classList.add('catalog-row--open');
        options.onView(item);
      },
      { signal },
    );
    onIntent(view, () => options.onPrefetch(item), signal);

    async function remove() {
      if (!window.confirm(`Delete "${item.title}"? This can't be undone.`)) {
        return;
      }

      try {
        await deleteCatalogItem(options.tenantId, item.entity_id);
        await catalogSearch.reload();
      } catch (error) {
        window.alert(errorMessage(error));
      }
    }

    let destroyPanel = () => {};
    let opened: 'edit' | 'instantiate' | null = null;

    function closePanel() {
      destroyPanel();
      destroyPanel = () => {};
      opened = null;
      panel.replaceChildren();
    }

    // What is open under a row says how to leave it.
    function withCancel(element: HTMLElement): HTMLElement {
      const cancel = document.createElement('button');

      cancel.type = 'button';
      cancel.className = 'btn btn-secondary';
      cancel.textContent = 'Cancel';
      cancel.addEventListener('click', closePanel, { signal });

      const wrap = document.createElement('div');

      wrap.className = 'stack';
      wrap.append(element, cancel);

      return wrap;
    }

    async function edit() {
      if (opened === 'edit') return closePanel();

      closePanel();
      opened = 'edit';
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
          entity.slug ?? (await suggestSlug(options.tenantId, item.title, 'item').catch(() => ''));

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

        destroyPanel = rendered.destroy;
        panel.replaceChildren(withCancel(rendered.element));
      } catch (error) {
        panel.textContent = errorMessage(error);
      }
    }

    function instantiate() {
      if (opened === 'instantiate') return closePanel();

      closePanel();
      opened = 'instantiate';

      const rendered = options.renderInstantiate(item, closePanel);

      destroyPanel = rendered.destroy;
      panel.replaceChildren(withCancel(rendered.element));
    }

    // What can be done with the item, off the row (IN4).
    menu.addEventListener(
      'click',
      () => {
        const entries: MenuItem[] = [
          { label: 'View', icon: 'kind-item', run: () => options.onView(item) },
        ];

        if (options.viewerIsGm) {
          entries.push(
            { label: 'Edit', run: () => void edit() },
            { label: 'Create instance', run: instantiate },
            { separator: true },
            { label: 'Delete', danger: true, run: () => void remove() },
          );
        }

        openMenu(menu, entries, {
          label: `Actions for ${item.title}`,
          sprite: `${BRANDING_CSS_URL}/icons.svg`,
        });
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
      titles.clear();

      for (const found of items) titles.set(found.entity_id, found.title);

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
      error.textContent = errorMessage(cause);
    },
  });

  loadMade();

  return {
    reload: async () => {
      await catalogSearch.reload();
      loadMade();
    },
    destroy() {
      catalogSearch.destroy();
      prototypeFilter.destroy();
      controller.abort();
    },
  };
}
