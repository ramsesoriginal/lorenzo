// Inline pass (ADR 0100, 0102): one left-to-right scan, stacks for links and
// `{{.class …}}` spans, and CommonMark's delimiter-run algorithm for emphasis.
import type { Attrs, Inline, Span } from './ast';

type Delim = { type: 'delim'; ch: string; n: number; orig: number; open: boolean; close: boolean };
/** A `{#id .class}` waiting to attach to the element before it (see `literal`). */
type Pending = { type: 'attrs'; attrs: Attrs; raw: string };
type Node = Inline | Delim | Pending;
type Parent = Extract<Inline, { children: Inline[] }>;
type Opener = { at: number; image: boolean; active: boolean };
type SpanOpener = { at: number; attrs: Attrs };

/** What a matched run of each delimiter character becomes, by how many characters it uses. */
const DELIMS: Record<string, { tags: Span[]; strict?: boolean; exact?: boolean }> = {
  '*': { tags: ['em', 'strong'] },
  // `_` never opens or closes inside a word, so `snake_case` stays literal.
  _: { tags: ['i', 'b'], strict: true },
  // These pair only with a run of the same length: ~sub~, ~~del~~, ^sup^.
  '~': { tags: ['sub', 'del'], exact: true },
  '^': { tags: ['sup'], exact: true },
};

