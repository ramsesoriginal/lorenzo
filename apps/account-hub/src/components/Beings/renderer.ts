// The beings of one library (RFC 0013), on /beings. Beings are tenant-scoped, but a hand-off needs a
// specific campaign context: only campaigns the caller GMs in the library are offered.

import { createCharacter, listBeings, updateCharacter } from '../../lib/characters';
import { isTenantAdmin } from '../../lib/format';
import { bindInlineRename } from '../../lib/inlineRename';
import { say, sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { isRepository } from '../../lib/tenantKind';
import type { BeingSummaryOut, CampaignSummaryOut, TenantSummaryOut } from '../../lib/types';
import { renderHandoff } from '../Handoff/renderer';

const required = requiredIn('Beings');

const SEARCH_DEBOUNCE_MS = 300;

export type BeingsInput = {
  tenant: TenantSummaryOut;
  gmCampaigns: CampaignSummaryOut[];
  onChanged: () => void;
};

// `root` is the <Beings /> block; the promise is its first list.
export async function renderBeings(root: HTMLElement, input: BeingsInput): Promise<void> {
  const { tenant, gmCampaigns, onChanged } = input;
  const readOnly = isRepository(tenant);
  const search = required<HTMLInputElement>(root, '[data-search]');
  const none = required<HTMLElement>(root, '[data-none]');
  const list = required<HTMLElement>(root, '[data-list]');

  required<HTMLElement>(root, '[data-name]').textContent = tenant.name;
  required<HTMLElement>(root, '[data-repository-badge]').hidden = !readOnly;

  function renderBeing(being: BeingSummaryOut): HTMLElement {
    if (readOnly) {
      const row = cloneRoot(root, '[data-readonly-template]');

      row.textContent = being.name;

      return row;
    }

    const row = cloneRoot(root, '[data-being-template]');
    const handoffButton = required<HTMLButtonElement>(row, '[data-handoff-button]');
    const slot = required<HTMLElement>(row, '[data-handoff-slot]');

    required<HTMLElement>(row, '[data-being-name]').textContent = being.name;

    bindInlineRename(
      {
        name: required<HTMLElement>(row, '[data-being-name]'),
        renameButton: required<HTMLButtonElement>(row, '[data-rename]'),
        form: required<HTMLFormElement>(row, '[data-rename-form]'),
        input: required<HTMLInputElement>(row, '[data-rename-input]'),
        cancel: required<HTMLButtonElement>(row, '[data-rename-cancel]'),
        status: required<HTMLElement>(row, '[data-status]'),
        alongside: [handoffButton],
      },
      being.name,
      async (newName) => {
        await updateCharacter(tenant.id, being.entity_id, { name: newName });
        onChanged();
      },
    );

    handoffButton.addEventListener('click', () => {
      const handoff = cloneRoot(root, '[data-handoff-template]');

      // The panel takes the button's place; it is in the page before it is bound, as the editors
      // and pickers inside need to be.
      handoffButton.hidden = true;
      slot.replaceChildren(handoff);
      renderHandoff(handoff, {
        being,
        tenantId: tenant.id,
        gmCampaigns,
        canReadRoster: isTenantAdmin(tenant),
        onDone: onChanged,
      });
    });

    return row;
  }

  // Only the newest answer paints: a search typed over a slower one.
  let latest = 0;

  // listBeings(tenantId, q) already accepts q (ADR 0079) - this is purely a missing input
  // element (RFC 0017 (b)).
  async function showResults(q?: string): Promise<void> {
    const turn = ++latest;
    const page = await listBeings(tenant.id, q);

    if (turn !== latest) return;

    none.hidden = page.items.length > 0;
    none.textContent = q ? 'No beings match.' : 'No beings yet.';
    list.hidden = page.items.length === 0;
    list.replaceChildren(...page.items.map(renderBeing));
  }

  let debounceHandle: ReturnType<typeof setTimeout> | undefined;

  search.addEventListener('input', () => {
    clearTimeout(debounceHandle);
    debounceHandle = setTimeout(() => void showResults(search.value.trim()), SEARCH_DEBOUNCE_MS);
  });

  if (!readOnly) {
    const form = required<HTMLFormElement>(root, '[data-create-form]');
    const nameInput = required<HTMLInputElement>(root, '[data-create-name]');
    const status = required<HTMLElement>(root, '[data-create-status]');

    form.hidden = false;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const name = nameInput.value.trim();

      if (name === '') return;

      say(status, 'Creating…');

      try {
        // No owner_player_id - that's exactly what makes this a being (is_pc: false) rather than
        // a player character.
        await createCharacter(tenant.id, { name, player_ids: [] });
        onChanged();
      } catch (e) {
        sayError(status, e);
      }
    });
  }

  await showResults();
}
