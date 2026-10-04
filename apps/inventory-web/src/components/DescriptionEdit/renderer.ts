// The description of an item with its display title, the item's shown name (ADR 0019, 0112),
// written in an InfoForm under the button that opens it.

import type { Renderer } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import { descriptionDraft, getDescription, saveDescription } from '../../lib/information';
import { requiredIn } from '../../lib/template';
import type { ItemBase } from '../../lib/types';
import { renderInfoForm } from '../InfoForm/renderer';

export type DescriptionEditOptions = {
  root: HTMLElement;
  tenantId: string;
  renderer: Renderer;
  // The description was saved and the form closed.
  onSaved(): void;
};

export type RenderedDescriptionEdit = {
  // The item the description is of, as it is now.
  show(item: ItemBase): void;
  // Only those who may write it are offered the button.
  allow(canWrite: boolean): void;
};

const required = requiredIn('Description edit');

export function renderDescriptionEdit(options: DescriptionEditOptions): RenderedDescriptionEdit {
  const { root, tenantId } = options;
  const edit = required<HTMLButtonElement>(root, '[data-edit]');
  const mount = required<HTMLElement>(root, '[data-mount]');

  let item: ItemBase | null = null;

  edit.addEventListener('click', async () => {
    if (!item) return;

    const { entity_id: entityId, title } = item;

    edit.disabled = true;

    try {
      const info = await getDescription(tenantId, entityId);
      let saved = false;

      edit.hidden = true;
      mount.replaceChildren(
        renderInfoForm(root, {
          initial: descriptionDraft(info, title),
          renderer: options.renderer,
          titleLabel: 'Display title',
          textLabel: 'Description',
          showVisibility: info === null,

          onSubmit: async (draft) => {
            await saveDescription(tenantId, entityId, info, draft, title);
            saved = true;
          },

          onClose: () => {
            mount.replaceChildren();
            edit.hidden = false;

            if (saved) options.onSaved();
          },
        }),
      );
    } catch (error) {
      window.alert(errorMessage(error));
    } finally {
      edit.disabled = false;
    }
  });

  return {
    show(shown) {
      item = shown;
      edit.textContent = shown.descriptions.some((description) => !description.from_entity)
        ? 'Edit description'
        : 'Write a description';
    },

    allow(canWrite) {
      edit.hidden = !canWrite;
    },
  };
}
