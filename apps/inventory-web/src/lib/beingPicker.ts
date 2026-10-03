import { createCombobox, type Suggestion } from '../components/Combobox/renderer';
import { beingNamed, unknownSlug } from './addresses';
import { listBeings } from './beings';
import { errorMessage } from './errorMessage';
import { listGroups, matchingGroups } from './groups';
import type { BeingRef, BeingSummary } from './types';

function beingLabel(being: BeingSummary): string {
  // is_pc is genuinely three-valued (BeingSummary) - null means no
  // Character row exists at all, distinct from false.
  if (being.is_pc === null) return `${being.name} (being)`;

  return being.is_pc ? being.name : `${being.name} (NPC)`;
}

/** The beings matching `query`, as a combobox offers them. */
export async function searchBeings(
  tenantId: string,
  query: string,
): Promise<Suggestion<BeingRef>[]> {
  const found = await listBeings(tenantId, query);

  return found.items.map((being) => ({ label: beingLabel(being), value: being }));
}

/** Beings, then groups (ADR 0124): a group can own things too, so it's offered alongside. */
export async function searchBeingsAndGroups(
  tenantId: string,
  query: string,
): Promise<Suggestion<BeingRef>[]> {
  const [beings, groups] = await Promise.all([
    searchBeings(tenantId, query),
    listGroups(tenantId).catch(() => [] as BeingRef[]),
  ]);

  return [
    ...beings,
    ...matchingGroups(groups, query).map((group) => ({
      label: `${group.name} (group)`,
      value: group,
    })),
  ];
}

// A panel that finds a being - by name search against GET /tenants/{t}/beings
// (ADR 0078: every being in the tenant, PCs/NPCs/bare beings alike), and the
// tenant's groups, which can own things too (ADR 0124) - or by
// pasting an entity id or slug directly (still handy as a quick-entry shortcut even
// now that search covers everything) - then runs performAction against
// whichever was picked. Ownership itself already accepts any entity id, no
// character-only validation server-side, so this works for any being.
// Shared by every "assign/reassign/give to a being" flow in this app.
// extraFields (e.g. a "how many?" quantity input for a partial give) are
// mounted above the search box - callers read their own values inside
// performAction, this panel doesn't know or care what they are.
export function renderBeingActionPanel(
  tenantId: string,
  performAction: (being: BeingRef) => Promise<string>,
  onDone: () => void,
  extraFields: HTMLElement[] = [],
): HTMLElement {
  const panel = document.createElement('div');
  panel.className = 'character-picker-panel';
  panel.append(...extraFields);

  const rawIdRow = document.createElement('div');
  rawIdRow.className = 'being-id-row';
  const rawIdInput = document.createElement('input');
  rawIdInput.type = 'text';
  rawIdInput.className = 'text-input';
  rawIdInput.placeholder = "or a being's id or slug…";
  rawIdInput.setAttribute('aria-label', "Being's id or slug");
  const rawIdButton = document.createElement('button');
  rawIdButton.type = 'button';
  rawIdButton.textContent = 'Use ID';
  rawIdRow.append(rawIdInput, rawIdButton);

  const statusEl = document.createElement('p');
  statusEl.className = 'picker-status';
  statusEl.hidden = true;

  const picker = createCombobox<BeingRef>({
    label: 'Search beings',
    placeholder: 'Search beings…',
    search: (query) => searchBeingsAndGroups(tenantId, query),
    onPick: (being) => void pick(being),
  });
  const input = picker.input;

  panel.append(picker.element, rawIdRow, statusEl);

  let busy = false;
  async function pick(being: BeingRef) {
    if (busy) return;
    busy = true;
    input.disabled = true;
    rawIdButton.disabled = true;
    try {
      const message = await performAction(being);
      statusEl.hidden = false;
      statusEl.classList.remove('error-text');
      statusEl.textContent = message;
      window.setTimeout(onDone, 1200);
    } catch (e) {
      statusEl.hidden = false;
      statusEl.classList.add('error-text');
      statusEl.textContent = errorMessage(e);
      input.disabled = false;
      rawIdButton.disabled = false;
      busy = false;
    }
  }

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') onDone();
  });

  // An id, or a slug (ADR 0135).
  rawIdButton.addEventListener('click', async () => {
    const value = rawIdInput.value.trim();
    if (!value) return;
    const showError = (message: string) => {
      statusEl.hidden = false;
      statusEl.classList.add('error-text');
      statusEl.textContent = message;
    };
    try {
      const being = await beingNamed(tenantId, value);
      if (being) void pick(being);
      else showError(unknownSlug(value));
    } catch (e) {
      showError(errorMessage(e));
    }
  });

  window.setTimeout(() => input.focus(), 0);
  return panel;
}
