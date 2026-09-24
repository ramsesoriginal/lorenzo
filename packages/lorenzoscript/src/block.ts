// Block pass (ADR 0100): containers collect their lines, strip their marker
// or indent, and recurse. Paragraph text is handed to the inline pass.
import type { Block, Document, Item } from './ast';
import { MAX_NESTING, parseInline } from './inline';

type Lines = string[];
type Rule = {
  re: RegExp;
  /** Whether a line starting this block may end a paragraph. */
  interrupts: (m: RegExpExecArray) => boolean;
  parse: (lines: Lines, i: number, m: RegExpExecArray) => [Block, number];
};

const FENCE = /^( {0,3})(`{3,}(?=[^`]*$)|~{3,})(.*)$/;
const HEADING = /^ {0,3}(#{1,6})(?=[ \t]|$)(.*)$/;
const RULE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const QUOTE = /^ {0,3}> ?/;
const LIST = /^( {0,3})(?:([-+*])|(\d{1,9})([.)]))( +|$)/;
const TASK = /^\[([ xX])\](?:[ \t]+|$)/;

const blank = (line: string) => line.trim() === '';
const indent = (line: string) => line.length - line.trimStart().length;
const always = () => true;

export function parse(source: string): Document {
  const text = source.replace(/\r\n?/g, '\n').replace(/\0/g, String.fromCharCode(0xfffd));
  // A final newline ends the last line; it doesn't start another one.
  const lines = text.replace(/\n$/, '').split('\n').map(expandTabs);
  return { children: parseBlocks(lines).blocks };
}

/** Leading tabs become spaces, to the next 4-column stop. */
function expandTabs(line: string): string {
  const lead = /^[ \t]*/.exec(line)?.[0] ?? '';
  if (!lead.includes('\t')) return line;
  let spaces = '';
  for (const c of lead) spaces += c === '\t' ? ' '.repeat(4 - (spaces.length % 4)) : ' ';
  return spaces + line.slice(lead.length);
}

/** `loose`: a blank line separates two of these blocks (decides list tightness). */
function parseBlocks(lines: Lines): { blocks: Block[]; loose: boolean } {
  const blocks: Block[] = [];
  let loose = false;
  let gap = false;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] as string;
    if (blank(line)) {
      gap = blocks.length > 0;
      i++;
      continue;
    }
    loose ||= gap;
    gap = false;
    const found = match(line);
    const [block, next] = found ? found[0].parse(lines, i, found[1]) : paragraph(lines, i);
    blocks.push(block);
    i = next;
  }
  return { blocks, loose };
}

let depth = 0;

/** A container's content, one level deeper. The MAX_NESTING-th container holds only text. */
function nested(lines: Lines): { blocks: Block[]; loose: boolean } {
  if (depth >= MAX_NESTING - 1) {
    const text = lines.join('\n').trim();
    return {
      blocks: text ? [{ type: 'paragraph', children: parseInline(text) }] : [],
      loose: false,
    };
  }
  depth++;
  try {
    return parseBlocks(lines);
  } finally {
    depth--;
  }
}

const RULES: Rule[] = [
  { re: /^ {4}/, interrupts: () => false, parse: indentedCode },
  { re: FENCE, interrupts: always, parse: fencedCode },
  { re: HEADING, interrupts: always, parse: heading },
  { re: RULE, interrupts: always, parse: (_, i) => [{ type: 'rule' }, i + 1] },
  { re: QUOTE, interrupts: always, parse: blockquote },
  {
    re: LIST,
    // Only a non-empty item, and only an ordered one starting at 1, may end a paragraph.
    interrupts: (m) =>
      !blank(m.input.slice(m[0].length)) && (m[3] === undefined || Number(m[3]) === 1),
    parse: list,
  },
];

function match(line: string): [Rule, RegExpExecArray] | undefined {
  for (const rule of RULES) {
    const m = rule.re.exec(line);
    if (m) return [rule, m];
  }
}

function interrupts(line: string): boolean {
  const found = match(line);
  return found ? found[0].interrupts(found[1]) : false;
}

/**
 * A container's content lines. A line without the container's marker still belongs to it
 * if it continues paragraph text ("lazy continuation"). Whether the content ends in
 * paragraph text is tracked line by line, looking through nested quote and list markers,
 * because re-parsing the content for every such line costs exponential time in nesting.
 */
class Content {
  readonly lines: Lines = [];
  private fenced = false;
  private open = false;

  add(line: string, lazy = false): void {
    this.lines.push(line);
    if (lazy) return;
    const text = innermost(line);
    if (FENCE.test(text)) this.fenced = !this.fenced;
    this.open = !this.fenced && !blank(text) && !match(text);
  }

  continues(line: string): boolean {
    return this.open && !blank(line) && !interrupts(line);
  }
}

const marker = (text: string) => QUOTE.exec(text) ?? (RULE.test(text) ? null : LIST.exec(text));

