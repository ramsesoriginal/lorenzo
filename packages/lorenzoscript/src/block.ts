// Block pass (ADR 0100, 0102): containers collect their lines, strip their marker
// or indent, and recurse. Paragraph text is handed to the inline pass.
import type { Abbreviation, Align, Block, Document, Footnote, Inline, Item } from './ast';
import {
  ATTR_LIST,
  attributes,
  MAX_NESTING,
  normalizeLabel,
  parseInline,
  plainText,
  slugify,
} from './inline';

type Lines = string[];
type Rule = {
  start: (lines: Lines, i: number) => RegExpExecArray | null;
  /** Whether a line starting this block may end a paragraph. */
  interrupts: (m: RegExpExecArray) => boolean;
  /** The block, or null for a definition, which is recorded on the document instead. */
  parse: (lines: Lines, i: number, m: RegExpExecArray) => [Block | null, number];
};

const FENCE = /^( {0,3})(`{3,}(?=[^`]*$)|~{3,})(.*)$/;
const HEADING = /^ {0,3}(#{1,6})(?=[ \t]|$)(.*)$/;
const RULE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const QUOTE = /^ {0,3}> ?/;
const LIST = /^( {0,3})(?:([-+*])|(\d{1,9})([.)]))([ \t]+|$)/;
const TASK = /^\[([ xX])\](?:[ \t]+|$)/;
/** `$$` alone opens a math block; `$$…$$` alone on a line is a whole one. */
const MATH = /^ {0,3}\$\$(?:[ \t]*|((?:(?!\$\$).)+)\$\$[ \t]*)$/;
const MATH_CLOSE = /^ {0,3}\$\$[ \t]*$/;
const TOC = /^ {0,3}\{\{toc\}\}[ \t]*$/i;
const DIV_OPEN = new RegExp(String.raw`^ {0,3}\{\{(${ATTR_LIST})[ \t]*$`);
const DIV_CLOSE = /^ {0,3}\}\}[ \t]*$/;
const FOOTNOTE = /^ {0,3}\[\^([^\]]+)\]:[ \t]*(.*)$/;
const ABBREVIATION = /^ {0,3}\*\[([^\]]+)\]:[ \t]*(.*)$/;
const TABLE_DELIM = /^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/;
const TRAILING_ATTRS = new RegExp(String.raw`(?:^|[ \t]+)\{[ \t]*(${ATTR_LIST})[ \t]*\}$`);

const blank = (line: string) => line.trim() === '';
const indent = (line: string) => line.length - line.trimStart().length;
const always = () => true;
const on = (re: RegExp) => (lines: Lines, i: number) => re.exec(lines[i] as string);

/** Footnote and abbreviation definitions, by label and term, collected during one `parse`. */
let footnotes = new Map<string, Footnote>();
let abbreviations = new Map<string, Abbreviation>();

export function parse(source: string): Document {
  const text = source.replace(/\r\n?/g, '\n').replace(/\0/g, String.fromCharCode(0xfffd));
  // A final newline ends the last line; it doesn't start another one.
  const lines = text.replace(/\n$/, '').split('\n').map(expandTabs);
  footnotes = new Map();
  abbreviations = new Map();
  const children = parseBlocks(lines).blocks;
  const doc: Document = {
    children,
    footnotes: [...footnotes.values()],
    abbreviations: [...abbreviations.values()],
  };
  assignIds(doc);
  return doc;
}

/** Every heading gets an id: its explicit one, else a de-duplicated slug of its text. */
function assignIds(doc: Document): void {
  const used = new Set<string>();
  /** Per slug, the last suffix tried, so a thousand equal headings don't retry -2, -3, …. */
  const suffix = new Map<string, number>();
  for (const heading of allBlocks(doc, true)) {
    if (heading.type !== 'heading') continue;
    if (!heading.attrs.id) {
      const base = slugify(plainText(heading.children)) || 'section';
      let id = base;
      let k = suffix.get(base) ?? 1;
      while (used.has(id)) id = `${base}-${++k}`;
      suffix.set(base, k);
      heading.attrs.id = id;
    }
    used.add(heading.attrs.id);
  }
}

