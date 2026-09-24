// HTML renderer (ADR 0100, 0102). Output is built only from the syntax tree, with
// every text and attribute escaped, so it is safe to assign to innerHTML.
// URL rules (RFC 0027 §5) are enforced here and nowhere else.
import type { Attrs, Block, Document, Inline, Item } from './ast';
import { headings } from './block';
import { attr, escapeHtml } from './html';
import { normalizeLabel, plainText } from './inline';
import { mathml } from './math';

export type RenderOptions = {
  /** Render `https` images. When false, every image renders as its alt text. Default true. */
  externalImages?: boolean;
};

const cr = (html: string) => (html.endsWith('\n') ? html : `${html}\n`);

/** Author ids always carry the `ls-` prefix, so they can't collide with the host page's. */
const attrsHtml = (a: Attrs | undefined, ...classes: string[]) =>
  attr('id', a?.id ? `ls-${a.id}` : '') +
  attr('class', [...classes, ...(a?.classes ?? [])].filter(Boolean).join(' '));

/** The URL to emit, or null if its scheme isn't allowed. */
const safeUrl = (url: string, schemes: RegExp) =>
  schemes.test(url) ? url.replace(/ /g, '%20') : null;
const LINK_SCHEMES = /^(?:https?|mailto):/i;
const IMAGE_SCHEMES = /^https:/i;

