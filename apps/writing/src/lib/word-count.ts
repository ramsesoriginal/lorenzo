import { type GoalContext, lengthGoal } from './length-goal';
import { countSources, prose, words } from './manuscript-count';

const amount = (count: number) => `${count} ${count === 1 ? 'word' : 'words'}`;

function disclosure(title: string) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = title;
  details.append(summary);
  return details;
}

export function draftCount(sources: () => string[], context?: GoalContext) {
  const element = disclosure('Word count');
  const updateGoal = lengthGoal(element, context);
  const output = document.createElement('p');
  element.append(output);
  let timer: ReturnType<typeof setTimeout> | undefined;
  const draw = () => {
    if (!element.open || !element.isConnected) return;
    const count = countSources(sources());
    updateGoal(count);
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

export function readingCount(
  article: HTMLElement,
  passages: readonly HTMLElement[],
  context?: GoalContext,
) {
  const element = disclosure('Word count');
  const updateGoal = lengthGoal(element, context);
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
    updateGoal(counts.reduce((sum, item) => sum + item.count, 0));
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
