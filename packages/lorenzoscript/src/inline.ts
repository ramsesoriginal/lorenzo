// Inline pass (ADR 0100): one left-to-right scan, a bracket stack for links,
// and CommonMark's delimiter-run algorithm for emphasis.
import type { Inline, Span } from './ast';

type Delim = { type: 'delim'; ch: string; n: number; orig: number; open: boolean; close: boolean };
type Node = Inline | Delim;
type Bracket = { at: number; image: boolean; active: boolean };

/** What a matched run of each delimiter character becomes, by how many characters it uses. */
const DELIMS: Record<string, { tags: Span[]; strict: boolean }> = {
  '*': { tags: ['em', 'strong'], strict: false },
  // `_` never opens or closes inside a word, so `snake_case` stays literal.
  _: { tags: ['i', 'b'], strict: true },
};

const PUNCT = /[!-/:-@[-`{-~]/;
const SPACE = /\s/;
const PUNCT_ANY = /[\p{P}\p{S}]/u;
const AUTOLINK = /^<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*)>/;
const EMAIL =
  /^<([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)>/;

const unescapePunct = (s: string) => s.replace(/\\([!-/:-@[-`{-~])/g, '$1');

/**
 * Blocks and inline elements each nest at most this deep; anything deeper stays text.
 * Everything that walks the tree recurses, so this bounds the stack, and parse time with it.
 */
export const MAX_NESTING = 32;

const DEPTH = new WeakMap<Inline, number>();
const depthOf = (nodes: Inline[]) => nodes.reduce((d, n) => Math.max(d, DEPTH.get(n) ?? 0), 0);
const nest = (node: Inline & { children: Inline[] }) => {
  DEPTH.set(node, depthOf(node.children) + 1);
  return node;
};
const textNode = (s: string): Inline => ({ type: 'text', text: s });

export function parseInline(src: string): Inline[] {
  const nodes: Node[] = [];
  const brackets: Bracket[] = [];
  let text = '';
  const flush = () => {
    if (text) nodes.push({ type: 'text', text });
    text = '';
  };
  const push = (node: Node) => {
    flush();
    nodes.push(node);
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
      push(hard ? { type: 'break' } : { type: 'text', text: '\n' });
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
      const image = c === '!';
      flush();
      brackets.push({ at: nodes.length, image, active: true });
      nodes.push({ type: 'text', text: image ? '![' : '[' });
      i += image ? 2 : 1;
    } else if (c === ']') {
      const bracket = brackets.pop();
      const dest = bracket?.active ? destination(src, i + 1) : null;
      if (!bracket || !dest) {
        text += ']';
        i++;
        continue;
      }
      flush();
      // The opening bracket's text node stays at `bracket.at`, to be replaced by the link.
      const children = literal(resolveEmphasis(nodes.splice(bracket.at + 1)));
      if (depthOf(children) >= MAX_NESTING) {
        nodes.push(...children, textNode(src.slice(i, dest.end)));
      } else {
        const type = bracket.image ? 'image' : 'link';
        nodes[bracket.at] = nest({ type, url: dest.url, title: dest.title, children });
        // No links inside links: every earlier `[` can no longer become one.
        if (!bracket.image) for (const b of brackets) if (!b.image) b.active = false;
      }
      i = dest.end;
    } else {
      const auto = c === '<' ? autolink(src.slice(i)) : null;
      if (auto) push(auto.link);
      else text += c;
      i += auto ? auto.length : 1;
    }
  }
  flush();
  return literal(resolveEmphasis(nodes));
}

/** `<https://…>` or `<name@host>` at the start of `s`. */
function autolink(s: string): { link: Inline; length: number } | null {
  const url = AUTOLINK.exec(s);
  const m = url ?? EMAIL.exec(s);
  if (!m) return null;
  const label = m[1] as string;
  const children: Inline[] = [{ type: 'text', text: label }];
  const link: Inline = { type: 'link', url: url ? label : `mailto:${label}`, title: '', children };
  return { link, length: m[0].length };
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

const opens = (node: Node | undefined, closer: Delim): node is Delim =>
  node?.type === 'delim' && node.ch === closer.ch && node.open && !oddMatch(node, closer);

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
      if (o < floor || opener?.type !== 'delim') {
        bottom.set(key, out.length);
        break;
      }
      const tags = DELIMS[closer.ch]?.tags ?? [];
      const use = Math.min(opener.n, closer.n, tags.length);
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

/** Unmatched delimiters become text, and neighbouring text merges. */
function literal(nodes: Node[]): Inline[] {
  const out: Inline[] = [];
  for (const n of nodes) {
    const node: Inline = n.type === 'delim' ? textNode(n.ch.repeat(n.n)) : n;
    const last = out.at(-1);
    if (node.type === 'text' && last?.type === 'text') last.text += node.text;
    else out.push(node.type === 'text' ? { ...node } : node);
  }
  return out;
}
