// A panel that finds a being - by name search against GET /tenants/{t}/beings (ADR 0078: every
// being in the tenant, PCs/NPCs/bare beings alike), and the tenant's groups, which can own
// things too (ADR 0124) - or by an entity id or slug typed in (ADR 0135), then runs
// `perform` against whichever was picked. Ownership accepts any entity id, with no
// character-only validation server-side, so this works for any being. Shared by every
// "assign/reassign/give to a being" flow in this app.

import { beingNamed, unknownSlug } from '../../lib/addresses';
import { searchBeingsAndGroups } from '../../lib/beingPicker';
import { errorMessage } from '../../lib/errorMessage';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { BeingRef } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

export type BeingPickerOptions = {
  tenantId: string;
  // What to do with the being picked: says what happened, or throws to leave the panel open.
  perform(being: BeingRef): Promise<string>;
  // After `perform` has said what happened, or on Escape.
  onDone(): void;
  // Fields of the caller's own (a "how many?" for a partial give), above the search box: the
  // caller reads them inside `perform`.
  extraFields?: HTMLElement[];
};

const required = requiredIn('Being picker');

export function renderBeingPicker(options: BeingPickerOptions): HTMLElement {
  const { tenantId } = options;
  const panel = cloneTemplate<HTMLElement>(
    required<HTMLTemplateElement>(document, '[data-being-picker-template]'),
  );
  const rawId = required<HTMLInputElement>(panel, '[data-raw-id]');
  const rawIdButton = required<HTMLButtonElement>(panel, '[data-raw-id-button]');
  const status = required<HTMLElement>(panel, '[data-status]');

  required<HTMLElement>(panel, '[data-extra]').append(...(options.extraFields ?? []));

  let busy = false;

  async function pick(being: BeingRef) {
    if (busy) return;

    busy = true;
    search.input.disabled = true;
    rawIdButton.disabled = true;

    try {
      say(status, await options.perform(being));
      window.setTimeout(options.onDone, 1200);
    } catch (error) {
      say(status, errorMessage(error), true);
      search.input.disabled = false;
      rawIdButton.disabled = false;
      busy = false;
    }
  }

  const search = renderCombobox<BeingRef>(panel, {
    search: (query) => searchBeingsAndGroups(tenantId, query),
    onPick: (being) => void pick(being),
  });

  search.input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') options.onDone();
  });

  rawIdButton.addEventListener('click', async () => {
    const value = rawId.value.trim();

    if (!value) return;

    try {
      const being = await beingNamed(tenantId, value);

      if (being) {
        void pick(being);
      } else {
        say(status, unknownSlug(value), true);
      }
    } catch (error) {
      say(status, errorMessage(error), true);
    }
  });

  window.setTimeout(() => search.input.focus(), 0);

  return panel;
}
