// The entry pane and the parents pane: what a person sees and edits of one entry, every change
// going through the command layer (core/bench.ts).

import { parse, render } from '@lorenzo/lorenzoscript';
import type { Bench, EntryStatus } from '../core/bench';
import type { Command } from '../core/commands';
import { canRename, canSetParents, type EditableKind } from '../core/transport';

/** Set while the shell redraws: a field that loses focus then must not commit what was half typed. */
export const redraw = { active: false };

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const button = (label: string, onClick: () => void, cls = 'btn') => {
  const b = el('button', cls, label);
  b.type = 'button';
  b.addEventListener('click', onClick);
  return b;
};

const STATUS_TEXT: Record<EntryStatus, (n: number) => string> = {
  synced: () => 'Synced',
  waiting: (n) => `Waiting to sync (${n})`,
  offline: () => 'Saved on this device',
  conflict: () => 'Conflict',
  attention: () => 'Needs attention',
};

export function statusText(bench: Bench, id: string): string {
  return STATUS_TEXT[bench.status(id)](bench.commandsFor(id).length);
}

export function renderEntry(
  bench: Bench,
  id: string | null,
  go: (id: string) => void,
): HTMLElement {
  const c = el('div', 'pane pane-entry');
  if (bench.loadError && !bench.entries.length) {
    c.append(el('p', 'bad', bench.loadError));
    return c;
  }
  if (!id || !bench.listing().some((e) => e.id === id)) {
    c.append(el('p', 'muted', 'Choose an entry in the explorer.'));
    return c;
  }
  const item = bench.view(id);
  if (!item) {
    c.append(el('p', 'muted', bench.loadError ?? 'Loading…'));
    return c;
  }

  const head = el('div', 'entry-head');
  const name = el('input', 'entry-name');
  name.type = 'text';
  name.value = item.name;
  if (!canRename(item.kinds)) {
    name.disabled = true;
    name.title = 'Only an item can be renamed so far.';
  }
  name.dataset.key = `name:${id}`;
  name.setAttribute('aria-label', 'Name');
  name.addEventListener('change', () => {
    if (redraw.active) return;
    const next = name.value.trim();
    if (next) bench.change('entry.set-name', id, next);
    else name.value = item.name;
  });
  const status = bench.status(id);
  const chip = el('span', `status status-${status}`, statusText(bench, id));
  chip.setAttribute('role', 'status');
  head.append(
    name,
    chip,
    (() => {
      const undo = button('Undo', () => bench.undo(id));
      undo.disabled = !bench.canUndo(id);
      return undo;
    })(),
  );
  c.append(head, el('p', 'kind', kindsText(item.kinds)), kindsEditor(bench, id, item.kinds));

  for (const cmd of bench.commandsFor(id)) {
    if (cmd.state === 'conflict') c.append(conflictRow(bench, cmd));
    else if (cmd.state === 'attention') c.append(attentionRow(bench, cmd));
  }

  c.append(
    el('h2', undefined, 'Parents'),
    parentsEditor(bench, id, item.parentIds, canSetParents(item.kinds), go),
  );

  c.append(
    el('h2', undefined, 'Description'),
    textEditor({
      key: `description:${id}`,
      label: 'Description',
      text: item.description?.text ?? '',
      onChange: (text) => bench.setDescription(id, text),
    }),
  );

  c.append(el('h2', undefined, 'Notes'));
  for (const note of item.notes)
    c.append(
      textEditor({
        key: `note:${note.id}`,
        label: `Note: ${note.title}`,
        text: note.text,
        onChange: (text) => bench.setNoteText(id, note.id, text),
      }),
    );
  c.append(newNote(bench, id));
  return c;
}

const KIND_CHOICES: { kind: EditableKind; label: string; help: string }[] = [
  { kind: 'item', label: 'Item', help: 'Something you can hold, carry or give.' },
  { kind: 'being', label: 'Being', help: 'Someone or something that acts: a person, a creature.' },
];

/** What an entry is: item, being, both or neither (a bare entry, which is what a group is). */
function kindsEditor(bench: Bench, id: string, kinds: readonly string[]): HTMLElement {
  const box = el('fieldset', 'kinds');
  box.append(el('legend', undefined, 'What is this entry?'));
  for (const choice of KIND_CHOICES) {
    const label = el('label', 'kind-choice');
    const input = el('input');
    input.type = 'checkbox';
    input.checked = kinds.includes(choice.kind);
    input.dataset.key = `kind:${id}:${choice.kind}`;
    // An inventory item is of the inventory, not of the catalog.
    if (choice.kind === 'item' && kinds.includes('item_instance')) {
      input.disabled = true;
      input.title = 'An inventory item is not an item of the catalog.';
    }
    input.addEventListener('change', () => {
      if (!redraw.active) bench.setKind(id, choice.kind, input.checked);
    });
    const text = el('span');
    text.append(el('strong', undefined, choice.label), document.createTextNode(` ${choice.help}`));
    label.append(input, text);
    box.append(label);
  }
  return box;
}

/** LorenzoScript as the reader sees it, without links to other entries resolved yet. */
const preview = (text: string): string => render(parse(text), {});

/**
 * A text and its preview. The preview follows what is typed; the change is written down, as a
 * command, when the field loses focus (so a half-typed sentence is never sent).
 */