export function render(doc: Document, options: RenderOptions = {}): string {
  const footnotes = new Map(doc.footnotes.map((f) => [f.label, f.children]));
  /** Footnote numbers by label, assigned (and iterated) in order of first reference. */
  const numbers = new Map<string, number>();
  const refs = new Map<string, number>();
  const text = abbreviator(doc);

  const inlines = (nodes: Inline[]): string => nodes.map(inline).join('');

  function inline(n: Inline): string {
    switch (n.type) {
      case 'text':
        return text(n.text);
      case 'codespan':
        return `<code${attrsHtml(n.attrs)}>${escapeHtml(n.text)}</code>`;
      case 'break':
        return '<br>\n';
      case 'math':
        return math(n.tex, n.display, n.attrs);
      case 'footnote':
        return footnoteRef(n.label);
      case 'link': {
        // In-document fragments point at author ids, which always carry the prefix.
        const href = n.url.startsWith('#') ? `#ls-${n.url.slice(1)}` : safeUrl(n.url, LINK_SCHEMES);
        const body = inlines(n.children);
        return href === null
          ? body
          : `<a${attr('href', href)}${attr('title', n.title)}${attrsHtml(n.attrs)}>${body}</a>`;
      }
      case 'image': {
        const alt = plainText(n.children);
        const src = options.externalImages === false ? null : safeUrl(n.url, IMAGE_SCHEMES);
        return src === null
          ? escapeHtml(alt)
          : `<img${attr('src', src)} alt="${escapeHtml(alt)}"${attr('title', n.title)}${attrsHtml(n.attrs)}>`;
      }
      default:
        return `<${n.type}${attrsHtml(n.attrs)}>${inlines(n.children)}</${n.type}>`;
    }
  }

  const blocks = (list: Block[]): string => list.map(block).join('');

  function block(b: Block): string {
    switch (b.type) {
      case 'paragraph':
        return `<p>${inlines(b.children)}</p>\n`;
      case 'heading':
        return `<h${b.level}${attrsHtml(b.attrs)}>${inlines(b.children)}</h${b.level}>\n`;
      case 'blockquote':
        return `<blockquote>\n${blocks(b.children)}</blockquote>\n`;
      case 'code': {
        const lang = /^[\w+#.-]+$/.test(b.lang) ? `language-${b.lang}` : '';
        return `<pre${attrsHtml(b.attrs)}><code${attr('class', lang)}>${escapeHtml(b.text)}</code></pre>\n`;
      }
      case 'rule':
        return '<hr>\n';
      case 'list': {
        const tag = b.ordered ? 'ol' : 'ul';
        const start = b.ordered && b.start !== 1 ? ` start="${b.start}"` : '';
        return `<${tag}${start}>\n${b.items.map((it) => item(it, b.tight)).join('')}</${tag}>\n`;
      }
      case 'table': {
        const row = (tag: string, cells: Inline[][]) =>
          `<tr>\n${cells.map((c, k) => `<${tag}${attr('align', b.align[k] ?? '')}>${inlines(c)}</${tag}>\n`).join('')}</tr>\n`;
        const body = b.rows.length
          ? `<tbody>\n${b.rows.map((r) => row('td', r)).join('')}</tbody>\n`
          : '';
        return `<table>\n<thead>\n${row('th', b.head)}</thead>\n${body}</table>\n`;
      }
      case 'div':
        return `<div${attrsHtml(b.attrs)}>\n${blocks(b.children)}</div>\n`;
      case 'math':
        return `${math(b.tex, true)}\n`;
      case 'toc':
        return toc();
    }
  }

  // Tight items drop their paragraphs' <p>. A task's checkbox leads its first paragraph.
  function item(it: Item, tight: boolean): string {
    const box =
      it.checked === null ? '' : `<input type="checkbox" disabled${it.checked ? ' checked' : ''}> `;
    const leadsParagraph = it.children[0]?.type === 'paragraph';
    let html = (box ? '<li class="ls-task">' : '<li>') + (leadsParagraph ? '' : box.trimEnd());
    it.children.forEach((child, k) => {
      const lead = k === 0 ? box : '';
      if (child.type !== 'paragraph') html = cr(html) + block(child);
      else if (tight) html += lead + inlines(child.children);
      else html = `${cr(html)}<p>${lead}${inlines(child.children)}</p>\n`;
    });
    return `${html}</li>\n`;
  }

  /** TeX outside the supported subset shows as its source, never half-rendered. */
  function math(tex: string, display: boolean, attrs?: Attrs): string {
    const body = mathml(tex);
    if (body === null) return `<code${attrsHtml(attrs, 'ls-math')}>${escapeHtml(tex)}</code>`;
    return `<math${display ? ' display="block"' : ''}${attrsHtml(attrs)}>${body}</math>`;
  }

  /** An undefined label is its literal text. Numbers follow first references, in order. */
  function footnoteRef(label: string): string {
    const key = normalizeLabel(label);
    if (!footnotes.has(key)) return escapeHtml(`[^${label}]`);
    const n = numbers.get(key) ?? numbers.size + 1;
    numbers.set(key, n);
    const count = (refs.get(key) ?? 0) + 1;
    refs.set(key, count);
    const id = count === 1 ? `ls-fnref-${n}` : `ls-fnref-${n}-${count}`;
    return `<sup class="ls-fnref"><a href="#ls-fn-${n}" id="${id}">${n}</a></sup>`;
  }

  /** Referenced footnotes, in number order. Rendering one can number further ones, which a
   * Map's iteration still reaches. */
  function footnoteSection(): string {
    let items = '';
    for (const [label, n] of numbers) {
      const back = `<a href="#ls-fnref-${n}" class="ls-backref" aria-label="Back to reference ${n}">↩</a>`;
      const body = blocks(footnotes.get(label) ?? []);
      const withBack = body.endsWith('</p>\n')
        ? `${body.slice(0, -'</p>\n'.length)} ${back}</p>\n`
        : `${body}<p>${back}</p>\n`;
      items += `<li id="ls-fn-${n}">\n${withBack}</li>\n`;
    }
    return items ? `<section class="ls-footnotes">\n<ol>\n${items}</ol>\n</section>\n` : '';
  }

  function toc(): string {
    type Entry = { level: number; link: string; children: Entry[] };
    const root: Entry = { level: 0, link: '', children: [] };
    const path = [root];
    for (const h of headings(doc.children)) {
      while ((path.at(-1) as Entry).level >= h.level) path.pop();
      const link = `<a href="#ls-${escapeHtml(h.attrs.id)}">${escapeHtml(plainText(h.children))}</a>`;
      const entry: Entry = { level: h.level, link, children: [] };
      (path.at(-1) as Entry).children.push(entry);
      path.push(entry);
    }
    const list = (entries: Entry[]): string =>
      `<ul>\n${entries.map((e) => `<li>${e.link}${e.children.length ? `\n${list(e.children)}` : ''}</li>\n`).join('')}</ul>\n`;
    return root.children.length ? `<nav class="ls-toc">\n${list(root.children)}</nav>\n` : '';
  }

  return blocks(doc.children) + footnoteSection();
}

/** Escapes text, wrapping defined abbreviations, as whole words, in <abbr>. */
function abbreviator(doc: Document): (text: string) => string {
  const titles = new Map(doc.abbreviations.map((a) => [a.term, a.title]));
  if (!titles.size) return escapeHtml;
  const terms = [...titles.keys()]
    .sort((a, b) => b.length - a.length)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])(${terms.join('|')})(?![\\p{L}\\p{N}_])`, 'u');
  return (text) =>
    text
      .split(pattern)
      .map((part, k) =>
        k % 2
          ? `<abbr${attr('title', titles.get(part) ?? '')}>${escapeHtml(part)}</abbr>`
          : escapeHtml(part),
      )
      .join('');
}
