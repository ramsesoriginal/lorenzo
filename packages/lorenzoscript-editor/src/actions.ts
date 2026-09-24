// Every edit the editor makes (ADR 0106): a pure function from the text and its
// selection to new ones, so each can be tested without a browser.

export type State = { text: string; start: number; end: number };
export type Action = (state: State) => State;

const lineStart = (text: string, i: number) => text.lastIndexOf('\n', i - 1) + 1;
const lineEnd = (text: string, i: number) => {
  const j = text.indexOf('\n', i);
  return j < 0 ? text.length : j;
};

/** `text` with [from, to) replaced by `insert`, and [start, end) selected in the result. */
const splice = (
  text: string,
  from: number,
  to: number,
  insert: string,
  start: number,
  end = start,
) => ({
  text: text.slice(0, from) + insert + text.slice(to),
  start,
  end,
});

/** Wraps the selection in `before`…`after`, or unwraps it if it already is. Nothing
 * selected: inserts `placeholder`, selected, to type over. */
export const wrap =
  (before: string, after = before, placeholder = 'text'): Action =>
  ({ text, start, end }) => {
    const outer = start - before.length;
    if (outer >= 0 && text.slice(outer, start) === before && text.slice(end).startsWith(after)) {
      return splice(
        text,
        outer,
        end + after.length,
        text.slice(start, end),
        outer,
        end - before.length,
      );
    }
    const inner = text.slice(start, end) || placeholder;
    const at = start + before.length;
    return splice(text, start, end, before + inner + after, at, at + inner.length);
  };

/** A list marker, bullet, task, or number, which another list action replaces rather than stacks on. */
const MARKER = /^(?:[-*+] (?:\[[ xX]\] )?|\d+[.)] )/;

/** Prefixes every line the selection touches; if they all start with `own`, removes it instead. */
const lines =
  (prefix: (k: number) => string, own: RegExp, replaces?: RegExp): Action =>
  ({ text, start, end }) => {
    const from = lineStart(text, start);
    const to = lineEnd(text, end);
    const old = text.slice(from, to).split('\n');
    const off = old.every((line) => own.test(line));
    const next = old.map((line, k) =>
      off ? line.replace(own, '') : prefix(k) + (replaces ? line.replace(replaces, '') : line),
    );
    const block = next.join('\n');
    if (start !== end) return splice(text, from, to, block, from, from + block.length);
    const shift = (next[0] as string).length - (old[0] as string).length;
    return splice(text, from, to, block, Math.max(from, start + shift));
  };

