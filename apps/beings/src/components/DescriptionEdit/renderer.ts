// The description of a being, written in an InfoForm under the button that opens it (ADR 0272). Its
// information's title is the being's shown name too (ADR 0019), so the form keeps it.

import { at, type Renderer } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import { descriptionDraft, getDescription, saveDescription } from '../../lib/information';
import { requiredIn } from '../../lib/template';
import { renderInfoForm } from '../InfoForm/renderer';

export type DescriptionEditOptions = {
  root: HTMLElement;
  tenantId: string;
  renderer: Renderer;
  // The description was saved and the form closed.
  onSaved(): void;
};

export type RenderedDescriptionEdit = {
  // The being the description is of, as it is now.
  show(being: { entityId: string; name: string; hasDescription: boolean }): void;
  // Only those who may write it are offered the button.
  allow(canWrite: boolean): void;
};

const required = requiredIn('Description edit');

export function renderDescriptionEdit(options: DescriptionEditOptions): RenderedDescriptionEdit {
  const { root, tenantId } = options;
  const edit = required<HTMLButtonElement>(root, '[data-edit]');
  const mount = required<HTMLElement>(root, '[data-mount]');

  let being: { entityId: string; name: string; hasDescription: boolean } | null = null;

  edit.addEventListener('click', async () => {
    if (!being) return;

    const { entityId, name: title } = being;

    edit.disabled = true;

    try {
      const info = await getDescription(tenantId, entityId);
      let saved = false;

      edit.hidden = true;
      mount.replaceChildren(
        renderInfoForm(root, {
          initial: descriptionDraft(info, title),
          renderer: at(options.renderer, entityId),
          titleLabel: 'Heading',
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
      being = shown;
      edit.textContent = shown.hasDescription ? 'Edit description' : 'Write a description';
    },

    allow(canWrite) {
      edit.hidden = !canWrite;
    },
  };
}
