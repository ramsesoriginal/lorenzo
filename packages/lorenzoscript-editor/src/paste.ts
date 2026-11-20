// Paste from Word, Google Docs or a web page (ADR 0512): the clipboard's HTML becomes
// LorenzoScript, so headings, emphasis, lists, links and quotations survive, and the styles,
// fonts and classes an office program adds do not. Opt-in: `pasteFromWord` on the editor.

const BLOCKS = new Set([
  'P',
  'DIV',
  'H1',
  'H2',
  'H3',
  'H4',
  'H5',
  'H6',
  'UL',
  'OL',
  'LI',
  'BLOCKQUOTE',
  'TABLE',
  'TR',
  'PRE',
]);

/** Whether the pasted HTML says more than plain text would (it has structure or emphasis). */
export function worthConverting(html: string): boolean {
  return /<(h[1-6]|ul|ol|li|strong|b|em|i|a|blockquote)[\s>]/i.test(html);
}

/** A node of the small tree the reader builds; text is a node with `text`. */
type Node = { tag: string; attrs: Record<string, string>; children: Node[]; text?: string };

const VOID = new Set(['br', 'hr', 'img', 'meta', 'link', 'input', 'col', 'wbr']);
const SKIP = new Set(['script', 'style', 'head', 'title', 'iframe', 'object', 'embed']);
const ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
  ndash: '–',
  mdash: '—',
  hellip: '…',
  lsquo: '‘',
  rsquo: '’',
  ldquo: '“',
  rdquo: '”',
};

function decode(text: string): string {
  let out = '';
  for (let i = 0; i < text.length; i++) {
    const c = text[i] as string;
    if (c !== '&') {
      out += c;
      continue;
    }
    const end = text.indexOf(';', i);
    const name = end > i && end - i <= 10 ? text.slice(i + 1, end) : '';
    let value: string | undefined = name ? ENTITIES[name] : undefined;
    if (name[0] === '#') {
      const code =
        name[1] === 'x' || name[1] === 'X'
          ? Number.parseInt(name.slice(2), 16)
          : Number(name.slice(1));
      if (Number.isInteger(code) && code > 0 && code < 0x110000) value = String.fromCodePoint(code);
    }
    if (value === undefined) out += c;
    else {
      out += value;
      i = end;
    }
  }
  return out;
}

/** The attributes of a tag's inside text, read one by one; only `href` and `style` are kept. */
function attributes(inside: string): Record<string, string> {
  const found: Record<string, string> = {};
  let i = 0;
  while (i < inside.length) {
    while (i < inside.length && /[\s/]/.test(inside[i] as string)) i++;
    let nameEnd = i;
    while (nameEnd < inside.length && !/[\s=/]/.test(inside[nameEnd] as string)) nameEnd++;
    const name = inside.slice(i, nameEnd).toLowerCase();
    i = nameEnd;
    while (i < inside.length && inside[i] === ' ') i++;
    let value = '';
    if (inside[i] === '=') {
      i++;
      while (i < inside.length && inside[i] === ' ') i++;
      const quote = inside[i];
      if (quote === '"' || quote === "'") {
        const close = inside.indexOf(quote, i + 1);
        const stop = close < 0 ? inside.length : close;
        value = inside.slice(i + 1, stop);
        i = stop + 1;
      } else {
        let stop = i;
        while (stop < inside.length && !/\s/.test(inside[stop] as string)) stop++;
        value = inside.slice(i, stop);
        i = stop;
      }
    }
    if ((name === 'href' || name === 'style') && !(name in found)) found[name] = decode(value);
    if (i === nameEnd && !name) i++;
  }
  return found;
}

/**
 * The clipboard's HTML as a small tree, by one pass over the text: no DOM, no scripting, no
 * pattern run over the whole input. Scripts, styles and other embedded content are skipped whole;
 * comments are dropped; an unclosed tag ends with the text.
 */
