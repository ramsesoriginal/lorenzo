// The semilive editor (ADR 0511): the same options and the same editor object as
// `@lorenzo/lorenzoscript-editor`, with a different surface. Every paragraph, heading, list,
// table and code block is shown formatted; the one clicked or moved into becomes a text area
// holding its source. The original <textarea> stays the one place the text lives.
import { parse, render as renderScript } from '@lorenzo/lorenzoscript';
import {
  ACTIONS,
  type ActionName,
  DEFAULT_TOOLBAR,
  type Editor,
  type EditorOptions,
  keyAction,
  type State,
} from '@lorenzo/lorenzoscript-editor';
import { History } from './history';
import { caretInSource, definitionsFor, type Segment, segmentsOf } from './segments';

type Options = EditorOptions;

const HISTORY_TITLES = { undo: 'Undo', redo: 'Redo' } as const;

export function createEditor(options: Options): Editor {
  const { textarea, toolbar = DEFAULT_TOOLBAR } = options;
  const toHtml = options.render ?? ((source: string) => renderScript(parse(source)));
  const doc = textarea.ownerDocument;
  const make = <K extends keyof HTMLElementTagNameMap>(
    tag: K,
    className = '',
    attrs: Record<string, string> = {},
  ) => {
    const node = doc.createElement(tag);
    node.className = className;
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    return node;
  };

  const root = make('div', 'card ls-editor ls-semilive', { 'data-layout': 'live' });
  const bar = make('div', 'editor-toolbar', { role: 'toolbar', 'aria-label': 'Formatting' });
  const surface = make('div', 'ls-semilive-blocks ls-content', {
    role: 'group',
    'aria-label': textarea.getAttribute('aria-label') ?? 'Text',
  });
  root.append(bar, surface);
  textarea.before(root);
  textarea.hidden = true;
  textarea.classList.add('editor-content');

  const history = new History();
  let source = textarea.value;
  let segments: Segment[] = segmentsOf(source);
  /** The block that is a text area, as an index into `segments`, and its live span. */
  let active: { index: number; field: HTMLTextAreaElement } | null = null;
  let afterEscape = false;
  let groupTimer: ReturnType<typeof setTimeout> | undefined;
  let grouping = false;
  let snapped: { first: number; last: number } | null = null;

  /** Everything that writes the text goes through here: the original text area, and its events. */
  function write(next: string, event = true) {
    source = next;
    textarea.value = next;
    if (event) {
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      textarea.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  /** Remember the text as it was before a run of typing; a pause ends the run. */
  function remember() {
    if (!grouping) history.push(source);
    grouping = true;
    clearTimeout(groupTimer);
    groupTimer = setTimeout(() => {
      grouping = false;
    }, 600);
  }

  // The buttons.
  const buttons = new Map<string, HTMLButtonElement>();
  for (const tool of toolbar) {
    if (tool === '|') {
      bar.append(make('span', 'divider', { role: 'separator' }));
      continue;
    }
    const spec = tool === 'undo' || tool === 'redo' ? null : ACTIONS[tool as ActionName];
    const title = tool === 'undo' || tool === 'redo' ? HISTORY_TITLES[tool] : (spec?.title ?? '');
    const button = make('button', '', {
      type: 'button',
      title,
      'aria-label': title,
    });
    button.dataset.tool = tool;
    button.innerHTML = tool === 'undo' ? '↶' : tool === 'redo' ? '↷' : (spec?.label ?? '');
    button.addEventListener('click', () => {
      if (tool === 'undo') return step(true);
      if (tool === 'redo') return step(false);
      if (tool === 'entity' && options.reviewEntitySelection && active?.field) {
        const { selectionStart, selectionEnd } = active.field;
        if (selectionStart !== selectionEnd) return options.reviewEntitySelection();
      }
      if (!active) addBlockAtEnd();
      if (active) apply(ACTIONS[tool as ActionName].run(stateOf(active.field)));
    });
    buttons.set(tool, button);
    bar.append(button);
  }
  // Keep the focus and the selection in the text area when a button is pressed.
  bar.addEventListener('mousedown', (e) => {
    if ((e.target as Element).closest('button[data-tool]')) e.preventDefault();
  });

  const stateOf = (field: HTMLTextAreaElement): State => ({
    text: field.value,
    start: field.selectionStart,
    end: field.selectionEnd,
  });

  /** Apply a pure action to the open block. */
  function apply(next: State) {
    if (!active) return;
    const { field } = active;
    field.value = next.text;
    field.setSelectionRange(next.start, next.end);
    changed();
  }

  /** The open block's text changed: carry it into the whole text. */
  function changed() {
    if (!active) return;
    const seg = segments[active.index];
    if (!seg) return;
    remember();
    const text = active.field.value;
    write(source.slice(0, seg.from) + text + source.slice(seg.to));
    const delta = text.length - (seg.to - seg.from);
    seg.to += delta;
    for (const later of segments.slice(active.index + 1)) {
      later.from += delta;
      later.to += delta;
    }
    sizeToText(active.field);
    syncCaret();
  }

  /** Let the original text area say where the caret is, as the app reading it expects. */
  function syncCaret() {
    if (!active) return;
    const seg = segments[active.index];
    if (!seg) return;
    const { selectionStart, selectionEnd } = active.field;
    textarea.setSelectionRange(seg.from + selectionStart, seg.from + selectionEnd);
  }

  const sizeToText = (field: HTMLTextAreaElement) => {
    field.rows = Math.max(1, field.value.split('\n').length);
  };

  // Painting.
  async function paintBlock(host: HTMLElement, seg: Segment) {
    const own = source.slice(seg.from, seg.to);
    const defs = definitionsFor(source, segments, seg);
    const html = await toHtml(defs ? `${own}\n\n${defs}` : own);
    host.innerHTML = html;
  }

  function paint(focusAt?: number) {
    const nodes: HTMLElement[] = [];
    segments.forEach((seg, index) => {
      if (seg.type === 'definition' && index !== active?.index) {
        return; // Definitions show where they are used.
      }
      if (active && active.index === index) {
        const field = make('textarea', 'text-input ls-semilive-field', {
          'aria-label': 'Edit this part',
          spellcheck: 'true',
        });
        field.value = source.slice(seg.from, seg.to);
        sizeToText(field);
        active.field = field;
        const holder = make('div', 'ls-block ls-block-open', { 'data-index': String(index) });
        holder.append(field);
        nodes.push(holder);
        wire(field);
        return;
      }
      const host = make('div', 'ls-block', { 'data-index': String(index), tabindex: '0' });
      void paintBlock(host, seg);
      nodes.push(host);
    });
    surface.replaceChildren(...nodes);
    if (active && focusAt !== undefined) {
      active.field.focus();
      active.field.setSelectionRange(focusAt, focusAt);
      syncCaret();
    }
    snapped = null;
  }

  /** The text areas' own events. */
  function wire(field: HTMLTextAreaElement) {
    field.addEventListener('input', changed);
    field.addEventListener('keyup', syncCaret);
    field.addEventListener('click', syncCaret);
    field.addEventListener('keydown', (e) => onFieldKey(e, field));
  }

  function onFieldKey(e: KeyboardEvent, field: HTMLTextAreaElement) {
    const wasEscaped = afterEscape;
    afterEscape = e.key === 'Escape';
    if (!active) return;
    const index = active.index;
    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    const collapsed = field.selectionStart === field.selectionEnd;
    const atStart = collapsed && field.selectionStart === 0;
    const atEnd = collapsed && field.selectionEnd === field.value.length;
    const before = field.value.slice(0, field.selectionStart);
    const onFirstLine = !before.includes('\n');
    const onLastLine = !field.value.slice(field.selectionEnd).includes('\n');

    if (e.key === 'Escape') {
      e.preventDefault();
      leave();
      surface.querySelector<HTMLElement>(`[data-index="${index}"]`)?.focus();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      step(!e.shiftKey);
      return;
    }
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'y') {
      e.preventDefault();
      step(false);
      return;
    }
    if (plain && !e.shiftKey && (e.key === 'ArrowUp' || e.key === 'ArrowLeft')) {
      if ((e.key === 'ArrowUp' && collapsed && onFirstLine) || (e.key === 'ArrowLeft' && atStart)) {
        const previous = nearest(index, -1);
        if (previous !== null) {
          e.preventDefault();
          open(previous, 'end');
        }
      }
      return;
    }
    if (plain && !e.shiftKey && (e.key === 'ArrowDown' || e.key === 'ArrowRight')) {
      if ((e.key === 'ArrowDown' && collapsed && onLastLine) || (e.key === 'ArrowRight' && atEnd)) {
        const next = nearest(index, 1);
        if (next !== null) {
          e.preventDefault();
          open(next, 'start');
        }
      }
      return;
    }
    if (e.key === 'Backspace' && plain && field.value === '') {
      const previous = nearest(index, -1);
      e.preventDefault();
      removeOpen();
      if (previous !== null) open(previous > index ? previous - 1 : previous, 'end');
      return;
    }
    if (e.key === 'Enter' && plain && e.shiftKey) {
      // A new line in the same paragraph.
      e.preventDefault();
      apply({
        text: `${field.value.slice(0, field.selectionStart)}\n${field.value.slice(field.selectionEnd)}`,
        start: field.selectionStart + 1,
        end: field.selectionStart + 1,
      });
      return;
    }
    const result = keyAction(e, stateOf(field), wasEscaped);
    if (result.handled) {
      e.preventDefault();
      apply(result.state);
      return;
    }
    if (e.key === 'Enter' && plain && !e.shiftKey && !e.isComposing && atEnd) {
      // The end of an ordinary paragraph starts a new one.
      e.preventDefault();
      newBlockAfter(index);
    }
  }

  /** The next block that is not a definition, in a direction, or null. */
  function nearest(index: number, step: 1 | -1): number | null {
    for (let i = index + step; i >= 0 && i < segments.length; i += step)
      if (segments[i]?.type !== 'definition') return i;
    return null;
  }

  /** Close the open block: read the whole text again, so the blocks are what the text now says. */
  function leave() {
    active = null;
    segments = segmentsOf(source);
    paint();
  }

  function open(index: number, where: 'start' | 'end' | number) {
    const target = segments[index];
    if (!target) return;
    const from = target.from;
    if (active) {
      // What was typed may have split or joined blocks: read the text again, and find this one.
      active = null;
      segments = segmentsOf(source);
    }
    let found = segments.findIndex(
      (s) => s.from <= from && from <= s.to && s.type !== 'definition',
    );
    if (found < 0) found = Math.min(index, segments.length - 1);
    const seg = segments[found];
    if (!seg) return;
    const length = seg.to - seg.from;
    const at =
      where === 'start' ? 0 : where === 'end' ? length : Math.min(length, Math.max(0, where));
    active = { index: found, field: undefined as unknown as HTMLTextAreaElement };
    paint(at);
  }

  function newBlockAfter(index: number) {
    const seg = segments[index];
    if (!seg) return;
    remember();
    write(`${source.slice(0, seg.to)}\n\n${source.slice(seg.to)}`);
    const from = seg.to + 2;
    segments.splice(index + 1, 0, { from, to: from, type: 'paragraph' });
    for (const later of segments.slice(index + 2)) {
      later.from += 2;
      later.to += 2;
    }
    active = { index: index + 1, field: undefined as unknown as HTMLTextAreaElement };
    paint(0);
  }

  function addBlockAtEnd() {
    if (segments.length) {
      open(segments.length - 1, 'end');
      return;
    }
    segments = [{ from: 0, to: 0, type: 'paragraph' }];
    active = { index: 0, field: undefined as unknown as HTMLTextAreaElement };
    paint(0);
  }

  function removeOpen() {
    if (!active) return;
    const seg = segments[active.index];
    if (!seg) return;
    remember();
    const from = Math.max(0, seg.from - 2);
    write(source.slice(0, from) + source.slice(seg.to));
    active = null;
    segments = segmentsOf(source);
    paint();
  }

  /** Undo or redo across paragraphs. */
  function step(undo: boolean) {
    grouping = false;
    const next = undo ? history.undo(source) : history.redo(source);
    if (next === null) return;
    active = null;
    write(next);
    segments = segmentsOf(source);
    paint();
  }

  // A click on a formatted block opens it, with the caret near where it was clicked.
  const point = (x: number, y: number): { node: Node; offset: number } | null => {
    const d = doc as Document & {
      caretPositionFromPoint?: (
        x: number,
        y: number,
      ) => { offsetNode: Node; offset: number } | null;
      caretRangeFromPoint?: (x: number, y: number) => Range | null;
    };
    const position = d.caretPositionFromPoint?.(x, y);
    if (position) return { node: position.offsetNode, offset: position.offset };
    const range = d.caretRangeFromPoint?.(x, y);
    return range ? { node: range.startContainer, offset: range.startOffset } : null;
  };
  surface.addEventListener('click', (e) => {
    const block = (e.target as Element).closest<HTMLElement>('.ls-block:not(.ls-block-open)');
    if (!block || (e.target as Element).closest('a')) return;
    if (!doc.getSelection()?.isCollapsed) return;
    const index = Number(block.dataset.index);
    const seg = segments[index];
    if (!seg) return;
    const own = source.slice(seg.from, seg.to);
    const hit = point(e.clientX, e.clientY);
    const at =
      hit && hit.node.nodeType === 3
        ? caretInSource(own, hit.node.textContent ?? '', hit.offset)
        : own.length;
    open(index, at);
  });
  surface.addEventListener('keydown', (e) => {
    const block = (e.target as Element).closest<HTMLElement>('.ls-block:not(.ls-block-open)');
    if (block && e.target === block && (e.key === 'Enter' || e.key === 'F2')) {
      e.preventDefault();
      open(Number(block.dataset.index), 'end');
      return;
    }
    if (e.target instanceof HTMLTextAreaElement) return;
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      step(!e.shiftKey);
      return;
    }
    // A selection that spans paragraphs snaps to whole paragraphs, and typing over it does nothing.
    if (snapped && (e.key.length === 1 || ['Enter', 'Backspace', 'Delete'].includes(e.key))) {
      if (!(e.ctrlKey || e.metaKey)) e.preventDefault();
    }
  });

  const onSelection = () => {
    const selection = doc.getSelection();
    if (!selection || selection.isCollapsed || !selection.anchorNode || !selection.focusNode) {
      if (snapped) clearSnap();
      return;
    }
    const a = (selection.anchorNode as Node).parentElement?.closest<HTMLElement>('.ls-block');
    const b = (selection.focusNode as Node).parentElement?.closest<HTMLElement>('.ls-block');
    if (!a || !b || a === b || !surface.contains(a) || !surface.contains(b)) {
      if (snapped) clearSnap();
      return;
    }
    const first = Math.min(Number(a.dataset.index), Number(b.dataset.index));
    const last = Math.max(Number(a.dataset.index), Number(b.dataset.index));
    snapped = { first, last };
    for (const node of surface.querySelectorAll<HTMLElement>('.ls-block')) {
      const i = Number(node.dataset.index);
      node.toggleAttribute('data-selected', i >= first && i <= last);
    }
  };
  const clearSnap = () => {
    snapped = null;
    for (const node of surface.querySelectorAll('.ls-block[data-selected]'))
      node.removeAttribute('data-selected');
  };
  doc.addEventListener('selectionchange', onSelection);
  surface.addEventListener('copy', (e) => {
    if (!snapped) return;
    const from = segments[snapped.first]?.from;
    const to = segments[snapped.last]?.to;
    if (from === undefined || to === undefined) return;
    e.preventDefault();
    e.clipboardData?.setData('text/plain', source.slice(from, to));
  });

  // Start: the text as it is. An empty text opens one empty block to type into.
  if (segments.length === 0) {
    segments = [{ from: 0, to: 0, type: 'paragraph' }];
    active = { index: 0, field: undefined as unknown as HTMLTextAreaElement };
    paint();
  } else paint();

  return {
    element: root,
    replaceSelection(replacement) {
      if (!active) addBlockAtEnd();
      if (!active) return;
      const { field } = active;
      const start = field.selectionStart;
      const end = start + replacement.length;
      apply({
        text: field.value.slice(0, start) + replacement + field.value.slice(field.selectionEnd),
        start: end,
        end,
      });
    },
    async refresh() {
      // The text may have been set from outside.
      source = textarea.value;
      active = null;
      segments = segmentsOf(source);
      paint();
    },
    destroy() {
      clearTimeout(groupTimer);
      doc.removeEventListener('selectionchange', onSelection);
      textarea.classList.remove('editor-content');
      textarea.hidden = false;
      root.before(textarea);
      root.remove();
    },
  };
}
