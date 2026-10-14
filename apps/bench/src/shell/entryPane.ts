// The entry pane and the parents pane: what a person sees and edits of one entry, every change
// going through the command layer (core/bench.ts).

import { slugify } from '@lorenzo/lorenzoscript';
import type { Bench, EntryStatus } from '../core/bench';
import type { Command } from '../core/commands';
import { canRename, canSetParents, type EditableKind, slugProblem } from '../core/transport';

import { ancestorPath } from './ancestors';
import { attachEntryPicker } from './entryPicker';
import { openLink } from './entryPickerText';
import { icon, iconButton, kindIcon, statusIcon } from './icons';
import { liveEditor } from './liveEditor';

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

/** The icon of an entry in the list: its kinds', or a bare entry's while it is not known yet. */
function kindIconOf(bench: Bench, id: string) {
  return kindIcon(bench.listing().find((e) => e.id === id)?.kinds ?? []);
}

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

  const trail = ancestorPath(bench.listing(), id);
  if (trail.length) {
    const nav = el('nav', 'breadcrumb');
    nav.setAttribute('aria-label', 'Inherits from');
    for (const a of trail) {
      const b = button(a.name, () => go(a.id), 'crumb');
      nav.append(b, el('span', 'crumb-sep', '/'));
    }
    c.append(nav);
  }

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
  c.append(name);

  // What it is, its link name, and how its changes are doing: one quiet line.
  const meta = el('div', 'meta');
  const kinds = kindsEditor(bench, id, item.kinds);
  meta.append(kinds, linkNameField(bench, id, item.name, item.slug));
  const status = bench.status(id);
  const chip = el('span', `status status-${status}`);
  chip.append(icon(statusIcon(status), 13), document.createTextNode(statusText(bench, id)));
  chip.setAttribute('role', 'status');
  const undo = el('button', 'btn quiet');
  undo.type = 'button';
  undo.append(icon('undo', 14), document.createTextNode(' Undo'));
  undo.addEventListener('click', () => bench.undo(id));
  undo.disabled = !bench.canUndo(id);
  meta.append(el('span', 'grow'), chip, undo);
  c.append(meta, el('p', 'kind sr-only', kindsText(item.kinds)));

  for (const cmd of bench.commandsFor(id)) {
    if (cmd.state === 'conflict') c.append(conflictRow(bench, cmd));
    else if (cmd.state === 'attention') c.append(attentionRow(bench, cmd));
  }

  // The description, with the picture beside it.
  const main = el('div', 'entry-main');
  main.append(
    textEditor(bench, go, {
      key: `description:${id}`,
      home: id,
      label: 'Description',
      placeholder: 'Write a description…',
      text: item.description?.text ?? '',
      onChange: (text) => bench.setDescription(id, text),
    }),
    pictureSection(bench, id),
  );
  c.append(main);

  // What is around the text: where it inherits from and its notes. In Write, which is for writing,
  // this steps back (bench.css).
  const extra = el('div', 'entry-extra');
  extra.append(
    el('h2', 'section', 'Inherits from'),
    parentsEditor(bench, id, item.parentIds, canSetParents(item.kinds), go),
  );

  extra.append(el('h2', 'section', 'Notes'));
  item.notes.forEach((note, i) => {
    const row = el('div', 'note-row');
    const editor = textEditor(bench, go, {
      key: `note:${note.id}`,
      home: id,
      label: `Note: ${note.title}`,
      text: note.text,
      onChange: (text) => bench.setNoteText(id, note.id, text),
    });
    const order = el('div', 'note-order');
    for (const [label, by, disabled] of [
      ['Move note up', -1, i === 0],
      ['Move note down', 1, i === item.notes.length - 1],
    ] as const) {
      const b = iconButton(
        by < 0 ? 'up' : 'down',
        `${label}: ${note.title}`,
        () => bench.moveNote(id, note.id, by),
        'btn',
        14,
      );
      b.disabled = disabled;
      b.dataset.key = `note-${by < 0 ? 'up' : 'down'}:${note.id}`;
      order.append(b);
    }
    row.append(order, editor, noteAudience(bench, id, note));
    extra.append(row);
  });
  extra.append(newNote(bench, id));
  c.append(extra);
  return c;
}