export function readHtml(html: string): Node {
  const root: Node = { tag: '#root', attrs: {}, children: [] };
  const stack: Node[] = [root];
  const lower = html.toLowerCase();
  let i = 0;
  const top = () => stack[stack.length - 1] as Node;
  const addText = (text: string) => {
    if (text) top().children.push({ tag: '#text', attrs: {}, children: [], text: decode(text) });
  };
  while (i < html.length) {
    const open = html.indexOf('<', i);
    if (open < 0) {
      addText(html.slice(i));
      break;
    }
    addText(html.slice(i, open));
    if (html.startsWith('<!--', open)) {
      const end = html.indexOf('-->', open + 4);
      i = end < 0 ? html.length : end + 3;
      continue;
    }
    const close = html.indexOf('>', open);
    if (close < 0) break;
    const inside = html.slice(open + 1, close);
    i = close + 1;
    const closing = inside[0] === '/';
    let nameEnd = closing ? 1 : 0;
    while (nameEnd < inside.length && !/[\s/]/.test(inside[nameEnd] as string)) nameEnd++;
    const tag = inside.slice(closing ? 1 : 0, nameEnd).toLowerCase();
    if (!tag || tag[0] === '!' || tag[0] === '?') continue;
    if (closing) {
      for (let k = stack.length - 1; k > 0; k--) {
        if ((stack[k] as Node).tag === tag) {
          stack.length = k;
          break;
        }
      }
      continue;
    }
    if (SKIP.has(tag)) {
      const end = lower.indexOf(`</${tag}`, i);
      const after = end < 0 ? -1 : html.indexOf('>', end);
      i = after < 0 ? html.length : after + 1;
      continue;
    }
    const node: Node = { tag, attrs: attributes(inside.slice(nameEnd)), children: [] };
    top().children.push(node);
    if (!VOID.has(tag) && !inside.endsWith('/')) stack.push(node);
  }
  return root;
}

/** The LorenzoScript for a clipboard's HTML. */
export function htmlToScript(html: string): string {
  const out = walk(readHtml(html), { list: [] });
  return out
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/\n\n +(?=\S)/g, '\n\n')
    .trim();
}

type Context = { list: ('ul' | 'ol')[] };

function inline(node: Node, context: Context): string {
  let text = '';
  for (const child of node.children) text += walk(child, context);
  return text;
}

/** All the text under a node. */
const text = (node: Node): string => node.text ?? node.children.map(text).join('');

const wrap = (mark: string, text: string) => {
  const inner = text.trim();
  if (!inner) return text;
  const lead = text.slice(0, text.length - text.trimStart().length);
  const trail = text.slice(text.trimEnd().length);
  return `${lead}${mark}${inner}${mark}${trail}`;
};

function walk(node: Node, context: Context): string {
  if (node.text !== undefined) return node.text.replace(/\s+/g, ' ');
  const el = node;
  const tag = el.tag.toUpperCase();
  const style = el.attrs.style ?? '';
  if (tag === 'BR') return '\n';
  if (tag === 'STRONG' || tag === 'B') return wrap('**', inline(el, context));
  if (tag === 'EM' || tag === 'I') return wrap('*', inline(el, context));
  if (tag === 'DEL' || tag === 'S' || tag === 'STRIKE') return wrap('~~', inline(el, context));
  if (tag === 'CODE') return `\`${text(el)}\``;
  if (tag === 'A') {
    const href = el.attrs.href ?? '';
    const label = inline(el, context).trim();
    return href && label && /^(https?:|mailto:)/i.test(href) ? `[${label}](${href})` : label;
  }
  if (tag === 'SPAN') {
    // Word and Google Docs say bold and italic in a span's style.
    let text = inline(el, context);
    if (/font-weight:\s*(bold|[6-9]00)/i.test(style)) text = wrap('**', text);
    if (/font-style:\s*italic/i.test(style)) text = wrap('*', text);
    return text;
  }
  if (/^H[1-6]$/.test(tag))
    return `\n\n${'#'.repeat(Number(tag[1]))} ${inline(el, context).trim()}\n\n`;
  if (tag === 'UL' || tag === 'OL') {
    const next = { list: [...context.list, tag.toLowerCase() as 'ul' | 'ol'] };
    let n = 0;
    let lines = '';
    for (const item of el.children) {
      if (item.tag !== 'li') continue;
      n++;
      const depth = context.list.length;
      const marker = tag === 'OL' ? `${n}.` : '-';
      const body = inline(item, next)
        .trim()
        .replace(/\n{2,}/g, '\n');
      lines += `${'  '.repeat(depth)}${marker} ${body}\n`;
    }
    return context.list.length ? `\n${lines.trimEnd()}` : `\n\n${lines}\n`;
  }
  if (tag === 'LI') return inline(el, context);
  if (tag === 'BLOCKQUOTE') {
    const quoted = inline(el, context)
      .trim()
      .split('\n')
      .map((line) => `> ${line}`.trimEnd())
      .join('\n');
    return `\n\n${quoted}\n\n`;
  }
  if (BLOCKS.has(tag)) {
    const text = inline(el, context).trim();
    return text ? `\n\n${text}\n\n` : '';
  }
  return inline(el, context);
}
