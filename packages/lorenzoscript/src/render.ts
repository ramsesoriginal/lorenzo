// HTML renderer (ADR 0100). Output is built only from the syntax tree, with
// every text and attribute escaped, so it is safe to assign to innerHTML.
// URL rules (RFC 0027 §5) are enforced here and nowhere else.
import type { Block, Document, Inline, Item } from './ast';

export type RenderOptions = {
  /** Render `https` images. When false, every image renders as its alt text. Default true. */
  externalImages?: boolean;
};

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const escapeHtml = (s: string) => s.replace(/[&<>"]/g, (c) => ESCAPES[c] as string);
const attr = (name: string, value: string) => (value ? ` ${name}="${escapeHtml(value)}"` : '');
const cr = (html: string) => (html.endsWith('\n') ? html : `${html}\n`);

/** Plain text of inline content, e.g. for an image's alt. */
const plain = (nodes: Inline[]): string =>
  nodes.map((n) => ('children' in n ? plain(n.children) : 'text' in n ? n.text : ' ')).join('');

/** The URL to emit, or null if its scheme isn't allowed. */
const safeUrl = (url: string, schemes: RegExp) =>
  schemes.test(url) ? url.replace(/ /g, '%20') : null;
const LINK_SCHEMES = /^(?:https?|mailto):/i;
const IMAGE_SCHEMES = /^https:/i;

export function render(doc: Document, options: RenderOptions = {}): string {
  const inlines = (nodes: Inline[]): string => nodes.map(inline).join('');

  function inline(n: Inline): string {
    switch (n.type) {
      case 'text':
        return escapeHtml(n.text);
      case 'codespan':
        return `<code>${escapeHtml(n.text)}</code>`;
      case 'break':
        return '<br>\n';
      case 'link': {
        // In-document fragments point at author ids, which always carry the prefix.
        const href = n.url.startsWith('#') ? `#ls-${n.url.slice(1)}` : safeUrl(n.url, LINK_SCHEMES);
        const body = inlines(n.children);
        return href === null
          ? body
          : `<a${attr('href', href)}${attr('title', n.title)}>${body}</a>`;
      }
      case 'image': {
        const alt = plain(n.children);
        const src = options.externalImages === false ? null : safeUrl(n.url, IMAGE_SCHEMES);
        return src === null
          ? escapeHtml(alt)
          : `<img${attr('src', src)} alt="${escapeHtml(alt)}"${attr('title', n.title)}>`;
      }
      default:
        return `<${n.type}>${inlines(n.children)}</${n.type}>`;
    }
  }

  const blocks = (list: Block[]): string => list.map(block).join('');

  function block(b: Block): string {
    switch (b.type) {
      case 'paragraph':
        return `<p>${inlines(b.children)}</p>\n`;
      case 'heading':
        return `<h${b.level}>${inlines(b.children)}</h${b.level}>\n`;
      case 'blockquote':
        return `<blockquote>\n${blocks(b.children)}</blockquote>\n`;
      case 'code': {
        const lang = /^[\w+#.-]+$/.test(b.lang) ? `language-${b.lang}` : '';
        return `<pre><code${attr('class', lang)}>${escapeHtml(b.text)}</code></pre>\n`;
      }
      case 'rule':
        return '<hr>\n';
      case 'list': {
        const tag = b.ordered ? 'ol' : 'ul';
        const start = b.ordered && b.start !== 1 ? ` start="${b.start}"` : '';
        return `<${tag}${start}>\n${b.items.map((it) => item(it, b.tight)).join('')}</${tag}>\n`;
      }
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

  return blocks(doc.children);
}
