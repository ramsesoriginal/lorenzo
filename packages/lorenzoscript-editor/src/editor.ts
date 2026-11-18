// The DOM layer (ADR 0106): enhances an existing <textarea> with a toolbar, keyboard
// helpers, and a live preview. Every edit itself is a pure action from ./actions.
import { parse, render as renderScript } from '@lorenzo/lorenzoscript';
import { ACTIONS, type ActionName, type State } from './actions';
import { findAll, replaceMatches } from './find';
import { keyAction } from './keys';
import { htmlToScript, worthConverting } from './paste';

export type Tool = ActionName | 'undo' | 'redo' | '|';

export type EditorOptions = {
  textarea: HTMLTextAreaElement;
  /** Open a host-provided review when the entity tool is used with a selection. */
  reviewEntitySelection?: () => void;
  /** Action names in order, `'|'` for a divider. */
  toolbar?: Tool[];
  /** Preview beside the text (stacked on narrow screens), or behind a Write/Preview tab. */
  layout?: 'split' | 'tabs';
  /** Source to HTML. Default: LorenzoScript without a resolver. May be async, e.g. to fetch
   * `references()` first; an older result never replaces a newer one. */
  render?: (source: string) => string | Promise<string>;
  /** Milliseconds after the last keystroke before the preview re-renders. */
  delay?: number;
  /** Pasted HTML from Word, Google Docs or a page becomes LorenzoScript (ADR 0512). Off by default. */
  pasteFromWord?: boolean;
  /** Ctrl/Cmd+H opens find and replace over the text (ADR 0512). Off by default. */
  findReplace?: boolean;
};

export type Editor = {
  replaceSelection: (replacement: string) => void;
  element: HTMLElement;
  refresh: () => Promise<void>;
  destroy: () => void;
};

// biome-ignore format: one toolbar group per line
export const DEFAULT_TOOLBAR: Tool[] = [
  'bold', 'italic', 'strike', 'code', '|',
  'heading', 'quote', 'bullets', 'numbers', 'tasks', '|',
  'link', 'entity', 'image', '|',
  'codeblock', 'table', 'math', 'footnote', 'date', '|',
  'undo', 'redo',
];

const HISTORY = { undo: { label: '↶', title: 'Undo' }, redo: { label: '↷', title: 'Redo' } };