const PUNCT = /[!-/:-@[-`{-~]/;
const SPACE = /\s/;
const PUNCT_ANY = /[\p{P}\p{S}]/u;
const AUTOLINK = /^<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*)>/;
const EMAIL =
  /^<([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)>/;
const FOOTNOTE_REF = /^\[\^([^\]\s][^\]]*)\]/;

/** `#id` and `.class` tokens, the one attribute syntax every `{…}` and `{{…}}` shares. */
export const ATTR_LIST = String.raw`[.#][A-Za-z][\w-]*(?:[ \t]+[.#][A-Za-z][\w-]*)*`;
const ATTRS = new RegExp(String.raw`^\{[ \t]*(${ATTR_LIST})[ \t]*\}`);
const SPAN_OPEN = new RegExp(String.raw`^\{\{(${ATTR_LIST})(?:[ \t]+|(?=\}\}))`);

export function attributes(list: string): Attrs {
  const attrs: Attrs = { id: '', classes: [] };
  for (const token of list.split(/[ \t]+/).filter(Boolean)) {
    if (token.startsWith('#')) attrs.id = token.slice(1);
    else attrs.classes.push(token.slice(1));
  }
  return attrs;
}

const unescapePunct = (s: string) => s.replace(/\\([!-/:-@[-`{-~])/g, '$1');

/** Footnote labels match like CommonMark link labels. */
export const normalizeLabel = (label: string) => label.trim().replace(/\s+/g, ' ').toLowerCase();

/** Heading ids, and stage 3's `[[wikilink]]` slugs: ASCII, lowercase, hyphenated. */
export const slugify = (s: string) =>
  s
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

/** Plain text of inline content, e.g. for an image's alt or a heading's slug. */
export const plainText = (nodes: Inline[]): string =>
  nodes
    .map((n) =>
      'children' in n
        ? plainText(n.children)
        : 'text' in n
          ? n.text
          : 'tex' in n
            ? n.tex
            : n.type === 'break'
              ? ' '
              : '',
    )
    .join('');

/**
 * Blocks and inline elements each nest at most this deep; anything deeper stays text.
 * Everything that walks the tree recurses, so this bounds the stack, and parse time with it.
 */
export const MAX_NESTING = 32;

const DEPTH = new WeakMap<Inline, number>();
const depthOf = (nodes: Inline[]) => nodes.reduce((d, n) => Math.max(d, DEPTH.get(n) ?? 0), 0);
const nest = (node: Parent) => {
  DEPTH.set(node, depthOf(node.children) + 1);
  return node;
};
const textNode = (s: string): Inline => ({ type: 'text', text: s });

export function parseInline(src: string): Inline[] {
  const nodes: Node[] = [];
  const brackets: Opener[] = [];
  const spans: SpanOpener[] = [];
  let text = '';
  const flush = () => {
    if (text) nodes.push(textNode(text));
    text = '';
  };
  const push = (node: Node) => {
    flush();
    nodes.push(node);
  };
  /** Replaces the opener's placeholder at `at` with `make(everything after it)`, unless too deep. */
  const close = (at: number, make: (children: Inline[]) => Parent, closing: string) => {
    flush();
    const children = literal(resolveEmphasis(nodes.splice(at + 1)));
    // Openers of either kind left open inside can no longer close.
    while ((brackets.at(-1)?.at ?? -1) > at) brackets.pop();
    while ((spans.at(-1)?.at ?? -1) > at) spans.pop();
    if (depthOf(children) >= MAX_NESTING) {
      nodes.push(...children, textNode(closing));
      return false;
    }
    nodes[at] = nest(make(children));
    return true;
  };

  let i = 0;
  while (i < src.length) {
    const c = src[i] as string;
    const next = src[i + 1] ?? '';

    if (c === '\\' && (next === '\n' || PUNCT.test(next))) {
      if (next === '\n') push({ type: 'break' });
      else text += next;
      i += 2;
    } else if (c === '\n') {
      const hard = / {2,}$/.test(text);
      text = text.replace(/ +$/, '');
      push(hard ? { type: 'break' } : textNode('\n'));
      i++;
    } else if (c === '`') {
      const run = /^`+/.exec(src.slice(i))?.[0] as string;
      const end = closingRun(src, i + run.length, run.length);
      if (end < 0) text += run;
      else push({ type: 'codespan', text: codeText(src.slice(i + run.length, end)) });
      i = end < 0 ? i + run.length : end + run.length;
    } else if (c in DELIMS) {
      const start = i;
      while (src[i] === c) i++;
      push(delim(c, i - start, src[start - 1] ?? '\n', src[i] ?? '\n'));
    } else if (c === '[' || (c === '!' && next === '[')) {
      const ref = c === '[' ? FOOTNOTE_REF.exec(src.slice(i)) : null;
      if (ref) {
        push({ type: 'footnote', label: ref[1] as string });
        i += ref[0].length;
        continue;
      }
      const image = c === '!';
      flush();
      brackets.push({ at: nodes.length, image, active: true });
      nodes.push(textNode(image ? '![' : '['));
      i += image ? 2 : 1;
    } else if (c === ']') {
      const bracket = brackets.pop();
      const dest = bracket?.active ? destination(src, i + 1) : null;
      if (!bracket || !dest) {
        text += ']';
        i++;
        continue;
      }
      const type = bracket.image ? 'image' : 'link';
      const { url, title } = dest;
      const linked = close(
        bracket.at,
        (children) => ({ type, url, title, children }),
        src.slice(i, dest.end),
      );
      // No links inside links: every earlier `[` can no longer become one.
      if (linked && !bracket.image) for (const b of brackets) if (!b.image) b.active = false;
      i = dest.end;
    } else if (c === '{' && next === '{') {
      const m = SPAN_OPEN.exec(src.slice(i));
      if (m) {
        flush();
        spans.push({ at: nodes.length, attrs: attributes(m[1] as string) });
        nodes.push(textNode(m[0]));
      } else text += '{{';
      i += m ? m[0].length : 2;
    } else if (c === '}' && next === '}' && spans.length) {
      const { at, attrs } = spans.pop() as SpanOpener;
      close(at, (children) => ({ type: 'span', attrs, children }), '}}');
      i += 2;
    } else {
      const token =
        c === '<'
          ? autolink(src.slice(i))
          : c === '$'
            ? math(src, i)
            : c === '{'
              ? pending(src.slice(i))
              : null;
      if (token) push(token.node);
      else text += c;
      i += token ? token.length : 1;
    }
  }
  flush();
  return literal(resolveEmphasis(nodes));
}

type Token = { node: Node; length: number } | null;

/** `<https://…>` or `<name@host>` at the start of `s`. */
function autolink(s: string): Token {
  const url = AUTOLINK.exec(s);
  const m = url ?? EMAIL.exec(s);
  if (!m) return null;
  const label = m[1] as string;
  const node: Inline = {
    type: 'link',
    url: url ? label : `mailto:${label}`,
    title: '',
    children: [textNode(label)],
  };
  return { node, length: m[0].length };
}

/**
 * `$…$` or `$$…$$` at `src[i]`. As in Pandoc, inline math can't start or end with a
 * space or be followed by a digit, so `$5 and $10` stays text.
 */
function math(src: string, i: number): Token {
  const display = src[i + 1] === '$';
  const fence = display ? '$$' : '$';
  const start = i + fence.length;
  let k = start;
  while (k < src.length && !src.startsWith(fence, k)) k += src[k] === '\\' ? 2 : 1;
  const tex = src.slice(start, k);
  if (k >= src.length || !tex.trim()) return null;
  if (!display && (/^\s|\s$/.test(tex) || /\d/.test(src[k + 1] ?? ''))) return null;
  return { node: { type: 'math', display, tex: tex.trim() }, length: k + fence.length - i };
}

function pending(s: string): Token {
  const m = ATTRS.exec(s);
  return (
    m && {
      node: { type: 'attrs', attrs: attributes(m[1] as string), raw: m[0] },
      length: m[0].length,
    }
  );
}

/** Index of the next backtick run of exactly `length`, or -1. */
function closingRun(src: string, from: number, length: number): number {
  const re = /`+/g;
  re.lastIndex = from;
  for (let m = re.exec(src); m; m = re.exec(src)) if (m[0].length === length) return m.index;
  return -1;
}

function codeText(raw: string): string {
  const s = raw.replace(/\n/g, ' ');
  return /^ .*[^ ].* $/.test(s) ? s.slice(1, -1) : s;
}

function delim(ch: string, n: number, before: string, after: string): Delim {
  const ws = (s: string) => SPACE.test(s);
  const pn = (s: string) => PUNCT_ANY.test(s);
  const left = !ws(after) && (!pn(after) || ws(before) || pn(before));
  const right = !ws(before) && (!pn(before) || ws(after) || pn(after));
  const strict = DELIMS[ch]?.strict;
  const open = strict ? left && (!right || pn(before)) : left;
  const close = strict ? right && (!left || pn(after)) : right;
  return { type: 'delim', ch, n, orig: n, open, close };
}

type Destination = { url: string; title: string; end: number };

/** `(url "title")` starting at `src[j]`, or null if it isn't one. */
function destination(src: string, j: number): Destination | null {
  if (src[j] !== '(') return null;
  let k = skipSpace(src, j + 1);
  let url: string;
  if (src[k] === '<') {
    const end = src.indexOf('>', k);
    if (end < 0 || /[\n<]/.test(src.slice(k + 1, end))) return null;
    url = src.slice(k + 1, end);
    k = end + 1;
  } else {
    const start = k;
    for (let depth = 0; k < src.length; k++) {
      const ch = src[k] as string;
      if (ch === '\\' && PUNCT.test(src[k + 1] ?? '')) k++;
      else if (SPACE.test(ch) || (ch === ')' && depth === 0)) break;
      else if (ch === '(') depth++;
      else if (ch === ')') depth--;
    }
    url = src.slice(start, k);
  }
  const afterUrl = k;
  k = skipSpace(src, k);
  let title = '';
  const quote = src[k];
  if (k > afterUrl && (quote === '"' || quote === "'" || quote === '(')) {
    const close = quote === '(' ? ')' : quote;
    let end = k + 1;
    while (end < src.length && src[end] !== close) end += src[end] === '\\' ? 2 : 1;
    if (end >= src.length) return null;
    title = src.slice(k + 1, end);
    k = skipSpace(src, end + 1);
  }
  if (src[k] !== ')') return null;
  return { url: unescapePunct(url), title: unescapePunct(title), end: k + 1 };
}

const skipSpace = (src: string, k: number) => {
  while (k < src.length && SPACE.test(src[k] as string)) k++;
  return k;
};

/** CommonMark's "rule of 3": runs that can both open and close don't pair up unevenly. */
function oddMatch(opener: Delim, closer: Delim): boolean {
  return (
    (opener.close || closer.open) &&
    (opener.orig + closer.orig) % 3 === 0 &&
    !(opener.orig % 3 === 0 && closer.orig % 3 === 0)
  );
}

const SPACELESS = new Set<Span>(['sub', 'sup']);
const hasSpace = (n: Node) =>
  n.type === 'break' || (n.type !== 'delim' && n.type !== 'attrs' && SPACE.test(plainText([n])));

function opens(node: Node | undefined, closer: Delim): node is Delim {
  if (node?.type !== 'delim' || node.ch !== closer.ch || !node.open) return false;
  const rule = DELIMS[closer.ch];
  return rule?.exact
    ? node.n === closer.n && closer.n <= rule.tags.length
    : !oddMatch(node, closer);
}

/**
 * Pairs delimiter runs into spans. Output is built as a stack, so matching only ever
 * cuts its tail, and `bottom` (CommonMark's "openers bottom") keeps a closer from
 * rescanning openers already known not to fit: linear time, not quadratic.
 */
function resolveEmphasis(nodes: Node[]): Node[] {
  const out: Node[] = [];
  const bottom = new Map<string, number>();
  for (const closer of nodes) {
    if (closer.type !== 'delim' || !closer.close) {
      out.push(closer);
      continue;
    }
    const key = `${closer.ch}${closer.open}${closer.orig % 3}`;
    while (closer.n > 0) {
      const floor = Math.min(bottom.get(key) ?? 0, out.length);
      let o = out.length - 1;
      while (o >= floor && !opens(out[o], closer)) o--;
      const opener = out[o];
      const tags = DELIMS[closer.ch]?.tags ?? [];
      const use = opener?.type === 'delim' ? Math.min(opener.n, closer.n, tags.length) : 0;
      // As in Pandoc, sub- and superscripts hold no spaces, so `x^2 + y^2` stays text.
      // Any opener further back would span the same space, so none can match either.
      const spaced = SPACELESS.has(tags[use - 1] as Span) && out.slice(o + 1).some(hasSpace);
      if (o < floor || opener?.type !== 'delim' || spaced) {
        bottom.set(key, out.length);
        break;
      }
      opener.n -= use;
      closer.n -= use;
      const children = literal(out.splice(o + 1));
      if (!opener.n) out.pop();
      if (depthOf(children) < MAX_NESTING)
        out.push(nest({ type: tags[use - 1] as Span, children }));
      else out.push(textNode(closer.ch.repeat(use)), ...children, textNode(closer.ch.repeat(use)));
    }
    if (closer.n > 0) out.push(closer);
  }
  return out;
}

/**
 * Unmatched delimiters become text, a pending `{…}` attaches to the element right
 * before it (or becomes its text), and neighbouring text merges.
 */
function literal(nodes: Node[]): Inline[] {
  const out: Inline[] = [];
  for (const n of nodes) {
    const last = out.at(-1);
    if (
      n.type === 'attrs' &&
      last &&
      last.type !== 'text' &&
      last.type !== 'break' &&
      last.type !== 'footnote' &&
      !last.attrs
    ) {
      last.attrs = n.attrs;
      continue;
    }
    const node: Inline =
      n.type === 'delim' ? textNode(n.ch.repeat(n.n)) : n.type === 'attrs' ? textNode(n.raw) : n;
    if (node.type === 'text' && last?.type === 'text') last.text += node.text;
    else out.push(node.type === 'text' ? { ...node } : node);
  }
  return out;
}