/** A line without any of its nested quote and list markers. */
function innermost(line: string): string {
  let text = line;
  for (let k = 0, m = marker(text); m && k < MAX_NESTING; k++, m = marker(text)) {
    text = text.slice(m[0].length);
  }
  return text;
}

function paragraph(lines: Lines, i: number): [Block, number] {
  let j = i + 1;
  while (j < lines.length && !blank(lines[j] as string) && !interrupts(lines[j] as string)) j++;
  const text = lines
    .slice(i, j)
    .map((l) => l.trimStart())
    .join('\n')
    .trimEnd();
  return [{ type: 'paragraph', children: parseInline(text) }, j];
}

function heading(_: Lines, i: number, m: RegExpExecArray): [Block, number] {
  const text = (m[2] as string)
    .trim()
    .replace(/(^|[ \t])#+$/, '')
    .trim();
  return [{ type: 'heading', level: (m[1] as string).length, children: parseInline(text) }, i + 1];
}

function indentedCode(lines: Lines, i: number): [Block, number] {
  const body: Lines = [];
  let j = i;
  for (; j < lines.length; j++) {
    const line = lines[j] as string;
    if (!blank(line) && indent(line) < 4) break;
    body.push(line.slice(Math.min(4, indent(line))));
  }
  while (body.length && blank(body.at(-1) as string)) {
    body.pop();
    j--;
  }
  return [{ type: 'code', lang: '', text: `${body.join('\n')}\n` }, j];
}

function fencedCode(lines: Lines, i: number, m: RegExpExecArray): [Block, number] {
  const [, ind = '', fence = '', info = ''] = m;
  const close = new RegExp(`^ {0,3}${fence[0]}{${fence.length},}[ \\t]*$`);
  const strip = new RegExp(`^ {0,${ind.length}}`);
  let text = '';
  let j = i + 1;
  for (; j < lines.length && !close.test(lines[j] as string); j++) {
    text += `${(lines[j] as string).replace(strip, '')}\n`;
  }
  return [{ type: 'code', lang: info.trim().split(/\s+/)[0] as string, text }, j + 1];
}

function blockquote(lines: Lines, i: number): [Block, number] {
  const inner = new Content();
  let j = i;
  for (; j < lines.length; j++) {
    const line = lines[j] as string;
    const m = QUOTE.exec(line);
    if (m) inner.add(line.slice(m[0].length));
    else if (inner.continues(line)) inner.add(line, true);
    else break;
  }
  return [{ type: 'blockquote', children: nested(inner.lines).blocks }, j];
}

/** The marker character: `-`/`+`/`*`, or `.`/`)` after a number. A different one starts a new list. */
const kind = (m: RegExpExecArray) => m[2] ?? m[4];

function sibling(line: string, of: string): RegExpExecArray | null {
  const m = LIST.exec(line);
  return m && kind(m) === of && !RULE.test(line) ? m : null;
}

function list(lines: Lines, i: number, first: RegExpExecArray): [Block, number] {
  const items: Item[] = [];
  let loose = false;
  let m: RegExpExecArray | null = first;
  while (m) {
    const [item, next, itemLoose] = listItem(lines, i, m);
    items.push(item);
    loose ||= itemLoose;
    i = next;
    let j = i;
    while (j < lines.length && blank(lines[j] as string)) j++;
    m = j < lines.length ? sibling(lines[j] as string, kind(first) as string) : null;
    if (m) {
      loose ||= j > i;
      i = j;
    }
  }
  const ordered = first[3] !== undefined;
  const start = ordered ? Number(first[3]) : 1;
  return [{ type: 'list', ordered, start, tight: !loose, items }, i];
}

function listItem(lines: Lines, i: number, m: RegExpExecArray): [Item, number, boolean] {
  const line = lines[i] as string;
  const markerEnd = (m[0] as string).length - (m[5]?.length ?? 0);
  const spaces = m[5]?.length ?? 0;
  const empty = blank(line.slice(markerEnd));
  // Content starts after the marker's spaces; more than 4 means indented code, so only 1 counts.
  const width = markerEnd + (empty || spaces > 4 ? 1 : spaces);
  // Indenting by the content column continues the item, and 4 always does.
  const cont = Math.min(width, 4);
  let head = line.slice(width);
  const task = TASK.exec(head);
  if (task) head = head.slice(task[0].length);
  const inner = new Content();
  inner.add(head);
  let j = i + 1;
  for (; j < lines.length; j++) {
    const l = lines[j] as string;
    if (blank(l)) inner.add('');
    else if (indent(l) >= cont) inner.add(l.slice(cont));
    else if (!LIST.test(l) && inner.continues(l)) inner.add(l, true);
    else break;
  }
  while (inner.lines.length > 1 && blank(inner.lines.at(-1) as string)) {
    inner.lines.pop();
    j--;
  }
  const { blocks, loose } = nested(inner.lines);
  const checked = task ? task[1] !== ' ' : null;
  return [{ type: 'item', checked, children: blocks }, j, loose];
}
