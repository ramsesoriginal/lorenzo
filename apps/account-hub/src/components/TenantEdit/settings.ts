// A library's settings, General (the design's screen 13): its name, link name and description as
// fields that are always there for an administrator, saved together from the shell's save bar, which
// says how many changes are not saved (ADR 0412). The Edit-then-Save form of renderTenantEdit stays for
// a repository. Only what changed is sent (PATCH) with the version that was read, so a change made
// meanwhile is the 412 below, not silently overwritten.

import { ApiError } from '../../lib/apiError';
import { createDescriptionEditor } from '../../lib/lorenzoScript';
import { currentShell } from '../../lib/shell';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn } from '../../lib/template';
import { kindNoun, kindNounCapitalized } from '../../lib/tenantKind';
import { getTenant, updateTenant } from '../../lib/tenants';
import type { TenantOut, TenantSummaryOut, TenantUpdate } from '../../lib/types';

const required = requiredIn('Tenant settings');

let formCount = 0;

export type RenderedTenantSettings = {
  // Shows the fields for an administrator of `tenant`, with what it holds now, and drops whatever
  // was there for the tenant before.
  show(tenant: TenantSummaryOut): void;
};

// `root` is <Tenant />'s settings block, one for every tenant shown, so this binds once and `show`
// says which tenant it is for.
export function renderTenantSettings(
  root: HTMLElement,
  onSaved: (tenant: TenantOut) => void,
): RenderedTenantSettings {
  const status = required<HTMLElement>(root, '[data-edit-status]');

  // Counts the tenants shown, so an answer that arrives for an earlier one is dropped.
  let shown = 0;
  let openForm: HTMLFormElement | null = null;

  function drop(): void {
    openForm?.remove();
    openForm = null;
    currentShell()
      ?.saveBar({ save() {}, discard() {} })
      .set(0);
  }

  async function build(target: TenantSummaryOut, turn: number): Promise<void> {
    say(status, 'Loading…');

    try {
      // The summary has no description, and the editor needs the version it is editing: both
      // come from this read.
      let { tenant: current, etag } = await getTenant(target.id, { force: true });

      if (turn !== shown) return;

      const noun = kindNoun(target.kind);
      const form = required<HTMLFormElement>(
        fromTemplate(root.closest('[data-tenant]') ?? root, '[data-tenant-edit-form-template]'),
        '[data-form]',
      );
      const nameInput = required<HTMLInputElement>(form, '[data-name-input]');
      const slugInput = required<HTMLInputElement>(form, '[data-slug-input]');
      const hint = required<HTMLElement>(form, '[data-hint]');
      const descriptionInput = required<HTMLTextAreaElement>(form, '[data-description-input]');
      const formStatus = required<HTMLElement>(form, '[data-form-status]');

      // The save bar does the saving: the form's own buttons are for a page without a shell.
      form.classList.remove('card', 'card-body');
      required<HTMLElement>(form, '[data-actions]').hidden = Boolean(currentShell());

      for (const word of form.querySelectorAll<HTMLElement>('[data-noun-capitalized]')) {
        word.textContent = kindNounCapitalized(target.kind);
      }

      const fill = () => {
        nameInput.value = current.name;
        slugInput.value = current.slug;
        descriptionInput.value = current.description;
      };

      fill();
      hint.id = `tenant-details-hint-${formCount++}`;
      slugInput.setAttribute('aria-describedby', hint.id);
      openForm = form;
      root.append(form);
      // Once the form is in the page, and its value is set, so the preview starts from the text.
      const editor = createDescriptionEditor(descriptionInput);

      say(status, '');

      const changes = () =>
        Number(nameInput.value.trim() !== current.name) +
        Number(slugInput.value !== current.slug) +
        Number(descriptionInput.value.trim() !== current.description);

      const shell = currentShell();
      const bar = shell?.saveBar({
        async save() {
          await save();
        },
        discard() {
          fill();
          void editor.refresh();
          say(formStatus, '');
          bar?.set(0);
        },
      });

      const update = () => bar?.set(changes());

      form.addEventListener('input', update);
      form.addEventListener('change', update);

      async function save(): Promise<void> {
        if (!form.reportValidity()) throw new Error('Check the fields.');

        const patch: TenantUpdate = {};

        if (nameInput.value.trim() !== current.name) patch.name = nameInput.value.trim();
        if (slugInput.value !== current.slug) patch.slug = slugInput.value;
        if (descriptionInput.value.trim() !== current.description) {
          patch.description = descriptionInput.value.trim();
        }

        if (Object.keys(patch).length === 0) return;

        say(formStatus, 'Saving…');

        try {
          const updated = await updateTenant(current.id, patch, etag);

          target.name = updated.name;
          target.slug = updated.slug;

          // The next save needs the version this one made.
          ({ tenant: current, etag } = await getTenant(target.id, { force: true }));

          if (turn !== shown) return;

          fill();
          say(formStatus, '');
          bar?.set(0);
          shell?.toast({ kind: 'ok', title: 'Saved' });
          onSaved(updated);
        } catch (error) {
          if (error instanceof ApiError && error.status === 412) {
            say(
              formStatus,
              `This ${noun} changed while you were editing. Reload the page to use its latest version.`,
            );
          } else {
            sayError(formStatus, error);
          }

          throw error;
        }
      }

      form.addEventListener('submit', (event) => {
        event.preventDefault();
        void save().catch(() => {});
      });
    } catch (error) {
      if (turn !== shown) return;

      sayError(status, error);
    }
  }

  return {
    show(next) {
      shown += 1;
      drop();
      say(status, '');
      root.hidden = next.role !== 'owner' && next.role !== 'orga';

      if (!root.hidden) void build(next, shown);
    },
  };
}
