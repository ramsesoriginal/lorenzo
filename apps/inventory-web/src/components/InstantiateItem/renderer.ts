import { searchBeings } from '../../lib/beingPicker';
import { errorMessage } from '../../lib/errorMessage';
import { createItemInstance } from '../../lib/items';
import { slugProblem, suggestSlug } from '../../lib/slugs';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { BeingRef, CatalogItem } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

export type InstantiateItemOptions = {
  tenantId: string;
  item: CatalogItem;
  onDone(): void;
};

export type RenderedInstantiateItem = {
  element: HTMLElement;
  destroy(): void;
};

const required = requiredIn('Instantiate item');

function clonePanel(): HTMLElement {
  const template = document.querySelector<HTMLTemplateElement>('#instantiate-item-template');

  if (!template) {
    throw new Error('Instantiate item template not found. Did you render <InstantiateItem />?');
  }

  return cloneTemplate<HTMLElement>(template);
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
  const noOwnerButton = required<HTMLButtonElement>(panel, '[data-no-owner]');
  const status = required<HTMLElement>(panel, '[data-status]');

  // Several rows can have a panel open at once, so ids can't be fixed.
  const id = crypto.randomUUID();

  slugInput.id = `instantiate-${id}-slug`;
  slugLabel.htmlFor = slugInput.id;

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

  let busy = false;

  async function finish(action: () => Promise<string>) {
    if (busy) return;

    checkSlug(slugInput.value);

    busy = true;
    search.disabled = true;
    slugInput.disabled = true;
    noOwnerButton.disabled = true;
    beings.close();
    say(status, '');

    try {
      const message = await action();

      say(status, message);
      window.setTimeout(options.onDone, 1200);
    } catch (error) {
      say(status, errorMessage(error), true);
      search.disabled = false;
      slugInput.disabled = false;
      noOwnerButton.disabled = false;
      busy = false;
    }
  }

  const beings = renderCombobox<BeingRef>(panel, {
    search: (query) => searchBeings(options.tenantId, query),

    onPick(being) {
      void finish(async () => {
        await createItemInstance(
          options.tenantId,
          options.item.entity_id,
          being.entity_id,
          slugInput.value.trim() || undefined,
        );

        return `Created and assigned to ${being.name}.`;
      });
    },

    signal,
  });
  const search = beings.input;

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
      controller.abort();
    },
  };
}