/**
 * Every block in document order, at any depth; with `footnotes`, theirs follow. The one walk
 * that heading ids, `{{TOC}}`, and `references()` share, so they can't disagree.
 */
export function* allBlocks(doc: Document, footnotes = false): Generator<Block> {
  const walk = function* (blocks: Block[]): Generator<Block> {
    for (const b of blocks) {
      yield b;
      if (b.type === 'blockquote' || b.type === 'div') yield* walk(b.children);
      else if (b.type === 'list') for (const item of b.items) yield* walk(item.children);
    }
  };
  yield* walk(doc.children);
  if (footnotes) for (const f of doc.footnotes) yield* walk(f.children);
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
    if (blank(lines[i] as string)) {
      gap = blocks.length > 0;
      i++;
      continue;
    }
    loose ||= gap;
    gap = false;
    const found = match(lines, i);
    const [block, next] = found ? found[0].parse(lines, i, found[1]) : paragraph(lines, i);
    if (block) blocks.push(block);
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
  { start: on(/^ {4}/), interrupts: () => false, parse: indentedCode },
  { start: on(FENCE), interrupts: always, parse: fencedCode },
  { start: on(MATH), interrupts: always, parse: mathBlock },
  { start: on(HEADING), interrupts: always, parse: heading },
  { start: on(RULE), interrupts: always, parse: (_, i) => [{ type: 'rule' }, i + 1] },
  { start: on(QUOTE), interrupts: always, parse: blockquote },
  { start: on(TOC), interrupts: always, parse: (_, i) => [{ type: 'toc' }, i + 1] },
  { start: on(DIV_OPEN), interrupts: always, parse: div },
  { start: on(FOOTNOTE), interrupts: always, parse: footnote },
  { start: on(ABBREVIATION), interrupts: always, parse: abbreviation },
  {
    start: on(LIST),
    // Only a non-empty item, and only an ordered one starting at 1, may end a paragraph.
    interrupts: (m) =>
      !blank(m.input.slice(m[0].length)) && (m[3] === undefined || Number(m[3]) === 1),
    parse: list,
  },
  { start: tableStart, interrupts: always, parse: table },
];

function match(lines: Lines, i: number): [Rule, RegExpExecArray] | undefined {
  for (const rule of RULES) {
    const m = rule.start(lines, i);
    if (m) return [rule, m];
  }
}

function interrupts(lines: Lines, i: number): boolean {
  const found = match(lines, i);
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
    this.open = !this.fenced && !blank(text) && !match([text], 0);
  }

  continues(line: string): boolean {
    return this.open && !blank(line) && !interrupts([line], 0);
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
  while (j < lines.length && !blank(lines[j] as string) && !interrupts(lines, j)) j++;
  const text = lines
    .slice(i, j)
    .map((l) => l.trimStart())
    .join('\n')
    .trimEnd();
  return [{ type: 'paragraph', children: parseInline(text) }, j];
}

/** A trailing `{#id .class}` split off `text`. */
function trailingAttrs(text: string) {
  const m = TRAILING_ATTRS.exec(text);
  return { rest: m ? text.slice(0, m.index) : text, attrs: attributes(m?.[1] ?? '') };
}

