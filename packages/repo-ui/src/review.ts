// The three-way review element (ADR 0389): a field that changed, drawn as its name, its values
// stacked (Was, Now, Yours) and, where the person has to choose, the choice. Plain DOM; every value
// reaches the page as a text node, never as markup. The host decides what a choice does.

import type { ReviewItem, ReviewOptions, ReviewSide, ReviewWords } from './types';
import { reviewRows, reviewWords } from './words';

// Ids and radio names have to be unique in the page, and a screen draws many reviews.
let serial = 0;

function node<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string) {
  const element = document.createElement(tag);

  element.className = className;

  if (text !== undefined) element.textContent = text;

  return element;
}

type Draw = {
  readonly words: ReviewWords;
  readonly mode: 'choose' | 'act';
  readonly choose: (id: string, side: ReviewSide, label: string) => void;
};

function values(item: ReviewItem, words: ReviewWords): HTMLElement | null {
  const rows = reviewRows(item.change, words);

  if (rows.length === 0) return null;

  const list = node('dl', 'repo-review-values');

  for (const row of rows) {
    const term = node('dt', 'repo-review-term', row.term);
    const value = node('dd', 'repo-review-value', row.text);

    value.dataset.value = row.kind;
    list.append(term, value);
  }

  return list;
}

// The two radio buttons of `choose`: a group with the field's name and the question as its name.
function radios(item: ReviewItem, labelId: string, draw: Draw): HTMLElement {
  const group = node('fieldset', 'repo-review-choice');
  const legend = node('legend', 'repo-review-question', draw.words.choiceLegend);
  const name = `repo-review-${++serial}`;

  legend.id = `${name}-question`;
  group.setAttribute('aria-labelledby', `${labelId} ${legend.id}`);
  group.append(legend);

  for (const [side, text] of [
    ['mine', draw.words.keepMine],
    ['theirs', draw.words.takeTheirs],
  ] as const) {
    const option = node('label', 'repo-review-option');
    const input = document.createElement('input');

    input.type = 'radio';
    input.name = name;
    input.value = side;
    input.required = true;
    input.checked = item.choice?.chosen === side;
    input.addEventListener('change', () => {
      if (input.checked) draw.choose(item.id, side, item.label);
    });
    option.append(input, document.createTextNode(text));
    group.append(option);
  }

  return group;
}

// The two buttons of `act`: pressing one is the choice.
function buttons(item: ReviewItem, labelId: string, draw: Draw): HTMLElement {
  const group = node('div', 'repo-review-actions');

  group.setAttribute('role', 'group');
  group.setAttribute('aria-label', draw.words.chooseFor(item.label));
  group.setAttribute('aria-describedby', labelId);

  for (const [side, text] of [
    ['mine', draw.words.keepMine],
    ['theirs', draw.words.takeTheirs],
  ] as const) {
    const button = node('button', 'repo-review-action', text);

    button.type = 'button';
    button.dataset.side = side;
    button.addEventListener('click', () => draw.choose(item.id, side, item.label));
    group.append(button);
  }

  return group;
}

function field(item: ReviewItem, draw: Draw): HTMLElement {
  const root = node('div', 'repo-review-item');
  const label = node('strong', 'repo-review-label', item.label);

  label.id = `repo-review-label-${++serial}`;
  root.dataset.reviewItem = item.id;
  root.append(label);

  const list = values(item, draw.words);

  if (list) root.append(list);

  if (item.note !== undefined && item.note !== '') {
    root.append(node('p', 'repo-review-note', item.note));
  }

  if (item.choice !== undefined) {
    root.append(
      draw.mode === 'choose' ? radios(item, label.id, draw) : buttons(item, label.id, draw),
    );
  }

  return root;
}

/**
 * Draws a list of changed fields. One review for a row that changed several fields, or for a single
 * field: the element is the same. The returned element holds its own polite status line, which says
 * what was chosen for a screen reader; draw it again with fresh items to change what it shows.
 */
export function renderReview(
  items: readonly ReviewItem[],
  options: ReviewOptions = {},
): HTMLElement {
  const words = reviewWords(options.words);
  const root = node('div', 'repo-review');
  const status = node('p', 'repo-review-status');

  status.setAttribute('role', 'status');

  const draw: Draw = {
    words,
    mode: options.mode ?? 'choose',
    choose(id, side, label) {
      status.textContent = side === 'mine' ? words.keptMine(label) : words.tookTheirs(label);
      options.onChoose?.(id, side);
    },
  };

  root.append(...items.map((item) => field(item, draw)), status);

  return root;
}
