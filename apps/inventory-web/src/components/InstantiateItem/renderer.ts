import { renderBeingSuggestions } from '../../lib/beingPicker';
import { listBeings } from '../../lib/beings';
import { createItemInstance } from '../../lib/items';
import { slugProblem, suggestSlug } from '../../lib/slugs';
import type { CatalogItem } from '../../lib/types';

export type InstantiateItemOptions = {
  tenantId: string;
  item: CatalogItem;
  onDone(): void;
};

export type RenderedInstantiateItem = {
  element: HTMLElement;
  destroy(): void;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Instantiate item is missing ${selector}.`);
  }

  return element;
}

function clonePanel(): HTMLElement {
  const template = document.querySelector<HTMLTemplateElement>('#instantiate-item-template');

  if (!template) {
    throw new Error('Instantiate item template not found. Did you render <InstantiateItem />?');
  }

  const first = template.content.firstElementChild;

  if (!first) {
    throw new Error('Instantiate item template is empty.');
  }

  return first.cloneNode(true) as HTMLElement;
}

function checkSlug(value: string): void {
  const slug = value.trim();

  if (!slug) return;

  const problem = slugProblem(slug);

  if (problem) {
    throw new Error(problem);
  }
}

export function renderInstantiateItem(options: InstantiateItemOptions): RenderedInstantiateItem {
  const panel = clonePanel();
  const controller = new AbortController();
  const { signal } = controller;

  const slugLabel = required<HTMLLabelElement>(panel, '[data-slug-label]');
  const slugInput = required<HTMLInputElement>(panel, '[data-slug]');
  const combobox = required<HTMLElement>(panel, '[data-combobox]');
  const search = required<HTMLInputElement>(panel, '[data-search]');
  const suggestions = required<HTMLUListElement>(panel, '[data-suggestions]');
  const noOwnerButton = required<HTMLButtonElement>(panel, '[data-no-owner]');
  const status = required<HTMLElement>(panel, '[data-status]');

  // Several rows can have a panel open at once, so ids can't be fixed.
  const id = crypto.randomUUID();

  slugInput.id = `instantiate-${id}-slug`;
  slugLabel.htmlFor = slugInput.id;
  suggestions.id = `instantiate-${id}-suggestions`;
  search.setAttribute('aria-controls', suggestions.id);

  // An instance gets no slug unless one is typed, so the suggestion is only a placeholder.
  slugInput.placeholder = 'e.g. iron-sword-1';

  suggestSlug(options.tenantId, options.item.title, 'instance').then(
    (suggestion) => {
      if (suggestion) {
        slugInput.placeholder = `e.g. ${suggestion}`;
      }
    },
    () => {},
  );

  function closeSuggestions() {
    suggestions.hidden = true;
    suggestions.replaceChildren();
    search.setAttribute('aria-expanded', 'false');
  }

  let busy = false;

  async function finish(action: () => Promise<string>) {
    if (busy) return;

    checkSlug(slugInput.value);

    busy = true;
    search.disabled = true;
    slugInput.disabled = true;
    noOwnerButton.disabled = true;
    closeSuggestions();
    status.hidden = true;
    status.classList.remove('error-text');

    try {
      const message = await action();

      status.hidden = false;
      status.textContent = message;
      window.setTimeout(options.onDone, 1200);
    } catch (error) {
      status.hidden = false;
      status.classList.add('error-text');
      status.textContent = error instanceof Error ? error.message : String(error);
      search.disabled = false;
      slugInput.disabled = false;
      noOwnerButton.disabled = false;
      busy = false;
    }
  }

  let debounce: ReturnType<typeof setTimeout> | undefined;

  search.addEventListener(
    'input',
    () => {
      clearTimeout(debounce);

      const query = search.value.trim();

      if (!query) {
        closeSuggestions();
        return;
      }

      debounce = setTimeout(async () => {
        try {
          const result = await listBeings(options.tenantId, query);

          renderBeingSuggestions(suggestions, result.items, (being) => {
            void finish(async () => {
              await createItemInstance(
                options.tenantId,
                options.item.entity_id,
                being.entity_id,
                slugInput.value.trim() || undefined,
              );

              return `Created and assigned to ${being.name}.`;
            });
          });

          suggestions.hidden = false;
          search.setAttribute('aria-expanded', 'true');
        } catch {
          closeSuggestions();
        }
      }, 200);
    },
    { signal },
  );

  search.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape') {
        closeSuggestions();
      }
    },
    { signal },
  );

  document.addEventListener(
    'click',
    (event) => {
      if (!combobox.contains(event.target as Node)) {
        closeSuggestions();
      }
    },
    { signal },
  );

  noOwnerButton.addEventListener(
    'click',
    () => {
      void finish(async () => {
        await createItemInstance(
          options.tenantId,
          options.item.entity_id,
          undefined,
          slugInput.value.trim() || undefined,
        );

        return 'Created without an owner.';
      });
    },
    { signal },
  );

  window.setTimeout(() => search.focus(), 0);

  return {
    element: panel,

    destroy() {
      clearTimeout(debounce);
      controller.abort();
    },
  };
}
