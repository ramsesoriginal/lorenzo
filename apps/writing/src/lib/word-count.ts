import { parse, render } from '@lorenzo/lorenzoscript';

const segmenter = new Intl.Segmenter('en', { granularity: 'word' });
const words = (text: string) => {
  let total = 0;
  for (const segment of segmenter.segment(text)) if (segment.isWordLike) total++;
  return total;
};
const amount = (count: number) => `${count} ${count === 1 ? 'word' : 'words'}`;

// Keep inline formatting continuous. Separate blocks, cells and omitted non-prose nodes.
function prose(root: Node, range?: Range): string {
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

function disclosure(title: string) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = title;
  details.append(summary);
  return details;
}

export function draftCount(sources: () => string[]) {
  const element = disclosure('Word count');
  const output = document.createElement('p');
  element.append(output);
  let timer: ReturnType<typeof setTimeout> | undefined;
  const draw = () => {
    if (!element.open || !element.isConnected) return;
    const template = document.createElement('template');
    let count = 0;
    for (const source of sources()) {
      template.innerHTML = render(parse(source), { externalImages: false });
      count += words(prose(template.content));
    }
    output.textContent = `Current draft · ${amount(count)}`;
  };
  element.addEventListener('toggle', draw);
  return {
    element,
    refresh() {
      clearTimeout(timer);
      if (element.open) timer = setTimeout(draw, 200);
    },
  };
}

// A document selection can change through touch handles, keyboard or a mouse drag.
// Look up the mounted disclosure so a closed or revoked review is never retained here.
const observedDocuments = new WeakSet<Document>();
function watchSelection(doc: Document) {
  if (observedDocuments.has(doc)) return;
  observedDocuments.add(doc);
  doc.addEventListener('selectionchange', () => {
    for (const panel of doc.querySelectorAll('details[data-reading-word-count][open]'))
      panel.dispatchEvent(new Event('manuscript-selection'));
  });
}

export function readingCount(article: HTMLElement, passages: readonly HTMLElement[]) {
  const element = disclosure('Word count');
  const total = document.createElement('p');
  const selection = document.createElement('p');
  const picker = disclosure('Choose passages');
  const subtotal = document.createElement('p');
  picker.append(subtotal);
  element.append(total, selection, picker);
  let counts: { text: string; count: number }[] | undefined;
  const updateSelection = () => {
    if (!element.open) return;
    const selected = article.ownerDocument.getSelection();
    if (!selected || selected.isCollapsed || !selected.rangeCount) {
      selection.textContent = 'Highlight a passage in the manuscript to count it.';
      return;
    }
    const range = selected.getRangeAt(0);
    const count = passages.reduce((sum, passage) => sum + words(prose(passage, range)), 0);
    const label = `Highlighted passage · ${amount(count)}`;
    if (selection.textContent !== label) selection.textContent = label;
  };
  element.dataset.readingWordCount = '';
  watchSelection(article.ownerDocument);
  element.addEventListener('manuscript-selection', updateSelection);
  element.addEventListener('toggle', () => {
    if (!element.open) return;
    counts ??= passages.map((passage) => {
      const text = prose(passage);
      return { text, count: words(text) };
    });
    total.textContent = `Assembled manuscript · ${amount(counts.reduce((sum, item) => sum + item.count, 0))}`;
    updateSelection();
  });
  picker.addEventListener('toggle', () => {
    if (!picker.open || !counts || picker.querySelector('input')) return;
    let selected = 0;
    const draw = () => {
      subtotal.textContent = `Chosen passages · ${amount(selected)}`;
    };
    draw();
    for (const [index, item] of counts.entries()) {
      const label = document.createElement('label');
      label.className = 'row';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.addEventListener('change', () => {
        selected += input.checked ? item.count : -item.count;
        draw();
      });
      label.append(
        input,
        `Passage ${index + 1} · ${item.text.trim().replace(/\s+/g, ' ').slice(0, 60) || 'Empty text'}`,
      );
      picker.append(label);
    }
  });
  return element;
}
