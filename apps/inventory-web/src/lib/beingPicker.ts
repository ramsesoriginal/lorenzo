import { listBeings } from './beings';
import { listGroups, matchingGroups } from './groups';
import type { BeingRef, BeingSummary } from './types';

/** Beings, then groups (ADR 0124): a group can own things too, so it's offered alongside. */
export function renderBeingSuggestions(
  list: HTMLUListElement,
  beings: BeingSummary[],
  onPick: (being: BeingRef) => void,
  groups: BeingRef[] = [],
) {
  if (beings.length === 0 && groups.length === 0) {
    list.hidden = true;
    list.replaceChildren();
    return;
  }
  list.replaceChildren();
  for (const being of beings) {
    const li = document.createElement('li');
    li.className = 'combobox-suggestion';
    li.setAttribute('role', 'option');
    const button = document.createElement('button');
    button.type = 'button';
    // is_pc is genuinely three-valued (BeingSummary) - null means no
    // Character row exists at all, distinct from false.
    button.textContent =
      being.is_pc === null
        ? `${being.name} (being)`
        : being.is_pc
          ? being.name
          : `${being.name} (NPC)`;
    button.addEventListener('click', () => onPick(being));
    li.append(button);
    list.append(li);
  }
  for (const group of groups) {
    const li = document.createElement('li');
    li.className = 'combobox-suggestion';
    li.setAttribute('role', 'option');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${group.name} (group)`;
    button.addEventListener('click', () => onPick(group));
    li.append(button);
    list.append(li);
  }
  list.hidden = false;
}

/** Beings and groups matching `query`, for a being search. */
export async function searchBeingsAndGroups(
  tenantId: string,
  query: string,
): Promise<{ beings: BeingSummary[]; groups: BeingRef[] }> {
  const [beings, groups] = await Promise.all([
    listBeings(tenantId, query),
    listGroups(tenantId).catch(() => [] as BeingRef[]),
  ]);
  return { beings: beings.items, groups: matchingGroups(groups, query) };
}

// A panel that finds a being - by name search against GET /tenants/{t}/beings
// (ADR 0078: every being in the tenant, PCs/NPCs/bare beings alike), and the
// tenant's groups, which can own things too (ADR 0124) - or by
// pasting an entity id directly (still handy as a quick-entry shortcut even
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

  const combobox = document.createElement('div');
  combobox.className = 'combobox';
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'text-input';
  input.placeholder = 'Search beings…';
  input.autocomplete = 'off';
  input.setAttribute('aria-label', 'Search beings');
  const suggestions = document.createElement('ul');
  suggestions.className = 'combobox-suggestions';
  suggestions.setAttribute('role', 'listbox');
  suggestions.hidden = true;
  combobox.append(input, suggestions);

  const rawIdRow = document.createElement('div');
  rawIdRow.className = 'being-id-row';
  const rawIdInput = document.createElement('input');
  rawIdInput.type = 'text';
  rawIdInput.className = 'text-input';
  rawIdInput.placeholder = "or a being's entity id…";
  rawIdInput.setAttribute('aria-label', "Being's entity id");
  const rawIdButton = document.createElement('button');
  rawIdButton.type = 'button';
  rawIdButton.textContent = 'Use ID';
  rawIdRow.append(rawIdInput, rawIdButton);

  const statusEl = document.createElement('p');
  statusEl.className = 'picker-status';
  statusEl.hidden = true;

  panel.append(combobox, rawIdRow, statusEl);

  let busy = false;
  async function pick(being: BeingRef) {
    if (busy) return;
    busy = true;
    input.disabled = true;
    rawIdButton.disabled = true;
    suggestions.hidden = true;
    try {
      const message = await performAction(being);
      statusEl.hidden = false;
      statusEl.classList.remove('error-text');
      statusEl.textContent = message;
      window.setTimeout(onDone, 1200);
    } catch (e) {
      statusEl.hidden = false;
      statusEl.classList.add('error-text');
      statusEl.textContent = e instanceof Error ? e.message : String(e);
      input.disabled = false;
      rawIdButton.disabled = false;
      busy = false;
    }
  }

  let debounce: ReturnType<typeof setTimeout> | undefined;
  input.addEventListener('input', () => {
    clearTimeout(debounce);
    const query = input.value.trim();
    if (!query) {
      suggestions.hidden = true;
      suggestions.replaceChildren();
      return;
    }
    debounce = setTimeout(async () => {
      try {
        const { beings, groups } = await searchBeingsAndGroups(tenantId, query);
        renderBeingSuggestions(suggestions, beings, (being) => void pick(being), groups);
      } catch {
        suggestions.hidden = true;
      }
    }, 200);
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') onDone();
  });

  rawIdButton.addEventListener('click', () => {
    const id = rawIdInput.value.trim();
    if (!id) return;
    void pick({ entity_id: id, name: id });
  });

  window.setTimeout(() => input.focus(), 0);
  return panel;
}
