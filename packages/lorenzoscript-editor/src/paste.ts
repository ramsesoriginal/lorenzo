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

/** The LorenzoScript for a clipboard's HTML. */
export function htmlToScript(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  for (const gone of doc.querySelectorAll('style,script,meta,link,head,title,o\\:p')) gone.remove();
  const out = walk(doc.body, { list: [] });
  return out
    .replace(/ /g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

type Context = { list: ('ul' | 'ol')[] };

function inline(node: Node, context: Context): string {
  let text = '';
  for (const child of node.childNodes) text += walk(child, context);
  return text;
}

const wrap = (mark: string, text: string) => {
  const inner = text.trim();
  if (!inner) return text;
  const lead = text.slice(0, text.length - text.trimStart().length);
  const trail = text.slice(text.trimEnd().length);
  return `${lead}${mark}${inner}${mark}${trail}`;
};

function walk(node: Node, context: Context): string {
  if (node.nodeType === 3) return (node.textContent ?? '').replace(/\s+/g, ' ');
  if (node.nodeType !== 1) return '';
  const el = node as Element;
  const tag = el.tagName;
  const style = el.getAttribute('style') ?? '';
  if (tag === 'BR') return '\n';
  if (tag === 'STRONG' || tag === 'B') return wrap('**', inline(el, context));
  if (tag === 'EM' || tag === 'I') return wrap('*', inline(el, context));
  if (tag === 'DEL' || tag === 'S' || tag === 'STRIKE') return wrap('~~', inline(el, context));
  if (tag === 'CODE') return `\`${el.textContent ?? ''}\``;
  if (tag === 'A') {
    const href = el.getAttribute('href') ?? '';
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
      if (item.tagName !== 'LI') continue;
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
