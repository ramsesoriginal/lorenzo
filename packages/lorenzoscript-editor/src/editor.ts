// The DOM layer (ADR 0106): enhances an existing <textarea> with a toolbar, keyboard
// helpers, and a live preview. Every edit itself is a pure action from ./actions.
import { parse, render as renderScript } from '@lorenzo/lorenzoscript';
import { ACTIONS, type ActionName, indent, newline, type State } from './actions';

export type Tool = ActionName | 'undo' | 'redo' | '|';

export type EditorOptions = {
  textarea: HTMLTextAreaElement;
  /** Action names in order, `'|'` for a divider. */
  toolbar?: Tool[];
  /** Preview beside the text (stacked on narrow screens), or behind a Write/Preview tab. */
  layout?: 'split' | 'tabs';
  /** Source to HTML. Default: LorenzoScript without a resolver. May be async, e.g. to fetch
   * `references()` first; an older result never replaces a newer one. */
  render?: (source: string) => string | Promise<string>;
  /** Milliseconds after the last keystroke before the preview re-renders. */
  delay?: number;
};

export type Editor = { element: HTMLElement; refresh: () => Promise<void>; destroy: () => void };

// biome-ignore format: one toolbar group per line
export const DEFAULT_TOOLBAR: Tool[] = [
  'bold', 'italic', 'strike', 'code', '|',
  'heading', 'quote', 'bullets', 'numbers', 'tasks', '|',
  'link', 'entity', 'image', '|',
  'codeblock', 'table', 'math', 'footnote', 'date', '|',
  'undo', 'redo',
];

const HISTORY = { undo: { label: '↶', title: 'Undo' }, redo: { label: '↷', title: 'Redo' } };
const SHORTCUTS = new Map(
  Object.entries(ACTIONS).flatMap(([name, a]) => ('key' in a ? [[a.key, name as ActionName]] : [])),
);

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
      doc.execCommand(insert ? 'insertText' : 'delete', false, insert);
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
    const modified = e.ctrlKey || e.metaKey || e.altKey;
    if (e.key === 'Tab' && !modified) {
      // Escape, then Tab, leaves the editor: taking Tab over must not trap keyboard users.
      if (wasEscaped) return;
      e.preventDefault();
      apply(indent(e.shiftKey)(state()));
    } else if (e.key === 'Enter' && !modified && !e.shiftKey && !e.isComposing) {
      const next = newline(state());
      if (!next) return;
      e.preventDefault();
      apply(next);
    } else if ((e.ctrlKey || e.metaKey) && !e.altKey) {
      const name = SHORTCUTS.get(e.key.toLowerCase());
      if (!name) return;
      e.preventDefault();
      apply(ACTIONS[name].run(state()));
    }
  };
  textarea.addEventListener('keydown', onKey);

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
    refresh,
    destroy() {
      clearTimeout(timer);
      textarea.removeEventListener('keydown', onKey);
      textarea.removeEventListener('input', onInput);
      textarea.classList.remove('editor-content');
      textarea.hidden = false;
      root.before(textarea);
      root.remove();
    },
  };
}
