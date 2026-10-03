import { renderBeingActionPanel, searchBeings } from '../../lib/beingPicker';
import { errorMessage } from '../../lib/errorMessage';
import { onIntent } from '../../lib/hoverIntent';
import { deleteItemInstance, getOwnedItemInstances, setOwner, unsetOwner } from '../../lib/items';
import { giveOrAsk } from '../../lib/moveAnyway';
import { deleteSplitQuestion, isStackRefusal } from '../../lib/settingDown';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { BeingRef, ItemInstance, OwnedGroup } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

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

const required = requiredIn('Instances');

export function renderInstances(options: InstancesOptions): RenderedInstances {
  const { root, tenantId } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const viewing = required<HTMLElement>(root, '[data-viewing]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const groups = required<HTMLElement>(root, '[data-groups]');

  let currentCharacter: BeingRef | null = null;
  let requestId = 0;

  function renderRow(instance: ItemInstance): HTMLLIElement {
    const row = cloneTemplate<HTMLLIElement>(
      required<HTMLTemplateElement>(root, '[data-row-template]'),
    );
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
          window.alert(errorMessage(error));
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
          window.alert(errorMessage(error));
        }
      },
      { signal },
    );

    return row;
  }

  function renderGroup(group: OwnedGroup, rootTitle: string): HTMLElement {
    const section = cloneTemplate<HTMLElement>(
      required<HTMLTemplateElement>(root, '[data-group-template]'),
    );
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
      error.textContent = errorMessage(cause);
    }
  }

  const browse = renderCombobox<BeingRef>(root, {
    search: (query) => searchBeings(tenantId, query),
    onPick(being) {
      browse.input.value = being.name;
      void loadFor(being);
    },
    signal,
  });

  return {
    show() {
      root.hidden = false;
    },

    hide() {
      root.hidden = true;
    },

    destroy() {
      controller.abort();
    },
  };
}
