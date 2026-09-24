// `references()` (ADR 0105): what a caller must resolve before rendering, and what
// stage 7 stores: entity links, entity images, dates, and calendar expressions.
import type { Block, Document, Inline, Reference } from './ast';
import { allBlocks } from './block';

/** Every reference in the document, footnotes included, once each, in order of first use. */
export function references(doc: Document): Reference[] {
  const found = new Map<string, Reference>();
  const add = (ref: Reference) => {
    const key = JSON.stringify(ref);
    if (!found.has(key)) found.set(key, ref);
  };
  const visit = (nodes: Inline[]): void => {
    for (const n of nodes) {
      if ((n.type === 'link' || n.type === 'image') && n.ref) {
        add({ kind: n.type === 'link' ? 'entity' : 'image', ...n.ref });
      } else if (n.type === 'date') add({ kind: 'date', date: n.date });
      else if (n.type === 'calendar') add({ kind: 'calendar', expression: n.expression });
      if ('children' in n) visit(n.children);
    }
  };
  for (const block of allBlocks(doc, true))
    for (const content of inlineContent(block)) visit(content);
  return [...found.values()];
}

const inlineContent = (b: Block): Inline[][] =>
  b.type === 'paragraph' || b.type === 'heading'
    ? [b.children]
    : b.type === 'table'
      ? [...b.head, ...b.rows.flat()]
      : [];
