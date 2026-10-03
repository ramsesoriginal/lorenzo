import { renderBeingActionPanel, renderBeingSuggestions } from '../../lib/beingPicker';
import { listBeings } from '../../lib/beings';
import { onIntent } from '../../lib/hoverIntent';
import { deleteItemInstance, getOwnedItemInstances, setOwner, unsetOwner } from '../../lib/items';
import { giveOrAsk } from '../../lib/moveAnyway';
import { deleteSplitQuestion, isStackRefusal } from '../../lib/settingDown';
import type { BeingRef, ItemInstance, OwnedGroup } from '../../lib/types';

export type InstancesOptions = {
  root: HTMLElement;
  tenantId: string;
  viewerIsGm: boolean;
  onView(instance: ItemInstance): void;
  // A row's View is likely to be clicked next.
  onPrefetch(instance: ItemInstance): void;
};

export type RenderedInstances = {
  show(): void;
  hide(): void;
  destroy(): void;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Instances is missing ${selector}.`);
  }

  return element;
}

function cloneTemplate<T extends Element>(root: ParentNode, selector: string): T {
  const template = required<HTMLTemplateElement>(root, selector);
  const first = template.content.firstElementChild;

  if (!first) {
    throw new Error(`Instances template ${selector} is empty.`);
  }

  return first.cloneNode(true) as T;
}

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function renderInstances(options: InstancesOptions): RenderedInstances {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const browseLabel = required<HTMLElement>(root, '[data-browse-label]');
  const browseCombobox = required<HTMLElement>(root, '[data-browse-combobox]');
  const browseSearch = required<HTMLInputElement>(root, '[data-browse-search]');
  const browseSuggestions = required<HTMLUListElement>(root, '[data-browse-suggestions]');
  const viewing = required<HTMLElement>(root, '[data-viewing]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const groups = required<HTMLElement>(root, '[data-groups]');

  browseLabel.id = `instances-browse-label-${crypto.randomUUID()}`;
  browseSuggestions.id = `instances-browse-suggestions-${crypto.randomUUID()}`;
  browseSearch.setAttribute('aria-labelledby', browseLabel.id);
  browseSearch.setAttribute('aria-controls', browseSuggestions.id);

  let currentCharacter: BeingRef | null = null;
  let requestId = 0;

  function closeBrowseSuggestions() {
    browseSuggestions.hidden = true;
    browseSuggestions.replaceChildren();
    browseSearch.setAttribute('aria-expanded', 'false');
  }

  function renderRow(instance: ItemInstance): HTMLLIElement {
    const row = cloneTemplate<HTMLLIElement>(root, '[data-row-template]');
    const title = required<HTMLElement>(row, '[data-title]');
    const view = required<HTMLButtonElement>(row, '[data-view]');
    const reassign = required<HTMLButtonElement>(row, '[data-reassign]');
    const unassign = required<HTMLButtonElement>(row, '[data-unassign]');
    const remove = required<HTMLButtonElement>(row, '[data-delete]');
    const panel = required<HTMLElement>(row, '[data-panel]');

    title.textContent =
      instance.quantity && instance.quantity > 1
        ? `${instance.title} ×${instance.quantity}`
        : instance.title;

    if (instance.slug) {
      const slug = document.createElement('code');

      slug.className = 'catalog-row-slug';
      slug.textContent = instance.slug;
      title.append(' ', slug);
    }

    view.addEventListener('click', () => options.onView(instance), { signal });
    onIntent(view, () => options.onPrefetch(instance), signal);
    unassign.hidden = !instance.owner_entity_id;

    unassign.addEventListener(
      'click',
      async () => {
        unassign.disabled = true;

        try {
          await giveOrAsk((flags) => unsetOwner(tenantId, instance.entity_id, flags), {
            canOverride: options.viewerIsGm,
            ask: (question) => window.confirm(question),
          });

          if (currentCharacter) {
            void loadFor(currentCharacter);
          }
        } catch (error) {
          unassign.disabled = false;
          window.alert(reason(error));
        }
      },
      { signal },
    );

    reassign.addEventListener(
      'click',
      () => {
        const wasOpen = panel.childElementCount > 0;

        panel.replaceChildren();

        if (wasOpen) {
          reassign.textContent = 'Reassign';
          return;
        }

        reassign.textContent = 'Cancel';

        const picker = renderBeingActionPanel(
          tenantId,
          async (being) => {
            await giveOrAsk(
              (flags) => setOwner(tenantId, instance.entity_id, being.entity_id, false, flags),
              {
                canOverride: options.viewerIsGm,
                ask: (question) => window.confirm(question),
              },
            );

            return `Reassigned to ${being.name}.`;
          },
          () => {
            panel.replaceChildren();
            reassign.textContent = 'Reassign';

            if (currentCharacter) {
              void loadFor(currentCharacter);
            }
          },
        );

        panel.append(picker);
      },
      { signal },
    );

    remove.addEventListener(
      'click',
      async () => {
        if (!window.confirm(`Delete "${instance.title}"? This can't be undone.`)) {
          return;
        }

        remove.disabled = true;

        try {
          try {
            await deleteItemInstance(tenantId, instance.entity_id);
          } catch (error) {
            if (!isStackRefusal(error) || !window.confirm(deleteSplitQuestion(instance.title))) {
              throw error;
            }

            await deleteItemInstance(tenantId, instance.entity_id, { split: true });
          }

          if (currentCharacter) {
            void loadFor(currentCharacter);
          }
        } catch (error) {
          remove.disabled = false;
          window.alert(reason(error));
        }
      },
      { signal },
    );

    return row;
  }

  function renderGroup(group: OwnedGroup, rootTitle: string): HTMLElement {
    const section = cloneTemplate<HTMLElement>(root, '[data-group-template]');
    const heading = required<HTMLElement>(section, '[data-heading]');
    const list = required<HTMLUListElement>(section, '[data-list]');

    heading.textContent = group.container?.name ?? rootTitle;
    list.replaceChildren(...group.item_instances.map(renderRow));

    return section;
  }

  async function loadFor(character: BeingRef) {
    currentCharacter = character;
    const thisRequest = ++requestId;

    viewing.hidden = false;
    viewing.textContent = `Viewing ${character.name}'s inventory.`;
    empty.hidden = true;
    error.hidden = true;
    groups.replaceChildren();

    try {
      const response = await getOwnedItemInstances(tenantId, character.entity_id);

      if (thisRequest !== requestId) {
        return;
      }

      const nonEmptyGroups = response.groups.filter((group) => group.item_instances.length > 0);

      if (nonEmptyGroups.length === 0) {
        empty.hidden = false;
        empty.textContent = `${character.name} isn't carrying anything.`;
        return;
      }

      groups.replaceChildren(...nonEmptyGroups.map((group) => renderGroup(group, character.name)));
    } catch (cause) {
      if (thisRequest !== requestId) {
        return;
      }

      error.hidden = false;
      error.textContent = reason(cause);
    }
  }

  let browseDebounce: ReturnType<typeof setTimeout> | undefined;

  browseSearch.addEventListener(
    'input',
    () => {
      clearTimeout(browseDebounce);

      const query = browseSearch.value.trim();

      if (!query) {
        closeBrowseSuggestions();
        return;
      }

      browseDebounce = setTimeout(async () => {
        try {
          const result = await listBeings(tenantId, query);

          renderBeingSuggestions(browseSuggestions, result.items, (being) => {
            browseSearch.value = being.name;
            closeBrowseSuggestions();
            void loadFor(being);
          });

          browseSuggestions.hidden = false;
          browseSearch.setAttribute('aria-expanded', 'true');
        } catch {
          closeBrowseSuggestions();
        }
      }, 200);
    },
    { signal },
  );

  browseSearch.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape') {
        closeBrowseSuggestions();
      }
    },
    { signal },
  );

  document.addEventListener(
    'click',
    (event) => {
      if (!browseCombobox.contains(event.target as Node)) {
        closeBrowseSuggestions();
      }
    },
    { signal },
  );

  return {
    show() {
      root.hidden = false;
    },

    hide() {
      root.hidden = true;
    },

    destroy() {
      clearTimeout(browseDebounce);
      controller.abort();
    },
  };
}
