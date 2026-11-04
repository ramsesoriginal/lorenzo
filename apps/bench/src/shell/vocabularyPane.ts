// The Vocabulary pane: the stats the repository defines, and making, renaming and deleting them
// (ADR 0253, ADR 0390). A stat or one of its values is renamed in place; its kind of value is not.

import type { Bench } from '../core/bench';
import type { StatDef, StatGroup, StatType } from '../core/transport';
import { librariesLine } from './entryPane';
import { icon } from './icons';

export interface VocabularyUi {
  groups: StatGroup[] | null;
  note: string | null;
  /** The stat whose deletion is being confirmed. */
  confirming: string | null;
  /** The stat, or one value of it, being renamed. */
  editing: { statId: string; valueId: string | null } | null;
}
export const newVocabularyUi = (): VocabularyUi => ({
  groups: null,
  note: null,
  confirming: null,
  editing: null,
});

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
  /** A line to type the new name in: Enter renames, Escape leaves it as it was. */
  const renamer = (initial: string, label: string, save: (value: string) => Promise<void>) => {
    const form = el('form', 'vocab-rename');
    const input = el('input');
    input.type = 'text';
    input.value = initial;
    input.dataset.key = 'vocab-rename';
    input.setAttribute('aria-label', label);
    const ok = el('button', 'btn primary', 'Rename');
    ok.type = 'submit';
    const cancel = el('button', 'btn', 'Cancel');
    cancel.type = 'button';
    const leave = () => {
      ui.editing = null;
      redraw();
    };
    cancel.addEventListener('click', leave);
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') leave();
    });
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const value = input.value.trim();
      if (!value || value === initial) return leave();
      try {
        await save(value);
        ui.editing = null;
        ui.note = `Renamed ${initial} to ${value}.`;
        redraw();
      } catch (e) {
        fail(e, `Could not rename ${initial}.`);
      }
    });
    form.append(input, ok, cancel);
    queueMicrotask(() => {
      input.focus();
      input.select();
    });
    return form;
  };
  /** The allowed values of an enum stat, each one renamed in place. */
  const valueList = (d: StatDef, editing: VocabularyUi['editing']) => {
    const span = el('span', 'muted vocab-values');
    for (const [i, value] of d.enumValues.entries()) {
      const id = d.enumIds?.[i];
      if (i) span.append(document.createTextNode(' · '));
      if (id && editing?.valueId === id) {
        span.append(
          renamer(value, `New name of ${value}`, (next) => bench.renameEnumValue(d.id, id, next)),
        );
        continue;
      }
      if (!id) {
        span.append(document.createTextNode(value));
        continue;
      }
      const button = el('button', 'vocab-value', value);
      button.type = 'button';
      button.title = `Rename ${value}`;
      button.setAttribute('aria-label', `Rename the value ${value}`);
      button.addEventListener('click', () => {
        ui.editing = { statId: d.id, valueId: id };
        ui.confirming = null;
        redraw();
      });
      span.append(button);
    }
    return span;
  };
  if (ui.note) c.append(el('p', 'formula-note', ui.note));

  const list = el('ul', 'vocabulary');
  for (const d of [...bench.statDefs].sort((a, b) => a.name.localeCompare(b.name))) {
    const li = el('li', 'vocab-stat');
    li.dataset.stat = d.id;
    const type = TYPES.find(([t]) => t === d.type)?.[1] ?? d.type;
    const editing = ui.editing?.statId === d.id ? ui.editing : null;
    if (editing && !editing.valueId) {
      li.append(renamer(d.name, `New name of ${d.name}`, (name) => bench.renameStat(d.id, name)));
    } else {
      li.append(el('span', 'stat-name', d.name));
      const rename = el('button', 'x');
      rename.append(icon('edit', 12));
      rename.type = 'button';
      rename.setAttribute('aria-label', `Rename ${d.name}`);
      rename.addEventListener('click', () => {
        ui.editing = { statId: d.id, valueId: null };
        ui.confirming = null;
        redraw();
      });
      li.append(rename);
    }
    li.append(el('span', 'muted', type));
    if (d.type === 'enum') li.append(valueList(d, editing));
    const del = el('button', 'x', ui.confirming === d.id ? 'Delete it' : undefined);
    if (ui.confirming !== d.id) del.append(icon('close', 12));
    del.type = 'button';
    del.setAttribute('aria-label', `Delete ${d.name}`);
    del.addEventListener('click', async () => {
      if (ui.confirming !== d.id) {
        ui.confirming = d.id;
        const held = await bench.transport
          .countLibraries('stat', d.id)
          .catch(() => 'unknown' as const);
        ui.note = `Delete ${d.name} from the repository? Every entry loses its value. ${librariesLine(held)} Press again to delete.`;
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
  name.dataset.key = 'vocab-name';
  name.setAttribute('aria-label', 'Name of the new stat');
  const type = el('select');
  type.setAttribute('aria-label', 'Kind of value');
  for (const [value, text] of TYPES) type.append(new Option(text, value));
  const values = el('input');
  values.type = 'text';
  values.placeholder = 'Values, separated by commas';
  values.dataset.key = 'vocab-values';
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
  groupName.dataset.key = 'vocab-group';
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
      ui.note = `Made the stat ${label}.`;
      redraw();
    } catch (e) {
      fail(e, 'Could not make the stat.');
    }
  });
  c.append(form);
  return c;
}