/** What a note says of who reads it, and where it is Everyone's, the one click that takes it back. */
export const EVERYONE_NOTE = 'Visible to libraries that copy this';

/**
 * Under a note: GM only, or, for a note that is Everyone's, a lock and "Make GM only". Everyone's
 * text goes with every copy of the repository and is what a person may read before copying it
 * (RFC 0038 section 5), so it is shown where it is written. Making a note GM only is a change like
 * any other: written down, sent, and undone with Undo.
 */
function noteAudience(
  bench: Bench,
  entryId: string,
  note: { id: string; title: string; isPublic: boolean },
): HTMLElement {
  if (!note.isPublic) {
    const quiet = el('div', 'note-audience note-gm');
    quiet.dataset.key = `note-gm:${note.id}`;
    quiet.append(el('span', undefined, 'GM only'));
    return quiet;
  }
  const box = el('div', 'note-audience note-lock');
  box.dataset.key = `note-lock:${note.id}`;
  const label = el('span', 'note-lock-label');
  label.append(icon('private', 14), el('span', undefined, EVERYONE_NOTE));
  const make = button('Make GM only', () => bench.makeNoteGmOnly(entryId, note.id), 'btn quiet');
  make.setAttribute('aria-label', `Make GM only: ${note.title}`);
  make.dataset.key = `note-make-gm:${note.id}`;
  box.append(label, make);
  return box;
}

/** The link name: what `[[Name]]` and `[text](slug)` in a text call the entry by. */
function linkNameField(bench: Bench, id: string, name: string, slug: string | null): HTMLElement {
  const box = el('div', 'link-name');
  const label = el('label', 'link-label');
  label.append(el('span', undefined, 'Link name'));
  const input = el('input', 'mono');
  input.type = 'text';
  input.value = slug ?? '';
  input.placeholder = 'none';
  input.size = Math.max(6, (slug ?? '').length + 1);
  input.spellcheck = false;
  input.dataset.key = `slug:${id}`;
  label.append(input);
  const problem = el('p', 'bad');
  problem.hidden = true;
  input.addEventListener('change', () => {
    if (redraw.active) return;
    const text = input.value.trim();
    if (text === (slug ?? '')) return;
    const bad = text ? slugProblem(text) : null;
    problem.hidden = !bad;
    problem.textContent = bad ?? '';
    if (!bad) bench.setSlug(id, text || null);
  });
  box.append(label, problem);
  // An entry without one can be given the one its name makes, as a link to its name would use.
  const suggested = slugify(name);
  if (!slug && suggested && !slugProblem(suggested)) {
    const use = button(`Use “${suggested}”`, () => bench.setSlug(id, suggested));
    use.className = 'btn';
    box.append(use);
  }
  return box;
}

const KIND_CHOICES: { kind: EditableKind; label: string; help: string }[] = [
  { kind: 'item', label: 'Item', help: 'Something you can hold, carry or give.' },
  { kind: 'being', label: 'Being', help: 'Someone or something that acts: a person, a creature.' },
];

/** What an entry is: item, being, both or neither (a bare entry, which is what a group is). */
function kindsEditor(bench: Bench, id: string, kinds: readonly string[]): HTMLElement {
  const box = el('div', 'kinds');
  box.setAttribute('role', 'group');
  box.setAttribute('aria-label', 'What is this entry?');
  for (const choice of KIND_CHOICES) {
    const label = el('label', 'chip kind-choice');
    label.title = choice.help;
    const input = el('input', 'sr-only');
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
    label.append(input, icon(kindIcon([choice.kind]), 14), el('span', undefined, choice.label));
    box.append(label);
  }
  return box;
}

