// A text edited where it is drawn (ADR 0251): every block of the text is shown as it reads, except
// the one with the caret, which is its source. Click a block, or move into it with the arrow
// keys, and it turns into source; leave it and it is drawn again. The blocks are the text's
// paragraphs, lists, headings and code blocks, told apart by blank lines.

import type { Bench } from '../core/bench';
import { entryIdOfHref, type Rendered } from '../core/links';
import {
  dropBlock,
  enterIn,
  joinBlocks,
  mergeUp,
  onFirstLine,
  onLastLine,
  splitBlock,
  splitBlocks,
} from './blocks';
import { redraw } from './entryPane';
import { attachEntryPicker } from './entryPicker';
import { openLink } from './entryPickerText';
import { attachLinkPreviews, excerptOf, hideCard } from './linkPreview';
import { decorateStats } from './statChips';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

/** What an editor keeps while the page is drawn again around it. */
interface State {
  /** The text this was made from, and was last written as. */
  base: string;
  blocks: string[];
  active: number | null;
  /** Where the caret goes when a block turns into source. */
  caret: 'start' | 'end' | number;
  /** Something was typed since `base`. */
  dirty: boolean;
  /** The caret was in the editor when the page was last drawn (so it is put back). */
  focused: boolean;
}
const states = new Map<string, State>();

export interface LiveOptions {
  bench: Bench;
  /** Tells the editor from the others on the page, and a focus to be put back. */
  key: string;
  /** The entry the text belongs to: what `my/` links are held by. */
  home: string;
  label: string;
  text: string;
  /** Said where the text is empty. */
  placeholder?: string;
  onChange: (text: string) => void;
  go: (id: string) => void;
}

/** Makes a field as tall as its text, however the lines wrap. */
const grow = (a: HTMLTextAreaElement) => {
  a.style.height = 'auto';
  a.style.height = `${a.scrollHeight}px`;
};

const quoted = (slugs: string[]) => slugs.map((s) => `“${s}”`).join(', ');

