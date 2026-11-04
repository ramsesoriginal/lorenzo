import { parse, render } from '@lorenzo/lorenzoscript';

const segmenter = new Intl.Segmenter('en', { granularity: 'word' });
export const words = (text: string) => {
  let total = 0;
  for (const segment of segmenter.segment(text)) if (segment.isWordLike) total++;
  return total;
};

// Keep inline formatting continuous. Separate blocks, cells and omitted non-prose nodes.
export function prose(root: Node, range?: Range): string {
  const parts: string[] = [];
  const visit = (node: Node) => {
    if (range && !range.intersectsNode(node)) return;
    if (node.nodeType === Node.TEXT_NODE) {
      const value = node.textContent ?? '';
      parts.push(
        value.slice(
          range?.startContainer === node ? range.startOffset : 0,
          range?.endContainer === node ? range.endOffset : undefined,
        ),
      );
      return;
    }
    if (
      node instanceof Element &&
      node.matches('nav,pre,code,math,img,input,sup.ls-fnref,a.ls-backref')
    ) {
      parts.push(' ');
      return;
    }
    const boundary =
      node instanceof Element &&
      node.matches('p,h1,h2,h3,h4,h5,h6,br,li,th,td,div,section,blockquote,hr');
    if (boundary) parts.push(' ');
    for (const child of node.childNodes) visit(child);
    if (boundary) parts.push(' ');
  };
  visit(root);
  return parts.join('');
}

export function countSources(sources: readonly string[]) {
  const template = document.createElement('template');
  let count = 0;
  for (const source of sources) {
    template.innerHTML = render(parse(source), { externalImages: false });
    count += words(prose(template.content));
  }
  return count;
}