/** Cycles the cursor's line through `#`, `##`, `###`, and plain text. */
export const heading: Action = ({ text, start, end }) => {
  const from = lineStart(text, start);
  const to = lineEnd(text, start);
  const line = text.slice(from, to);
  const level = /^(#{1,6}) /.exec(line)?.[1]?.length ?? 0;
  const next = (level >= 3 ? '' : `${'#'.repeat(level + 1)} `) + line.replace(/^#{1,6} /, '');
  const shift = next.length - line.length;
  return splice(text, from, to, next, Math.max(from, start + shift), Math.max(from, end + shift));
};

/** `make(selection)` on lines of its own, with blank lines around it; `select` is within it. */
const block =
  (make: (selected: string) => { body: string; select?: [number, number] }): Action =>
  ({ text, start, end }) => {
    const { body, select = [body.length, body.length] } = make(text.slice(start, end));
    const before = text.slice(0, start);
    const after = text.slice(end);
    const lead = !before || before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n';
    const trail = !after || after.startsWith('\n\n') ? '' : after.startsWith('\n') ? '\n' : '\n\n';
    const at = start + lead.length;
    return splice(text, start, end, lead + body + trail, at + select[0], at + select[1]);
  };

/** `[selection](url)` with `url` selected to type over, or, with nothing selected, the text. */
const linkLike =
  (bang: string, placeholder: string): Action =>
  ({ text, start, end }) => {
    const label = text.slice(start, end) || placeholder;
    const labelAt = start + bang.length + 1;
    const urlAt = labelAt + label.length + 2;
    const insert = `${bang}[${label}](url)`;
    return start === end
      ? splice(text, start, end, insert, labelAt, labelAt + label.length)
      : splice(text, start, end, insert, urlAt, urlAt + 'url'.length);
  };

/** The next free `[^n]` after the selection, its definition at the end, ready to be written. */
export const footnote: Action = ({ text, end }) => {
  let n = 1;
  while (text.includes(`[^${n}]`)) n++;
  const withRef = `${text.slice(0, end)}[^${n}]${text.slice(end)}`;
  const out = `${withRef.trimEnd()}\n\n[^${n}]: `;
  return { text: out, start: out.length, end: out.length };
};

const iso = (d: Date) =>
  [d.getFullYear(), d.getMonth() + 1, d.getDate()].map((n) => String(n).padStart(2, '0')).join('-');

/** Today's `{{date}}`, in the writer's own time zone. */
export const date =
  (today: () => Date = () => new Date()): Action =>
  ({ text, start, end }) => {
    const insert = `{{date ${iso(today())}}}`;
    return splice(text, start, end, insert, start + insert.length);
  };

/** What a line continues with: quote markers and indentation, then maybe a list marker. */
const CONTINUES = /^((?:> ?)*[ \t]*)(?:([-*+] )(\[[ xX]\] )?|(\d+)([.)] ))?/;

/**
 * Enter: continues a list, task list, or quote on the next line, and ends it on an empty
 * item instead. Null means there's nothing to continue, so the browser's own newline applies.
 */
export function newline({ text, start, end }: State): State | null {
  if (start !== end) return null;
  const from = lineStart(text, start);
  const to = lineEnd(text, start);
  const [lead = '', prefix = '', bullet, task, number, delimiter] =
    CONTINUES.exec(text.slice(from, start)) ?? [];
  const listed = bullet !== undefined || number !== undefined;
  if (!listed && !prefix.includes('>')) return null;
  if (!text.slice(from + lead.length, to).trim()) {
    const kept = listed ? prefix : '';
    return splice(text, from, to, kept, from + kept.length);
  }
  const marker = bullet
    ? bullet + (task ? '[ ] ' : '')
    : number
      ? `${Number(number) + 1}${delimiter}`
      : '';
  const insert = `\n${prefix}${marker}`;
  return splice(text, start, start, insert, start + insert.length);
}

/**
 * Tab indents the selected lines, or the cursor's list item, by 4 spaces (the width that
 * continues a list item); elsewhere it inserts them. Shift-Tab (`out`) outdents by up to 4.
 */
export const indent =
  (out = false): Action =>
  ({ text, start, end }) => {
    const from = lineStart(text, start);
    const to = lineEnd(text, end);
    const item = MARKER.test(text.slice(from, to).trimStart());
    if (!out && !item && !text.slice(start, end).includes('\n')) {
      return splice(text, start, end, '    ', start + 4);
    }
    const old = text.slice(from, to).split('\n');
    const next = old.map((line) => (out ? line.replace(/^ {1,4}/, '') : `    ${line}`));
    const block = next.join('\n');
    const first = (next[0] as string).length - (old[0] as string).length;
    const last = block.length - (to - from);
    return splice(text, from, to, block, Math.max(from, start + first), Math.max(from, end + last));
  };

export type ActionName = keyof typeof ACTIONS;

/**
 * The toolbar's actions. `label` is trusted markup from this table only; `key` is the
 * Ctrl/⌘ shortcut, if any.
 */
export const ACTIONS = {
  bold: {
    label: '<strong>B</strong>',
    title: 'Bold',
    key: 'b',
    run: wrap('**', '**', 'bold text'),
  },
  italic: { label: '<em>I</em>', title: 'Italic', key: 'i', run: wrap('*', '*', 'italic text') },
  strike: { label: '<del>S</del>', title: 'Strikethrough', run: wrap('~~', '~~', 'struck text') },
  sub: { label: 'x<sub>2</sub>', title: 'Subscript', run: wrap('~', '~', '2') },
  sup: { label: 'x<sup>2</sup>', title: 'Superscript', run: wrap('^', '^', '2') },
  code: { label: '&lt;/&gt;', title: 'Code', run: wrap('`', '`', 'code') },
  math: { label: '∑', title: 'Math', run: wrap('$', '$', 'x^2') },
  link: { label: '↗', title: 'Link', key: 'k', run: linkLike('', 'text') },
  entity: { label: '⟦⟧', title: 'Link to an entity', run: wrap('[[', ']]', 'Name') },
  image: { label: '▣', title: 'Image', run: linkLike('!', 'description') },
  date: { label: '◷', title: "Today's date", run: date() },
  heading: { label: 'H', title: 'Heading', run: heading },
  quote: { label: '❝', title: 'Quote', run: lines(() => '> ', /^> ?/) },
  bullets: { label: '•', title: 'Bulleted list', run: lines(() => '- ', /^[-*+] (?!\[)/, MARKER) },
  numbers: {
    label: '1.',
    title: 'Numbered list',
    run: lines((k) => `${k + 1}. `, /^\d+[.)] /, MARKER),
  },
  tasks: {
    label: '☑',
    title: 'Task list',
    run: lines(() => '- [ ] ', /^[-*+] \[[ xX]\] /, MARKER),
  },
  codeblock: {
    label: '{ }',
    title: 'Code block',
    run: block((code) => ({
      body: `\`\`\`\n${code || 'code'}\n\`\`\``,
      select: [4, 4 + (code || 'code').length],
    })),
  },
  table: {
    label: '▦',
    title: 'Table',
    run: block(() => ({ body: '| Column | Column |\n| --- | --- |\n|  |  |', select: [2, 8] })),
  },
  rule: { label: '―', title: 'Horizontal rule', run: block(() => ({ body: '---' })) },
  toc: { label: '☰', title: 'Table of contents', run: block(() => ({ body: '{{TOC}}' })) },
  footnote: { label: '¹', title: 'Footnote', run: footnote },
} satisfies Record<string, { label: string; title: string; key?: string; run: Action }>;