/**
 * A text and its preview. The preview follows what is typed, with the entry links it names shown
 * as links (looked up as they appear); the change is written down, as a command, when the field
 * loses focus (so a half-typed sentence is never sent).
 */
/** The entry's main picture, with a way to choose another and to take it away. Online only. */
export function pictureSection(bench: Bench, id: string): HTMLElement {
  const box = el('div', 'picture');
  const pictures = bench.pictures;
  if (!bench.onServer(id)) {
    box.append(el('p', 'muted', 'A picture can be added once this entry has been sent.'));
    return box;
  }
  const url = pictures.get(id);
  if (url === undefined) void pictures.load(id);
  const busy = pictures.busy(id);
  if (url) {
    const img = el('img', 'picture-img');
    img.src = url;
    img.alt = 'Main picture';
    box.append(img);
  } else {
    box.append(el('p', 'muted', url === null ? 'No picture.' : 'Loading the picture…'));
  }
  const file = el('input');
  file.type = 'file';
  file.accept = 'image/png,image/jpeg,image/webp,image/gif';
  file.hidden = true;
  file.setAttribute('aria-label', 'Picture file');
  file.addEventListener('change', () => {
    const chosen = file.files?.[0];
    if (chosen) void pictures.set(id, chosen);
  });
  const choose = button(url ? 'Replace picture…' : 'Choose picture…', () => file.click(), 'lnk');
  choose.disabled = busy;
  const remove = button('Remove picture', () => void pictures.clear(id), 'lnk');
  remove.hidden = !url;
  remove.disabled = busy;
  const actions = el('div', 'picture-actions');
  actions.append(choose, remove, file);
  if (busy) actions.append(el('span', 'muted', 'Saving…'));
  box.append(actions);
  const problem = pictures.problem(id);
  if (problem) {
    const p = el('p', 'bad', problem);
    p.setAttribute('role', 'alert');
    box.append(p);
  }
  return box;
}

function textEditor(
  bench: Bench,
  go: (id: string) => void,
  o: {
    key: string;
    /** The entry the text belongs to: what `my/` links are held by. */
    home: string;
    label: string;
    text: string;
    placeholder?: string;
    onChange: (text: string) => void;
  },
): HTMLElement {
  return liveEditor({ bench, go, ...o });
}

/** Buttons that start a link or a picture at the caret, for whoever does not know to type `[[`. */
function linkToolbar(area: HTMLTextAreaElement): HTMLElement {
  const bar = el('div', 'text-toolbar');
  bar.setAttribute('role', 'toolbar');
  bar.setAttribute('aria-label', 'Insert');
  for (const [label, image] of [
    ['Link to an entry', false],
    ['Show a picture', true],
  ] as const) {
    const b = button(label, () => {
      const made = openLink(area.value, area.selectionStart, area.selectionEnd, image);
      area.value = made.text;
      area.focus();
      area.setSelectionRange(made.caret, made.caret);
      // The picker and the preview follow what is typed.
      area.dispatchEvent(new Event('input'));
    });
    // Pressing must not take the focus from the text, or the caret and selection are lost.
    b.addEventListener('mousedown', (ev) => ev.preventDefault());
    bar.append(b);
  }
  return bar;
}

function newNote(bench: Bench, entryId: string): HTMLElement {
  const form = el('form', 'new-note');
  const area = el('textarea', 'text-edit');
  area.rows = 2;
  area.placeholder = 'A new note';
  attachEntryPicker(area, bench);
  area.dataset.key = `new-note:${entryId}`;
  area.setAttribute('aria-label', 'A new note');
  const add = el('button', 'btn', 'Add note');
  add.type = 'submit';
  form.append(linkToolbar(area), area, add);
  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    if (bench.addNote(entryId, area.value)) area.value = '';
  });
  return form;
}

/** What an entry is, in words: its kinds, or a bare entry. */
export const kindsText = (kinds: readonly string[]): string =>
  kinds.length ? kinds.map((k) => k.replace('_', ' ')).join(' and ') : 'bare entry';

