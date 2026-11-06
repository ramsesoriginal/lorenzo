import { el, message } from './dom';
import { type EntryChoice, type EntryKind, findEnds, findEntries, findTypes } from './social-api';

export interface Picker {
  label: HTMLElement;
  /** The id of the chosen entry, or null. */
  value(): string | null;
  /** The name of the chosen entry, or ''. */
  name(): string;
}

/**
 * A control that finds an entry by name: a search box, and what it found as a list to choose
 * from. The label's words are the control's name; the choice is told in words under it.
 */
export function entryPicker(
  tenant: string,
  title: string,
  options: {
    exclude?: () => string | null;
    kind?: EntryKind;
    find?: (tenant: string, query: string) => Promise<EntryChoice[]>;
    nothing?: string;
  } = {},
): Picker {
  const label = el('div', '', 'field');
  const input = el('input', '', 'text-input');
  input.type = 'search';
  input.autocomplete = 'off';
  input.setAttribute('aria-label', `${title}: search by name`);
  const results = el('select', '', 'text-input');
  results.setAttribute('aria-label', `${title}: results`);
  results.hidden = true;
  const chosen = el('p', 'Nothing chosen yet.', 'status-text');
  chosen.setAttribute('role', 'status');
  let found: EntryChoice[] = [];
  let picked: EntryChoice | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let latest = 0;

  const choose = (entry: EntryChoice | null) => {
    picked = entry;
    chosen.textContent = entry ? `Chosen: ${entry.name}` : 'Nothing chosen yet.';
  };
  const search = async () => {
    const mine = ++latest;
    const text = input.value.trim();
    if (!text) {
      results.hidden = true;
      return;
    }
    try {
      const rows = (
        await (options.find ?? ((t, q) => findEntries(t, q, options.kind)))(tenant, text)
      ).filter((row) => row.id !== options.exclude?.() && !row.kinds.includes('relationship'));
      if (mine !== latest) return;
      found = rows;
      results.replaceChildren(
        ...rows.map((row) => {
          const option = el('option', row.name);
          option.value = row.id;
          return option;
        }),
      );
      results.hidden = rows.length === 0;
      results.size = Math.min(6, Math.max(2, rows.length));
      if (rows.length === 0) chosen.textContent = options.nothing ?? 'Nothing found by that name.';
    } catch (error) {
      chosen.textContent = message(error);
    }
  };
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => void search(), 200);
  });
  results.addEventListener('change', () => {
    choose(found.find((row) => row.id === results.value) ?? null);
  });
  label.append(el('span', title, 'field-label'), input, results, chosen);
  return {
    label,
    value: () => picked?.id ?? null,
    name: () => picked?.name ?? '',
  };
}

/** A being or a group, the ends a relationship is made between. */
export function endPicker(tenant: string, title: string, exclude?: () => string | null): Picker {
  return entryPicker(tenant, title, {
    find: findEnds,
    nothing: 'No being or group by that name.',
    ...(exclude ? { exclude } : {}),
  });
}

/** One of the types of relationship the library has. */
export function typePicker(tenant: string, title: string): Picker {
  return entryPicker(tenant, title, {
    find: findTypes,
    nothing: 'No type of relationship by that name.',
  });
}
