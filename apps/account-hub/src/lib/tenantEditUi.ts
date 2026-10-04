import { ApiError } from './apiError';
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import { getTenant, updateTenant } from './tenants';
import type { TenantOut, TenantSummaryOut, TenantUpdate } from './types';

function field(
  labelText: string,
  control: HTMLInputElement | HTMLTextAreaElement,
): HTMLLabelElement {
  const label = document.createElement('label');
  label.textContent = labelText;
  label.append(control);
  return label;
}

// Editing a library's name, slug and description - ADR 0136 for the slug and
// its stale-edit protection, ADR 0170 for the rest. Tenant administration uses
// OWNER/ORGA, as the existing PATCH route does. `onSaved` gets the saved
// library, so the page can show a new name without reloading.
export function renderTenantEdit(
  tenant: TenantSummaryOut,
  onSaved: (tenant: TenantOut) => void,
): HTMLElement {
  const section = document.createElement('div');
  section.className = 'tenant-details';
  const value = document.createElement('p');
  value.className = 'tenant-details-value';
  value.textContent = `Slug: ${tenant.slug}`;
  section.append(value);
  if (tenant.role !== 'owner' && tenant.role !== 'orga') return section;

  const edit = document.createElement('button');
  edit.type = 'button';
  edit.textContent = 'Edit library';
  const status = createStatusSpan();
  section.append(edit, status);
  edit.addEventListener('click', async () => {
    edit.disabled = true;
    status.textContent = 'Loading…';
    try {
      // The summary has no description, and the editor needs the version it is
      // editing: both come from this read.
      const { tenant: current, etag } = await getTenant(tenant.id);
      value.textContent = `Slug: ${current.slug}`;
      const form = document.createElement('form');
      form.className = 'tenant-details-form';

      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.value = current.name;
      nameInput.required = true;

      const slugInput = document.createElement('input');
      slugInput.type = 'text';
      slugInput.value = current.slug;
      slugInput.required = true;
      slugInput.pattern = '[a-z0-9]+(-[a-z0-9]+)*';
      slugInput.autocapitalize = 'none';
      slugInput.spellcheck = false;
      const hint = document.createElement('p');
      hint.className = 'tenant-details-hint';
      hint.id = `tenant-details-hint-${tenant.id}`;
      hint.textContent =
        'Use lowercase letters, numbers, and single hyphens between words. Links using the previous slug will stop working.';
      slugInput.setAttribute('aria-describedby', hint.id);

      const descriptionInput = document.createElement('textarea');
      descriptionInput.rows = 3;
      descriptionInput.value = current.description;

      const save = document.createElement('button');
      save.type = 'submit';
      save.textContent = 'Save';
      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.textContent = 'Cancel';
      const close = () => {
        section.replaceChildren(value, edit, status);
        status.textContent = '';
        edit.disabled = false;
        edit.focus();
      };
      cancel.addEventListener('click', close);
      form.append(
        field('Library name', nameInput),
        field('Library slug', slugInput),
        hint,
        field('Description', descriptionInput),
        save,
        cancel,
        status,
      );
      section.replaceChildren(value, form);
      status.textContent = '';
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
        status.textContent = 'Saving…';
        try {
          const updated = await updateTenant(current.id, patch, etag);
          tenant.name = updated.name;
          tenant.slug = updated.slug;
          value.textContent = `Slug: ${updated.slug}`;
          close();
          status.textContent = 'Saved.';
          onSaved(updated);
        } catch (error) {
          stale = error instanceof ApiError && error.status === 412;
          if (stale) {
            status.textContent =
              'This library changed while you were editing. Cancel and reopen the editor to use its latest version.';
          } else {
            showError(status, error);
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
      showError(status, error);
      edit.disabled = false;
    }
  });
  return section;
}
