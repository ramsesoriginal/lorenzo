// Editing a library's or repository's name, slug and description (ADR 0178 for the repository
// wording) - ADR 0136 for the slug and its stale-edit protection, ADR 0170 for the rest. Tenant
// administration uses OWNER/ORGA, as the existing PATCH route does. `onSaved` gets the saved
// tenant, so the page can show a new name without reloading.

import { ApiError } from '../../lib/apiError';
import { createDescriptionEditor } from '../../lib/lorenzoScript';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn } from '../../lib/template';
import { kindNoun, kindNounCapitalized } from '../../lib/tenantKind';
import { getTenant, updateTenant } from '../../lib/tenants';
import type { TenantOut, TenantSummaryOut, TenantUpdate } from '../../lib/types';

const required = requiredIn('Tenant edit');

let formCount = 0;

export type RenderedTenantEdit = {
  // Shows the Edit button for an administrator of `tenant`, and closes whatever was open for the
  // tenant before.
  show(tenant: TenantSummaryOut): void;
};

// `root` is <Tenant />'s block of the Edit button and <TenantEdit />'s form template. It is one
// block for every tenant shown, so this binds once and `show` says which tenant it is for.
export function renderTenantEdit(
  root: HTMLElement,
  onSaved: (tenant: TenantOut) => void,
): RenderedTenantEdit {
  const edit = required<HTMLButtonElement>(root, '[data-edit]');
  const status = required<HTMLElement>(root, '[data-edit-status]');

  let tenant: TenantSummaryOut | null = null;
  // Counts the tenants shown, so an answer that arrives for an earlier one is dropped.
  let shown = 0;
  let openForm: HTMLFormElement | null = null;

  edit.addEventListener('click', async () => {
    const target = tenant;
    const turn = shown;

    if (!target) return;

    const noun = kindNoun(target.kind);

    edit.disabled = true;
    say(status, 'Loading…');

    try {
      // The summary has no description, and the editor needs the version it is
      // editing: both come from this read.
      const { tenant: current, etag } = await getTenant(target.id, { force: true });

      if (turn !== shown) return;

      // The template may sit anywhere in <Tenant />, not only in this block.
      const form = required<HTMLFormElement>(
        fromTemplate(root.closest('[data-tenant]') ?? root, '[data-tenant-edit-form-template]'),
        '[data-form]',
      );
      const nameInput = required<HTMLInputElement>(form, '[data-name-input]');
      const slugInput = required<HTMLInputElement>(form, '[data-slug-input]');
      const hint = required<HTMLElement>(form, '[data-hint]');
      const descriptionInput = required<HTMLTextAreaElement>(form, '[data-description-input]');
      const save = required<HTMLButtonElement>(form, '[data-save]');
      const cancel = required<HTMLButtonElement>(form, '[data-cancel]');
      const formStatus = required<HTMLElement>(form, '[data-form-status]');

      for (const word of form.querySelectorAll<HTMLElement>('[data-noun-capitalized]')) {
        word.textContent = kindNounCapitalized(target.kind);
      }

      nameInput.value = current.name;
      slugInput.value = current.slug;
      descriptionInput.value = current.description;
      hint.id = `tenant-details-hint-${formCount++}`;
      slugInput.setAttribute('aria-describedby', hint.id);

      const close = () => {
        form.remove();
        openForm = null;
        edit.hidden = false;
        say(status, '');
        edit.disabled = false;
        edit.focus();
      };

      cancel.addEventListener('click', close);
      openForm = form;
      edit.hidden = true;
      root.append(form);

      // Once the form is in the page (a copy of a template belongs to an inert document until then,
      // and the editor keeps the document of its textarea) and its value is set, so the preview
      // starts from the text.
      createDescriptionEditor(descriptionInput);

      say(status, '');
      nameInput.focus();

      let stale = false;

      form.addEventListener('submit', async (event) => {
        event.preventDefault();

        if (save.disabled || stale || !form.reportValidity()) return;

        // Only what changed is sent (PATCH), so a change made to another field
        // meanwhile is the 412 below, not silently overwritten.
        const patch: TenantUpdate = {};

        if (nameInput.value.trim() !== current.name) patch.name = nameInput.value.trim();
        if (slugInput.value !== current.slug) patch.slug = slugInput.value;
        if (descriptionInput.value.trim() !== current.description) {
          patch.description = descriptionInput.value.trim();
        }

        if (Object.keys(patch).length === 0) {
          close();

          return;
        }

        save.disabled = true;
        cancel.disabled = true;
        nameInput.disabled = true;
        slugInput.disabled = true;
        descriptionInput.disabled = true;
        say(formStatus, 'Saving…');

        try {
          const updated = await updateTenant(current.id, patch, etag);

          target.name = updated.name;
          target.slug = updated.slug;

          // Another tenant may be shown by now: it keeps its own line.
          if (turn === shown) {
            close();
            say(status, 'Saved.');
          }

          onSaved(updated);
        } catch (error) {
          stale = error instanceof ApiError && error.status === 412;

          if (stale) {
            say(
              formStatus,
              `This ${noun} changed while you were editing. Cancel and reopen the editor to use its latest version.`,
            );
          } else {
            sayError(formStatus, error);
          }
        } finally {
          save.disabled = stale;
          cancel.disabled = false;
          nameInput.disabled = false;
          slugInput.disabled = false;
          descriptionInput.disabled = false;
        }
      });
    } catch (error) {
      if (turn !== shown) return;

      sayError(status, error);
      edit.disabled = false;
    }
  });

  return {
    show(next) {
      shown += 1;
      openForm?.remove();
      openForm = null;
      tenant = next;

      for (const word of edit.querySelectorAll<HTMLElement>('[data-noun]')) {
        word.textContent = kindNoun(next.kind);
      }

      edit.disabled = false;
      edit.hidden = next.role !== 'owner' && next.role !== 'orga';
      say(status, '');
    },
  };
}
