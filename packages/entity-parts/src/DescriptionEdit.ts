// The description of an entry, written in an InfoForm under the button that opens it (ADR 0272).
// Its information's title is the entry's shown name too (ADR 0019), so the form keeps it.
import type { LorenzoClient } from '@lorenzo/api-client';
import { renderAudienceControl } from '@lorenzo/information-editor';
import { type InfoFormDeps, renderInfoForm } from './InfoForm';
import { descriptionDraft, type informationApi } from './information';
import { errorMessage } from './internal/errorMessage';
import { requiredIn } from './internal/template';
import { at, type Renderer } from './text';

/** What the description is of: its id, the name it is shown by, and whether it has a text of its own. */
export type DescribedEntry = { entityId: string; name: string; hasDescription: boolean };

export type DescriptionEditDeps = InfoFormDeps & {
  client: LorenzoClient;
  information: ReturnType<typeof informationApi>;
  // The label of the form's title: "Display title", "Heading".
  titleLabel: string;
};

export type DescriptionEditOptions = {
  root: HTMLElement;
  tenantId: string;
  renderer: Renderer;
  // The description was saved and the form closed.
  onSaved(): void;
};

export type RenderedDescriptionEdit = {
  // The entry the description is of, as it is now.
  show(entry: DescribedEntry): void;
  // Only those who may write it are offered the button.
  allow(canWrite: boolean): void;
};

const required = requiredIn('Description edit');

export function renderDescriptionEdit(
  deps: DescriptionEditDeps,
  options: DescriptionEditOptions,
): RenderedDescriptionEdit {
  const { root, tenantId } = options;
  const { client, information } = deps;
  const edit = required<HTMLButtonElement>(root, '[data-edit]');
  const mount = required<HTMLElement>(root, '[data-mount]');

  let being: DescribedEntry | null = null;

  let canWrite = false;
  let audience: HTMLDetailsElement | null = null;
  function showAudience() {
    audience?.remove();
    audience = null;
    if (!being?.hasDescription) return;
    audience = renderAudienceControl({
      client,
      tenantId,
      informationId: async () =>
        being ? ((await information.getDescription(tenantId, being.entityId))?.id ?? null) : null,
      onSaved: options.onSaved,
    });
    audience.hidden = !canWrite;
    root.append(audience);
  }

  edit.addEventListener('click', async () => {
    if (!being) return;

    const { entityId, name: title } = being;

    edit.disabled = true;

    try {
      const info = await information.getDescription(tenantId, entityId);
      let saved = false;

      edit.hidden = true;
      if (audience) audience.hidden = true;
      mount.replaceChildren(
        renderInfoForm(deps, root, {
          initial: descriptionDraft(info, title),
          information: info ?? undefined,
          renderer: at(options.renderer, entityId),
          titleLabel: deps.titleLabel,
          textLabel: 'Description',
          showVisibility: info === null,

          onSubmit: async (draft) => {
            await information.saveDescription(tenantId, entityId, info, draft, title);
            saved = true;
          },

          onClose: () => {
            mount.replaceChildren();
            edit.hidden = false;
            showAudience();

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
      showAudience();
      edit.textContent = shown.hasDescription ? 'Edit description' : 'Write a description';
    },

    allow(allowed) {
      canWrite = allowed;
      edit.hidden = !allowed;
      if (audience) audience.hidden = !allowed;
    },
  };
}