export const showValue = (v: unknown, bench: Bench, cmd?: Command): string => {
  if (cmd?.type === 'notes.set-order') return 'another order';
  if (cmd?.type === 'note.set-public') return v === true ? 'Everyone' : 'GM only';
  if (cmd?.type === 'entry.set-slug' && v === null) return 'no link name';
  if (Array.isArray(v)) return v.map((p) => bench.displayName(p)).join(', ') || 'none';
  if (v === null) return 'nothing of its own (inherited)';
  if (typeof v === 'boolean') return v ? 'on' : 'off';
  return typeof v === 'string' ? `“${v}”` : String(v);
};

/** What a command changes, in a person's words: "name", "Weight", "link name". */
export function fieldLabel(cmd: Command): string {
  return (
    cmd.stat?.name ??
    (cmd.type === 'entry.set-slug' ? 'link name' : undefined) ??
    (cmd.type === 'notes.set-order' ? 'order of the notes' : undefined) ??
    (cmd.type === 'note.set-public' ? 'audience of the note' : undefined) ??
    (cmd.kind ? `${cmd.kind} kind` : cmd.type === 'entry.set-name' ? 'name' : 'parents')
  );
}

function conflictRow(bench: Bench, cmd: Command): HTMLElement {
  const label = fieldLabel(cmd);
  const box = el('div', 'problem problem-conflict');
  box.setAttribute('role', 'alert');
  box.append(
    el('strong', undefined, 'Conflict. '),
    document.createTextNode(
      `The ${label} was changed elsewhere to ${showValue(cmd.theirs, bench, cmd)}. Yours: ${showValue(cmd.mine, bench, cmd)}.`,
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
  const list = el('ul', 'list chips');
  if (!parentIds.length) list.append(el('li', 'muted', 'No parents.'));
  for (const p of parentIds) {
    const li = el('li', 'parent');
    const open = el('button', 'row');
    open.append(icon(kindIconOf(bench, p), 14), document.createTextNode(bench.displayName(p)));
    open.type = 'button';
    open.addEventListener('click', () => go(p));
    const remove = el('button', 'x');
    remove.append(icon('close', 12));
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

/** The Links pane: where this entry comes from, what comes from it, and the links in its texts. */
export function renderLinks(
  bench: Bench,
  id: string | null,
  go: (id: string) => void,
): HTMLElement {
  const c = el('div', 'pane pane-links');
  const item = id ? bench.view(id) : null;
  const row = (target: string, name: string, note?: string) => {
    const li = el('li');
    const b = el('button', 'row');
    b.append(icon(kindIconOf(bench, target), 14), el('span', 'nm', name));
    if (note) b.append(el('span', 'where muted', note));
    b.type = 'button';
    b.addEventListener('click', () => go(target));
    li.append(b);
    return li;
  };
  const section = (title: string, rows: HTMLElement[], empty = 'none') => {
    const ul = el('ul', 'list');
    if (!rows.length) ul.append(el('li', 'muted', empty));
    ul.append(...rows);
    c.append(el('h2', undefined, title), ul);
  };
  section(
    'Parents',
    (item?.parentIds ?? []).map((p) => row(p, bench.displayName(p))),
  );
  section(
    'Children',
    (id ? bench.childrenOf(id) : []).map((k) => row(k, bench.displayName(k))),
  );
  const connections = id ? bench.connections(id) : null;
  const waiting = !!id && !connections && bench.onServer(id);
  section(
    'Links to',
    (connections?.outgoing ?? []).map((o) => row(o.entry.id, o.entry.name, o.where)),
    waiting ? 'Reading…' : 'Nothing in its texts links to another entry.',
  );
  section(
    'Linked from',
    (connections?.incoming ?? []).map((i) =>
      row(i.entryId, i.name, i.type === 'description' ? 'Description' : `Note: ${i.title}`),
    ),
    waiting ? 'Reading…' : 'No text on another entry links here.',
  );
  return c;
}