export function liveEditor(o: LiveOptions): HTMLElement {
  let st = states.get(o.key);
  // A new source (the text was changed elsewhere, nothing typed here) starts over.
  if (!st || (st.base !== o.text && !st.dirty)) {
    const blocks = splitBlocks(o.text);
    st = {
      base: o.text,
      blocks,
      // An empty text is a field to write in, shown as its prompt; it does not take the focus.
      active: blocks.length === 1 && blocks[0] === '' ? 0 : null,
      caret: 'end',
      dirty: false,
      focused: false,
    };
  }
  states.set(o.key, st);
  const state = st;

  const wrap = el('div', 'text-editor live');
  const doc = el('div', 'live-doc ls-content text-preview');
  doc.setAttribute('aria-label', `${o.label}, as it reads`);
  doc.tabIndex = 0;
  const notes = el('p', 'muted link-notes');
  notes.hidden = true;
  let area: HTMLTextAreaElement | null = null;
  let skipFocus = false;
  /** Set while the blocks are drawn again: a field taken away is not the person leaving it. */
  let drawing = false;

  // ---- what is drawn --------------------------------------------------------------------------

  const html = (block: string) => o.bench.links.renderNow(block, o.home).html;

  const draw = () => {
    drawing = true;
    doc.replaceChildren();
    area = null;
    state.blocks.forEach((block, i) => {
      if (state.active === i) {
        const a = el('textarea', 'text-edit live-source');
        a.value = block;
        a.placeholder = o.placeholder ?? '';
        a.rows = 1;
        a.dataset.key = o.key;
        a.setAttribute('aria-label', o.label);
        area = a;
        a.addEventListener('focus', () => {
          state.focused = true;
        });
        attachEntryPicker(a, o.bench);
        wireSource(a, i);
        doc.append(a);
        // Sized to what is in it, wrapped lines included (after it is on the page).
        requestAnimationFrame(() => grow(a));
      } else {
        const b = el('div', 'live-block');
        b.dataset.block = String(i);
        if (block.trim() === '') {
          b.classList.add('live-empty');
          b.textContent = o.placeholder ?? '';
        } else {
          const drawn = html(block);
          b.innerHTML = drawn; // escaped by the renderer (ADR 0100)
          b.dataset.raw = drawn;
          decorateStats(b, o.bench, o.home);
        }
        b.querySelectorAll<HTMLElement>('a.ls-entity').forEach((a, n) => {
          a.dataset.key = `${o.key}:link:${i}:${n}`;
        });
        b.querySelectorAll<HTMLElement>('.ls-stat').forEach((c, n) => {
          c.dataset.key = `${o.key}:stat:${i}:${n}`;
        });
        b.addEventListener('mousedown', (ev) => {
          if (linkId(ev) || (ev.target as Element).closest?.('.stat-step'))
            return ev.preventDefault();
          ev.preventDefault();
          activate(i, 'end');
        });
        doc.append(b);
      }
    });
    drawing = false;
  };

  const showNotes = (r: Rendered) => {
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

  // What is already known shows at once; what is not is asked, and shown when it arrives.
  let turn = 0;
  const paint = async () => {
    const mine = ++turn;
    const text = joinBlocks(state.blocks);
    const quick = o.bench.links.renderNow(text, o.home);
    showNotes(quick);
    const full = await o.bench.links.render(text, o.home);
    if (mine !== turn) return;
    showNotes(full);
    // The blocks that are drawn (not the one being typed in) may have links that now resolve.
    doc.querySelectorAll<HTMLElement>('.live-block[data-block]').forEach((b) => {
      const block = state.blocks[Number(b.dataset.block)] ?? '';
      if (block.trim() !== '') {
        const now = html(block);
        // Compared with what was drawn, not with the page (the chips have buttons added).
        if (b.dataset.raw !== now) {
          b.innerHTML = now;
          b.dataset.raw = now;
          decorateStats(b, o.bench, o.home);
        }
      }
    });
  };

  // ---- changing what is source ----------------------------------------------------------------

  const focusSource = () => {
    if (!area) return;
    area.focus();
    const at =
      state.caret === 'start' ? 0 : state.caret === 'end' ? area.value.length : state.caret;
    area.setSelectionRange(at, at);
  };

  const activate = (i: number, caret: State['caret']) => {
    // A block left empty (a new one nothing was typed in) is not kept.
    if (
      state.active !== null &&
      state.active !== i &&
      (state.blocks[state.active] ?? '').trim() === ''
    ) {
      const gone = state.active;
      state.blocks = dropBlock(state.blocks, gone);
      i = gone < i ? i - 1 : i;
    }
    state.active = Math.max(0, Math.min(i, state.blocks.length - 1));
    state.caret = caret;
    draw();
    focusSource();
  };

  const commit = () => {
    state.blocks = state.blocks.filter((b) => b.trim() !== '');
    if (!state.blocks.length) state.blocks = [''];
    const text = joinBlocks(state.blocks);
    if (state.dirty && text !== state.base) {
      state.base = text;
      state.dirty = false;
      // After the focus has moved on: writing it down draws the page again, which puts the focus
      // back where it was a moment ago, and that is not where the person went (a link, say).
      setTimeout(() => o.onChange(text), 0);
    }
    state.dirty = false;
  };

  const leave = (refocus: boolean) => {
    if (state.active === null) return;
    state.active = null;
    state.focused = false;
    commit();
    draw();
    if (refocus) {
      skipFocus = true;
      doc.focus();
    }
  };

  // ---- the source of one block ----------------------------------------------------------------

  const wireSource = (a: HTMLTextAreaElement, i: number) => {
    const fit = () => grow(a);
    a.addEventListener('input', () => {
      state.blocks[i] = a.value;
      state.dirty = true;
      fit();
      void paint();
    });
    a.addEventListener('keydown', (ev) => {
      // The picker has the keys while its list is open.
      if (ev.defaultPrevented || ev.isComposing) return;
      const at = a.selectionStart;
      const plain =
        at === a.selectionEnd && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey;
      if (ev.key === 'ArrowUp' && plain && onFirstLine(a.value, at) && i > 0) {
        ev.preventDefault();
        activate(i - 1, 'end');
      } else if (
        ev.key === 'ArrowDown' &&
        plain &&
        onLastLine(a.value, at) &&
        i < state.blocks.length - 1
      ) {
        ev.preventDefault();
        activate(i + 1, 'start');
      } else if (ev.key === 'ArrowLeft' && plain && at === 0 && i > 0) {
        ev.preventDefault();
        activate(i - 1, 'end');
      } else if (
        ev.key === 'ArrowRight' &&
        plain &&
        at === a.value.length &&
        i < state.blocks.length - 1
      ) {
        ev.preventDefault();
        activate(i + 1, 'start');
      } else if (ev.key === 'Enter' && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey) {
        ev.preventDefault();
        const made = enterIn(a.value, at);
        state.dirty = true;
        if (made.kind === 'newline') {
          state.blocks[i] = made.text;
          state.caret = made.caret;
          draw();
          focusSource();
        } else {
          state.blocks = splitBlock(state.blocks, i, made.before, made.after);
          state.active = null;
          activate(i + 1, 'start');
        }
        void paint();
      } else if (ev.key === 'Backspace' && plain && at === 0 && i > 0) {
        ev.preventDefault();
        const merged = mergeUp(state.blocks, i);
        if (merged) {
          state.blocks = merged.blocks;
          state.dirty = true;
          state.active = merged.active;
          state.caret = merged.caret;
          draw();
          focusSource();
          void paint();
        }
      } else if (ev.key === 'Escape') {
        ev.preventDefault();
        leave(true);
      }
    });
  };

  // Leaving the editor (not moving inside it) ends the source.
  wrap.addEventListener('focusout', (ev) => {
    if (redraw.active || drawing || !wrap.isConnected) return;
    const to = ev.relatedTarget;
    if (to instanceof Node && (wrap.contains(to) || (to as Element).closest?.('.entry-picker')))
      return;
    leave(false);
  });
  // Tabbing in puts the caret in the first block.
  doc.addEventListener('focus', () => {
    if (skipFocus) {
      skipFocus = false;
      return;
    }
    if (state.active === null) activate(0, 'start');
  });

  // ---- links in the drawn blocks --------------------------------------------------------------

  const linkId = (ev: Event) => {
    const link = ev.target instanceof Element ? ev.target.closest('a.ls-entity') : null;
    return entryIdOfHref(link?.getAttribute('href') ?? null);
  };
  doc.addEventListener('click', (ev) => {
    const id = linkId(ev);
    if (!id) return;
    ev.preventDefault();
    hideCard();
    // What was typed is kept before going elsewhere.
    if (state.active !== null) leave(false);
    else commit();
    o.go(id);
  });
  attachLinkPreviews(doc, async (id) => {
    await o.bench.open(id, true);
    const entry = o.bench.view(id);
    if (!entry) return null;
    return {
      name: entry.name,
      what: entry.kinds.length
        ? entry.kinds.map((k) => k.replace('_', ' ')).join(' and ')
        : 'bare entry',
      excerpt: entry.description ? excerptOf(entry.description.text) : '',
    };
  });

  // ---- the buttons over the text --------------------------------------------------------------

  const bar = el('div', 'text-toolbar');
  bar.setAttribute('role', 'toolbar');
  bar.setAttribute('aria-label', 'Insert');
  for (const [label, image] of [
    ['Link to an entry', false],
    ['Show a picture', true],
  ] as const) {
    const b = el('button', 'btn', label);
    b.type = 'button';
    b.addEventListener('click', () => {
      // With no block being written, the last one is.
      if (state.active === null) activate(state.blocks.length - 1, 'end');
      const target = area;
      if (!target) return;
      const made = openLink(target.value, target.selectionStart, target.selectionEnd, image);
      target.value = made.text;
      target.focus();
      target.setSelectionRange(made.caret, made.caret);
      // The picker and the preview follow what is typed.
      target.dispatchEvent(new Event('input'));
    });
    // Pressing must not take the focus from the text, or the caret and selection are lost.
    b.addEventListener('mousedown', (ev) => ev.preventDefault());
    bar.append(b);
  }

  draw();
  wrap.append(bar, doc, notes);
  void paint();
  // A redraw of the page while a block is source puts it back as source.
  if (state.active !== null && state.focused && document.activeElement === document.body)
    queueMicrotask(() => {
      // The page may have put the focus and the selection back itself by now.
      if (document.activeElement === document.body) focusSource();
    });
  return wrap;
}