export function createEditor(options: EditorOptions): Editor {
  const { textarea, toolbar = DEFAULT_TOOLBAR, layout = 'split', delay = 150 } = options;
  const toHtml = options.render ?? ((source: string) => renderScript(parse(source)));
  const doc = textarea.ownerDocument;
  const make = (tag: string, className: string, attrs: Record<string, string> = {}) => {
    const node = doc.createElement(tag);
    node.className = className;
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    return node;
  };

  const root = make('div', 'card ls-editor', { 'data-layout': layout });
  const bar = make('div', 'editor-toolbar', { role: 'toolbar', 'aria-label': 'Formatting' });
  const panes = make('div', 'ls-editor-panes');
  const preview = make('div', 'editor-content ls-content ls-preview', {
    role: 'region',
    'aria-label': 'Preview',
  });
  textarea.before(root);
  root.append(bar, panes);
  panes.append(textarea, preview);
  textarea.classList.add('editor-content');

  const state = (): State => ({
    text: textarea.value,
    start: textarea.selectionStart,
    end: textarea.selectionEnd,
  });

  /** Replaces only what changed, through insertText, so the browser's own undo keeps working. */
  function apply(next: State): void {
    const prev = textarea.value;
    let a = 0;
    while (a < prev.length && prev[a] === next.text[a]) a++;
    let b = 0;
    const room = Math.min(prev.length, next.text.length) - a;
    while (b < room && prev[prev.length - 1 - b] === next.text[next.text.length - 1 - b]) b++;
    textarea.focus();
    if (prev !== next.text) {
      textarea.setSelectionRange(a, prev.length - b);
      const insert = next.text.slice(a, next.text.length - b);
      doc.execCommand?.(insert ? 'insertText' : 'delete', false, insert);
      // Where insertText isn't supported: the same result, without native undo.
      if (textarea.value !== next.text) {
        textarea.value = next.text;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
    textarea.setSelectionRange(next.start, next.end);
  }

  for (const tool of toolbar) {
    if (tool === '|') {
      bar.append(make('span', 'divider'));
      continue;
    }
    const spec: { label: string; title: string; key?: string } =
      tool === 'undo' || tool === 'redo' ? HISTORY[tool] : ACTIONS[tool];
    const title = spec.key ? `${spec.title} (Ctrl/⌘+${spec.key.toUpperCase()})` : spec.title;
    const button = make('button', '', { type: 'button', title, 'aria-label': spec.title });
    button.dataset.tool = tool;
    button.innerHTML = spec.label;
    button.addEventListener('click', () => {
      if (tool === 'undo' || tool === 'redo') {
        textarea.focus();
        doc.execCommand(tool);
      } else if (
        tool === 'entity' &&
        options.reviewEntitySelection &&
        textarea.selectionStart !== textarea.selectionEnd
      ) {
        options.reviewEntitySelection();
      } else apply(ACTIONS[tool].run(state()));
    });
    bar.append(button);
  }
  // Keep the textarea's focus and selection when a toolbar button is pressed.
  bar.addEventListener('mousedown', (e) => {
    if ((e.target as Element).closest('button[data-tool]')) e.preventDefault();
  });

  let escaped = false;
  const onKey = (e: KeyboardEvent) => {
    const wasEscaped = escaped;
    escaped = e.key === 'Escape';
    const result = keyAction(e, state(), wasEscaped);
    if (!result.handled) return;
    e.preventDefault();
    apply(result.state);
  };
  textarea.addEventListener('keydown', onKey);

  const onPaste = (e: ClipboardEvent) => {
    const html = e.clipboardData?.getData('text/html') ?? '';
    if (!html || !worthConverting(html)) return;
    const converted = htmlToScript(html);
    if (!converted) return;
    e.preventDefault();
    const current = state();
    const end = current.start + converted.length;
    apply({
      text: current.text.slice(0, current.start) + converted + current.text.slice(current.end),
      start: end,
      end,
    });
  };
  if (options.pasteFromWord) textarea.addEventListener('paste', onPaste);

  const finder = options.findReplace ? findBar() : null;
  const onFind = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'h') {
      e.preventDefault();
      finder?.open();
    }
  };
  if (finder) {
    textarea.addEventListener('keydown', onFind);
    root.insertBefore(finder.element, panes);
  }

  /** The find and replace bar: Find, Replace, Next, Replace, Replace all, and a count. */
  function findBar() {
    const element = make('div', 'row ls-find', {
      role: 'search',
      'aria-label': 'Find and replace',
    });
    element.hidden = true;
    const field = (label: string) => {
      const input = make('input', 'text-input', {
        type: 'text',
        'aria-label': label,
        placeholder: label,
      });
      return input as HTMLInputElement;
    };
    const find = field('Find');
    const replace = field('Replace with');
    const count = make('span', 'caption', { role: 'status' });
    const button = (label: string, run: () => void) => {
      const b = make('button', 'btn btn-secondary', { type: 'button' });
      b.textContent = label;
      b.addEventListener('click', run);
      return b;
    };
    const matches = () => findAll(textarea.value, find.value);
    const refresh = () => {
      const n = matches().length;
      count.textContent = find.value ? `${n} ${n === 1 ? 'match' : 'matches'}` : '';
    };
    const next = () => {
      const all = matches();
      const from = textarea.selectionEnd;
      const hit = all.find(([start]) => start >= from) ?? all[0];
      if (!hit) return refresh();
      textarea.focus();
      textarea.setSelectionRange(hit[0], hit[1]);
    };
    const replaceOne = () => {
      const selected = textarea.value.slice(textarea.selectionStart, textarea.selectionEnd);
      if (find.value && selected.toLocaleLowerCase() === find.value.toLocaleLowerCase()) {
        const text = textarea.value;
        apply({
          text:
            text.slice(0, textarea.selectionStart) +
            replace.value +
            text.slice(textarea.selectionEnd),
          start: textarea.selectionStart + replace.value.length,
          end: textarea.selectionStart + replace.value.length,
        });
      }
      next();
      refresh();
    };
    const replaceEvery = () => {
      const result = replaceMatches(textarea.value, find.value, replace.value);
      if (!result.count) return refresh();
      apply({ text: result.text, start: 0, end: 0 });
      count.textContent = `${result.count} replaced`;
    };
    find.addEventListener('input', refresh);
    find.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        next();
      }
      if (e.key === 'Escape') close();
    });
    const close = () => {
      element.hidden = true;
      textarea.focus();
    };
    element.append(
      find,
      replace,
      button('Next', next),
      button('Replace', replaceOne),
      button('Replace all', replaceEvery),
      button('Close', close),
      count,
    );
    return {
      element,
      open() {
        element.hidden = false;
        const word = textarea.value.slice(textarea.selectionStart, textarea.selectionEnd);
        if (word && !word.includes('\n')) find.value = word;
        refresh();
        find.focus();
        find.select();
      },
    };
  }

  let version = 0;
  const refresh = async () => {
    const mine = ++version;
    const html = await toHtml(textarea.value);
    if (mine === version) preview.innerHTML = html;
  };
  let timer: ReturnType<typeof setTimeout> | undefined;
  const onInput = () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, delay);
  };
  textarea.addEventListener('input', onInput);

  if (layout === 'tabs') bar.append(tabs());
  void refresh();

  /** Write/Preview tabs: one pane at a time, the formatting buttons off while previewing. */
  function tabs(): HTMLElement {
    const list = make('div', 'tabs', { role: 'tablist' });
    const show = (previewing: boolean) => {
      textarea.hidden = previewing;
      preview.hidden = !previewing;
      for (const [k, tab] of [...list.children].entries()) {
        tab.setAttribute('aria-selected', String(k === Number(previewing)));
      }
      for (const button of bar.querySelectorAll<HTMLButtonElement>('button[data-tool]')) {
        button.disabled = previewing;
      }
      if (previewing) void refresh();
    };
    for (const [k, label] of ['Write', 'Preview'].entries()) {
      const tab = make('button', 'tab', { type: 'button', role: 'tab' });
      tab.textContent = label;
      tab.addEventListener('click', () => show(k === 1));
      list.append(tab);
    }
    show(false);
    return list;
  }

  return {
    element: root,
    replaceSelection(replacement) {
      const current = state();
      const end = current.start + replacement.length;
      apply({
        text: current.text.slice(0, current.start) + replacement + current.text.slice(current.end),
        start: end,
        end,
      });
    },
    refresh,
    destroy() {
      clearTimeout(timer);
      textarea.removeEventListener('keydown', onKey);
      textarea.removeEventListener('paste', onPaste);
      textarea.removeEventListener('keydown', onFind);
      finder?.element.remove();
      textarea.removeEventListener('input', onInput);
      textarea.classList.remove('editor-content');
      textarea.hidden = false;
      root.before(textarea);
      root.remove();
    },
  };
}
