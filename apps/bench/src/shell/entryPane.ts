// The entry pane and the parents pane: what a person sees and edits of one entry, every change
// going through the command layer (core/bench.ts).

import { slugify } from '@lorenzo/lorenzoscript';
import type { Bench, EntryStatus } from '../core/bench';
import type { Command } from '../core/commands';
import { entryIdOfHref, type Rendered } from '../core/links';
import { canRename, canSetParents, type EditableKind, slugProblem } from '../core/transport';

import { ancestorPath } from './ancestors';
import { attachEntryPicker } from './entryPicker';
import { openLink } from './entryPickerText';
import { attachLinkPreviews, excerptOf, hideCard } from './linkPreview';

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
  c.append(
    head,
    el('p', 'kind', kindsText(item.kinds)),
    kindsEditor(bench, id, item.kinds),
    linkNameField(bench, id, item.name, item.slug),
    pictureSection(bench, id),
  );

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
    textEditor(bench, go, {
      key: `description:${id}`,
      home: id,
      label: 'Description',
      text: item.description?.text ?? '',
      onChange: (text) => bench.setDescription(id, text),
    }),
  );

  c.append(el('h2', undefined, 'Notes'));
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
      const b = button(by < 0 ? '↑' : '↓', () => bench.moveNote(id, note.id, by));
      b.title = label;
      b.setAttribute('aria-label', `${label}: ${note.title}`);
      b.disabled = disabled;
      b.dataset.key = `note-${by < 0 ? 'up' : 'down'}:${note.id}`;
      order.append(b);
    }
    row.append(order, editor);
    c.append(row);
  });
  c.append(newNote(bench, id));
  return c;
}

/** The link name: what `[[Name]]` and `[text](slug)` in a text call the entry by. */
function linkNameField(bench: Bench, id: string, name: string, slug: string | null): HTMLElement {
  const box = el('div', 'link-name');
  const label = el('label', undefined, 'Link name');
  const input = el('input');
  input.type = 'text';
  input.value = slug ?? '';
  input.placeholder = 'none: no text can link to this entry';
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

/**
 * A text and its preview. The preview follows what is typed, with the entry links it names shown
 * as links (looked up as they appear); the change is written down, as a command, when the field
 * loses focus (so a half-typed sentence is never sent).
 */
/** The entry's main picture, with a way to choose another and to take it away. Online only. */
function pictureSection(bench: Bench, id: string): HTMLElement {
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
  const choose = button(url ? 'Replace picture…' : 'Choose picture…', () => file.click());
  choose.disabled = busy;
  const remove = button('Remove picture', () => void pictures.clear(id));
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

const quoted = (slugs: string[]): string => slugs.map((s) => `“${s}”`).join(', ');

function textEditor(
  bench: Bench,
  go: (id: string) => void,
  o: {
    key: string;
    /** The entry the text belongs to: what `my/` links are held by. */
    home: string;
    label: string;
    text: string;
    onChange: (text: string) => void;
  },
): HTMLElement {
  const wrap = el('div', 'text-editor');
  const area = el('textarea', 'text-edit');
  area.value = o.text;
  area.rows = 4;
  area.dataset.key = o.key;
  area.setAttribute('aria-label', o.label);
  const shown = el('div', 'ls-content text-preview');
  shown.setAttribute('aria-label', `${o.label}, as it reads`);
  const notes = el('p', 'muted link-notes');
  notes.hidden = true;

  const draw = (r: Rendered) => {
    shown.innerHTML = r.html; // escaped by the renderer (ADR 0100)
    // A link keeps the focus when the page is drawn again.
    shown.querySelectorAll<HTMLElement>('a.ls-entity').forEach((a, i) => {
      a.dataset.key = `${o.key}:link:${i}`;
    });
    const said: string[] = [];
    if (r.missing.length)
      said.push(
        `Nothing is called ${quoted(r.missing)} yet, so ${r.missing.length === 1 ? 'that link stays' : 'those links stay'} as text.`,
      );
    if (r.notMine.length)
      said.push(
        `Nothing called ${quoted(r.notMine)} is held by whoever this belongs to, so ${r.notMine.length === 1 ? 'that link stays' : 'those links stay'} as text.`,
      );
    notes.hidden = !said.length;
    notes.textContent = said.join(' ');
  };
  // What is already known shows at once; what is not is asked, and shown when it arrives (unless
  // the text has moved on by then).
  let turn = 0;
  const paint = async () => {
    const mine = ++turn;
    const text = area.value;
    const quick = bench.links.renderNow(text, o.home);
    draw(quick);
    const full = await bench.links.render(text, o.home);
    if (
      mine === turn &&
      (full.html !== quick.html ||
        full.missing.join() !== quick.missing.join() ||
        full.notMine.join() !== quick.notMine.join())
    )
      draw(full);
  };
  void paint();
  attachEntryPicker(area, bench);
  area.addEventListener('input', () => void paint());
  area.addEventListener('change', () => {
    if (redraw.active) return;
    // After the focus has moved on: writing it down draws the page again, which puts the focus
    // back where it was a moment ago, and that is not where the person went (a link, say).
    setTimeout(() => o.onChange(area.value), 0);
  });

  // A link opens the entry in this workbench; pointing at one shows what it is.
  const linkId = (ev: Event) => {
    const link = ev.target instanceof Element ? ev.target.closest('a.ls-entity') : null;
    return entryIdOfHref(link?.getAttribute('href') ?? null);
  };
  // Pressing a link must not take the focus from the text: that would write the text down and
  // draw the page again between the press and the release, and the click would be lost.
  shown.addEventListener('mousedown', (ev) => {
    if (linkId(ev)) ev.preventDefault();
  });
  shown.addEventListener('click', (ev) => {
    const id = linkId(ev);
    if (!id) return;
    ev.preventDefault();
    hideCard();
    // What was typed is kept before going elsewhere.
    if (area.value !== o.text) o.onChange(area.value);
    go(id);
  });
  attachLinkPreviews(shown, async (id) => {
    await bench.open(id, true);
    const entry = bench.view(id);
    if (!entry) return null;
    return {
      name: entry.name,
      what: kindsText(entry.kinds),
      excerpt: entry.description ? excerptOf(entry.description.text) : '',
    };
  });
  wrap.append(linkToolbar(area), area, shown, notes);
  return wrap;
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

const show = (v: unknown, bench: Bench, cmd?: Command): string => {
  if (cmd?.type === 'notes.set-order') return 'another order';
  if (cmd?.type === 'entry.set-slug' && v === null) return 'no link name';
  if (Array.isArray(v)) return v.map((p) => bench.displayName(p)).join(', ') || 'none';
  if (v === null) return 'nothing of its own (inherited)';
  if (typeof v === 'boolean') return v ? 'on' : 'off';
  return typeof v === 'string' ? `“${v}”` : String(v);
};

function conflictRow(bench: Bench, cmd: Command): HTMLElement {
  const label =
    cmd.stat?.name ??
    (cmd.type === 'entry.set-slug' ? 'link name' : undefined) ??
    (cmd.type === 'notes.set-order' ? 'order of the notes' : undefined) ??
    (cmd.kind ? `${cmd.kind} kind` : cmd.type === 'entry.set-name' ? 'name' : 'parents');
  const box = el('div', 'problem problem-conflict');
  box.setAttribute('role', 'alert');
  box.append(
    el('strong', undefined, 'Conflict. '),
    document.createTextNode(
      `The ${label} was changed elsewhere to ${show(cmd.theirs, bench, cmd)}. Yours: ${show(cmd.mine, bench, cmd)}.`,
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
