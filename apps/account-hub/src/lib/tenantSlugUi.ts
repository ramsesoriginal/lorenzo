import { ApiError } from './apiError';
import { createStatusSpan } from './dom';
import { errorMessage } from './errorMessage';
import { getTenant, updateTenantSlug } from './tenants';
import type { TenantSummaryOut } from './types';

// Tenant administration uses OWNER/ORGA, as the existing PATCH route does.
export function renderTenantSlug(tenant: TenantSummaryOut): HTMLElement {
  const section = document.createElement('div');
  section.className = 'tenant-slug';
  const value = document.createElement('p');
  value.className = 'tenant-slug-value';
  value.textContent = `Slug: ${tenant.slug}`;
  section.append(value);
  if (tenant.role !== 'owner' && tenant.role !== 'orga') return section;

  const edit = document.createElement('button');
  edit.type = 'button';
  edit.textContent = 'Edit slug';
  const status = createStatusSpan();
  section.append(edit, status);
  edit.addEventListener('click', async () => {
    edit.disabled = true;
    status.textContent = 'Loading…';
    try {
      const { tenant: current, etag } = await getTenant(tenant.id);
      value.textContent = `Slug: ${current.slug}`;
      const form = document.createElement('form');
      form.className = 'tenant-slug-form';
      const label = document.createElement('label');
      label.textContent = 'Library slug';
      const input = document.createElement('input');
      input.type = 'text';
      input.value = current.slug;
      input.required = true;
      input.pattern = '[a-z0-9]+(-[a-z0-9]+)*';
      input.autocapitalize = 'none';
      input.spellcheck = false;
      label.append(input);
      const hint = document.createElement('p');
      hint.className = 'tenant-slug-hint';
      hint.id = `tenant-slug-hint-${tenant.id}`;
      hint.textContent =
        'Use lowercase letters, numbers, and single hyphens between words. Links using the previous slug will stop working.';
      input.setAttribute('aria-describedby', hint.id);
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
      form.append(label, hint, save, cancel, status);
      section.replaceChildren(value, form);
      status.textContent = '';
      input.focus();
      let stale = false;
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (save.disabled || stale || !form.reportValidity()) return;
        if (input.value === current.slug) {
          close();
          return;
        }
        save.disabled = true;
        cancel.disabled = true;
        input.disabled = true;
        status.textContent = 'Saving…';
        try {
          const updated = await updateTenantSlug(current.id, input.value, etag);
          tenant.slug = updated.slug;
          value.textContent = `Slug: ${updated.slug}`;
          close();
          status.textContent = 'Slug saved.';
        } catch (error) {
          stale = error instanceof ApiError && error.status === 412;
          status.textContent = stale
            ? 'This library changed while you were editing. Cancel and reopen the editor to use its latest version.'
            : error instanceof Error
              ? error.message
              : String(error);
        } finally {
          save.disabled = stale;
          cancel.disabled = false;
          input.disabled = false;
        }
      });
    } catch (error) {
      status.textContent = errorMessage(error);
      edit.disabled = false;
    }
  });
  return section;
}