function heading(_: Lines, i: number, m: RegExpExecArray): [Block, number] {
  const text = (m[2] as string)
    .trim()
    .replace(/(^|[ \t])#+$/, '')
    .trim();
  const { rest, attrs } = trailingAttrs(text);
  const level = (m[1] as string).length;
  return [{ type: 'heading', level, attrs, children: parseInline(rest) }, i + 1];
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
  const { rest, attrs } = trailingAttrs(info.trim());
  const lang = rest.split(/\s+/)[0] as string;
  const code: Block = { type: 'code', lang, text };
  if (attrs.id || attrs.classes.length) code.attrs = attrs;
  return [code, j + 1];
}

function mathBlock(lines: Lines, i: number, m: RegExpExecArray): [Block, number] {
  if (m[1] !== undefined) return [{ type: 'math', display: true, tex: m[1].trim() }, i + 1];
  const body: Lines = [];
  let j = i + 1;
  for (; j < lines.length && !MATH_CLOSE.test(lines[j] as string); j++)
    body.push(lines[j] as string);
  return [{ type: 'math', display: true, tex: body.join('\n').trim() }, j + 1];
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

/** `{{.class` … `}}`; nested class blocks inside are counted, so their `}}` isn't this one's. */
function div(lines: Lines, i: number, m: RegExpExecArray): [Block, number] {
  const inner: Lines = [];
  let open = 1;
  let j = i + 1;
  for (; j < lines.length; j++) {
    const line = lines[j] as string;
    if (DIV_OPEN.test(line)) open++;
    else if (DIV_CLOSE.test(line) && --open === 0) break;
    inner.push(line);
  }
  const attrs = attributes(m[1] as string);
  return [{ type: 'div', attrs, children: nested(inner).blocks }, j + 1];
}

function footnote(lines: Lines, i: number, m: RegExpExecArray): [null, number] {
  const [inner, j] = collect(lines, i, m[2] as string, 4);
  const label = normalizeLabel(m[1] as string);
  if (!footnotes.has(label)) footnotes.set(label, { label, children: nested(inner).blocks });
  return [null, j];
}

function abbreviation(_: Lines, i: number, m: RegExpExecArray): [null, number] {
  const term = (m[1] as string).trim();
  const title = (m[2] as string).trim();
  if (term && title && !abbreviations.has(term)) abbreviations.set(term, { term, title });
  return [null, i + 1];
}

/** A table row's cells: outer pipes dropped, split on unescaped `|`, `\|` kept as `|`. */
function cells(line: string): string[] {
  let row = line.trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1);
  return row.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'));
}

/** A header row directly above a delimiter row with as many cells starts a table. */
function tableStart(lines: Lines, i: number): RegExpExecArray | null {
  const delimiters = lines[i + 1];
  if (delimiters === undefined || !delimiters.includes('|') || !TABLE_DELIM.test(delimiters)) {
    return null;
  }
  const header = lines[i] as string;
  return cells(header).length === cells(delimiters).length ? /^/.exec(header) : null;
}

function table(lines: Lines, i: number): [Block, number] {
  const head = cells(lines[i] as string);
  const align = cells(lines[i + 1] as string).map((c): Align => {
    if (c.startsWith(':')) return c.endsWith(':') ? 'center' : 'left';
    return c.endsWith(':') ? 'right' : null;
  });
  const rows: Inline[][][] = [];
  let j = i + 2;
  for (; j < lines.length && !blank(lines[j] as string) && !interrupts(lines, j); j++) {
    const row = cells(lines[j] as string);
    rows.push(head.map((_, k) => parseInline(row[k] ?? '')));
  }
  return [{ type: 'table', align, head: head.map((c) => parseInline(c)), rows }, j];
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
  let head = line.slice(width);
  const task = TASK.exec(head);
  if (task) head = head.slice(task[0].length);
  // Indenting by the content column continues the item, and 4 always does.
  const [inner, j] = collect(lines, i, head, Math.min(width, 4));
  const { blocks, loose } = nested(inner);
  const checked = task ? task[1] !== ' ' : null;
  return [{ type: 'item', checked, children: blocks }, j, loose];
}

/**
 * A list item's or footnote's content: the text after its marker, then every line that is
 * blank, indented by `cont`, or lazily continues a paragraph. Trailing blank lines aren't its.
 */
function collect(lines: Lines, i: number, head: string, cont: number): [Lines, number] {
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
  return [inner.lines, j];
}
