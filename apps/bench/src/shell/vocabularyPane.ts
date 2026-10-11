// The Vocabulary pane: the stats the repository defines, and making and deleting them (ADR 0253).
// A stat cannot be renamed (the API has no way to, K6), so a name is chosen with care.

import type { Bench } from '../core/bench';
import type { StatGroup, StatType } from '../core/transport';

export interface VocabularyUi {
  groups: StatGroup[] | null;
  note: string | null;
  /** The stat whose deletion is being confirmed. */
  confirming: string | null;
}
export const newVocabularyUi = (): VocabularyUi => ({ groups: null, note: null, confirming: null });

const TYPES: [StatType, string][] = [
  ['int', 'Whole number'],
  ['float', 'Decimal number'],
  ['text', 'Text'],
  ['bool', 'Tag (yes or no)'],
  ['enum', 'One of a list'],
];
const NEW_GROUP = '__new';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

export function renderVocabulary(bench: Bench, ui: VocabularyUi, redraw: () => void): HTMLElement {
  const c = el('div', 'pane pane-vocabulary');
  if (!ui.groups) {
    bench.transport
      .listStatGroups()
      .then((g) => {
        ui.groups = g;
      })
      .catch((e) => {
        ui.groups = [];
        ui.note = e instanceof Error ? e.message : 'Could not read the stat groups.';
      })
      .finally(redraw);
    c.append(el('p', 'muted', 'Reading the stats…'));
    return c;
  }
  const fail = (e: unknown, fallback: string) => {
    ui.note = e instanceof Error ? e.message : fallback;
    redraw();
  };
  if (ui.note) c.append(el('p', 'formula-note', ui.note));

  const list = el('ul', 'vocabulary');
  for (const d of [...bench.statDefs].sort((a, b) => a.name.localeCompare(b.name))) {
    const li = el('li', 'vocab-stat');
    li.dataset.stat = d.id;
    const type = TYPES.find(([t]) => t === d.type)?.[1] ?? d.type;
    li.append(el('span', 'stat-name', d.name), el('span', 'muted', type));
    if (d.type === 'enum') li.append(el('span', 'muted', d.enumValues.join(' · ')));
    const del = el('button', 'x', ui.confirming === d.id ? 'Delete it' : '×');
    del.type = 'button';
    del.setAttribute('aria-label', `Delete ${d.name}`);
    del.addEventListener('click', async () => {
      if (ui.confirming !== d.id) {
        ui.confirming = d.id;
        ui.note = `Delete ${d.name} from the repository? Every entry loses its value. Press again to delete.`;
        return redraw();
      }
      try {
        const readers = await bench.transport.formulaDependents(d.id);
        if (readers.length) {
          ui.note = `${d.name} is read by ${readers.length} ${readers.length === 1 ? 'formula' : 'formulas'}; take those away first.`;
        } else {
          await bench.transport.deleteStat(d.id);
          await bench.reloadStatDefinitions();
          ui.note = `Deleted ${d.name}.`;
        }
        ui.confirming = null;
        redraw();
      } catch (e) {
        ui.confirming = null;
        fail(e, `Could not delete ${d.name}.`);
      }
    });
    li.append(del);
    list.append(li);
  }
  if (!bench.statDefs.length) list.append(el('li', 'muted', 'No stats yet.'));
  c.append(list);

  const form = el('form', 'new-stat');
  form.setAttribute('aria-label', 'New stat');
  const name = el('input');
  name.type = 'text';
  name.placeholder = 'Name of the new stat';
  name.setAttribute('aria-label', 'Name of the new stat');
  const type = el('select');
  type.setAttribute('aria-label', 'Kind of value');
  for (const [value, text] of TYPES) type.append(new Option(text, value));
  const values = el('input');
  values.type = 'text';
  values.placeholder = 'Values, separated by commas';
  values.setAttribute('aria-label', 'Values');
  values.hidden = true;
  type.addEventListener('change', () => {
    values.hidden = type.value !== 'enum';
  });
  const group = el('select');
  group.setAttribute('aria-label', 'Group');
  for (const g of ui.groups) group.append(new Option(g.name, g.id));
  group.append(new Option('A new group…', NEW_GROUP));
  const groupName = el('input');
  groupName.type = 'text';
  groupName.placeholder = 'Name of the new group';
  groupName.setAttribute('aria-label', 'Name of the new group');
  groupName.hidden = true;
  const syncGroup = () => {
    groupName.hidden = group.value !== NEW_GROUP;
  };
  group.addEventListener('change', syncGroup);
  if (!ui.groups.length) {
    group.value = NEW_GROUP;
    syncGroup();
  }
  const submit = el('button', 'btn primary', 'Make the stat');
  submit.type = 'submit';
  form.append(name, type, values, group, groupName, submit);
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const label = name.value.trim();
    if (!label) return;
    try {
      let groupId = group.value;
      if (groupId === NEW_GROUP) {
        const made = await bench.transport.createStatGroup(groupName.value.trim() || 'General');
        ui.groups = [...(ui.groups ?? []), made];
        groupId = made.id;
      }
      const enumValues =
        type.value === 'enum'
          ? values.value
              .split(',')
              .map((v) => v.trim())
              .filter(Boolean)
          : [];
      if (type.value === 'enum' && !enumValues.length) {
        ui.note = 'Give the values to choose from, separated by commas.';
        return redraw();
      }
      await bench.transport.createStat({
        name: label,
        groupId,
        type: type.value as StatType,
        enumValues,
      });
      await bench.reloadStatDefinitions();
      ui.note = `Made the stat ${label}. A stat cannot be renamed afterwards.`;
      redraw();
    } catch (e) {
      fail(e, 'Could not make the stat.');
    }
  });
  c.append(form);
  return c;
}