function textEditor(o: {
  key: string;
  label: string;
  text: string;
  onChange: (text: string) => void;
}): HTMLElement {
  const wrap = el('div', 'text-editor');
  const area = el('textarea', 'text-edit');
  area.value = o.text;
  area.rows = 4;
  area.dataset.key = o.key;
  area.setAttribute('aria-label', o.label);
  const shown = el('div', 'ls-content text-preview');
  shown.setAttribute('aria-label', `${o.label}, as it reads`);
  shown.innerHTML = preview(o.text);
  area.addEventListener('input', () => {
    shown.innerHTML = preview(area.value);
  });
  area.addEventListener('change', () => {
    if (redraw.active) return;
    o.onChange(area.value);
  });
  wrap.append(area, shown);
  return wrap;
}

function newNote(bench: Bench, entryId: string): HTMLElement {
  const form = el('form', 'new-note');
  const area = el('textarea', 'text-edit');
  area.rows = 2;
  area.placeholder = 'A new note';
  area.dataset.key = `new-note:${entryId}`;
  area.setAttribute('aria-label', 'A new note');
  const add = el('button', 'btn', 'Add note');
  add.type = 'submit';
  form.append(area, add);
  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    if (bench.addNote(entryId, area.value)) area.value = '';
  });
  return form;
}

/** What an entry is, in words: its kinds, or a bare entry. */
export const kindsText = (kinds: readonly string[]): string =>
  kinds.length ? kinds.map((k) => k.replace('_', ' ')).join(' and ') : 'bare entry';

const show = (v: unknown, bench: Bench): string => {
  if (Array.isArray(v)) return v.map((p) => bench.displayName(p)).join(', ') || 'none';
  if (v === null) return 'nothing of its own (inherited)';
  if (typeof v === 'boolean') return v ? 'on' : 'off';
  return typeof v === 'string' ? `“${v}”` : String(v);
};

function conflictRow(bench: Bench, cmd: Command): HTMLElement {
  const label =
    cmd.stat?.name ??
    (cmd.kind ? `${cmd.kind} kind` : cmd.type === 'entry.set-name' ? 'name' : 'parents');
  const box = el('div', 'problem problem-conflict');
  box.setAttribute('role', 'alert');
  box.append(
    el('strong', undefined, 'Conflict. '),
    document.createTextNode(
      `The ${label} was changed elsewhere to ${show(cmd.theirs, bench)}. Yours: ${show(cmd.mine, bench)}.`,
    ),
  );
  const actions = el('span', 'actions');
  actions.append(
    button('Keep mine', () => bench.keepMine(cmd.id)),
    button('Use theirs', () => bench.discard(cmd.id)),
  );
  box.append(actions);
  return box;
}

function attentionRow(bench: Bench, cmd: Command): HTMLElement {
  const box = el('div', 'problem problem-attention');
  box.setAttribute('role', 'alert');
  box.append(
    el('strong', undefined, 'Needs attention. '),
    document.createTextNode(cmd.error ?? 'The server refused this change.'),
  );
  const actions = el('span', 'actions');
  actions.append(
    button('Try again', () => bench.retry(cmd.id)),
    button('Discard', () => bench.discard(cmd.id)),
  );
  box.append(actions);
  return box;
}

function parentsEditor(
  bench: Bench,
  id: string,
  parentIds: string[],
  editable: boolean,
  go: (id: string) => void,
): HTMLElement {
  const wrap = el('div', 'parents');
  const list = el('ul', 'list');
  if (!parentIds.length) list.append(el('li', 'muted', 'No parents.'));
  for (const p of parentIds) {
    const li = el('li', 'parent');
    const open = el('button', 'row', bench.displayName(p));
    open.type = 'button';
    open.addEventListener('click', () => go(p));
    const remove = el('button', 'x', '×');
    remove.type = 'button';
    remove.title = `Remove parent ${bench.displayName(p)}`;
    remove.setAttribute('aria-label', `Remove parent ${bench.displayName(p)}`);
    remove.addEventListener('click', () =>
      bench.change(
        'entry.set-parents',
        id,
        parentIds.filter((x) => x !== p),
      ),
    );
    li.append(open, remove);
    list.append(li);
  }
  if (!editable) {
    wrap.append(list, el('p', 'muted', 'An inventory item changes its parent in its own way.'));
    return wrap;
  }
  const add = el('select', 'add-parent');
  add.setAttribute('aria-label', 'Add a parent');
  add.append(new Option('Add a parent…', ''));
  for (const e of bench.listing())
    if (e.id !== id && !parentIds.includes(e.id)) add.append(new Option(e.name, e.id));
  add.addEventListener('change', () => {
    if (add.value) bench.change('entry.set-parents', id, [...parentIds, add.value]);
  });
  wrap.append(list, add);
  return wrap;
}

/** The "Parents and children" pane: where this entry comes from, and what comes from it. */
export function renderLinks(
  bench: Bench,
  id: string | null,
  go: (id: string) => void,
): HTMLElement {
  const c = el('div', 'pane pane-links');
  const item = id ? bench.view(id) : null;
  const list = (ids: string[]) => {
    const ul = el('ul', 'list');
    if (!ids.length) ul.append(el('li', 'muted', 'none'));
    for (const other of ids) {
      const li = el('li');
      const b = el('button', 'row', bench.displayName(other));
      b.type = 'button';
      b.addEventListener('click', () => go(other));
      li.append(b);
      ul.append(li);
    }
    return ul;
  };
  c.append(
    el('h2', undefined, 'Parents'),
    list(item?.parentIds ?? []),
    el('h2', undefined, 'Children'),
    list(id ? bench.childrenOf(id) : []),
  );
  return c;
}
