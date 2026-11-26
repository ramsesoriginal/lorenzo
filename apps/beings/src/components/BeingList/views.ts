// The three views of the list (BN1, BN4): rows as a table, cards, and side by side. They only draw;
// the renderer decides what is shown and what happens when a number is stepped.

import { initials } from '@lorenzo/app-shell';
import { kindLabel, type ListedBeing } from '../../lib/beingList';
import { BRANDING_CSS_URL } from '../../lib/config';
import { beingPageHref } from '../../lib/entityLinks';
import { type Numbers, sideRows } from '../../lib/listViews';
import { playedByText } from '../../lib/playedBy';

export type Drawing = {
  tenantAddress: string;
  numbers: ReadonlyMap<string, Numbers | null>;
  playedBy: ReadonlyMap<string, string[]>;
  rostersKnown: boolean;
  owned: ReadonlySet<string> | null;
  columns: readonly { name: string; label: string }[];
  /** Beings the viewer may run, for the steppers in Play. */
  canRun(being: ListedBeing): boolean;
  playing: boolean;
  step(being: ListedBeing, numberName: string, direction: 'step-down' | 'step-up'): void;
  /** Called for each row or card, to give it its picture. */
  observe(row: HTMLElement, being: ListedBeing): void;
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text) node.textContent = text;

  return node;
}

export function icon(name: string): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');

  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', `${BRANDING_CSS_URL}/icons.svg#icon-${name}`);
  svg.append(use);

  return svg;
}

/** The round avatar: the initials, and the picture over them once it has loaded. */
function avatar(being: ListedBeing, size: 'xs' | 'lg'): HTMLElement {
  const wrap = el('span', `being-avatar being-avatar-${size}`);
  const picture = el('img', 'being-avatar-picture');

  wrap.setAttribute('aria-hidden', 'true');
  wrap.append(el('span', 'being-avatar-initials', initials(being.name)));
  picture.dataset.listPicture = '';
  picture.hidden = true;
  picture.alt = '';
  picture.decoding = 'async';
  picture.width = 72;
  picture.height = 72;
  wrap.append(picture);

  return wrap;
}

function nameLink(being: ListedBeing, drawing: Drawing): HTMLAnchorElement {
  const link = el('a', '', being.name);

  link.href = beingPageHref(drawing.tenantAddress, being);
  link.dataset.name = '';

  return link;
}

const numberText = (numbers: Numbers | null | undefined, name: string): string =>
  numbers?.all.find((number) => number.name === name)?.text ?? '—';

export function drawRows(beings: readonly ListedBeing[], drawing: Drawing): HTMLElement {
  const table = el('div', 'being-table');
  const head = el('div', 'being-row being-row-head');
  const columns = drawing.columns;

  table.setAttribute('role', 'table');
  table.setAttribute('aria-label', 'Beings');
  table.style.setProperty('--being-columns', String(columns.length));
  head.setAttribute('role', 'row');

  for (const [label, right] of [
    ['Name', false],
    ['Kind', false],
    ['Played by', false],
    ...columns.map((column) => [column.label, true] as const),
  ] as const) {
    const cell = el('span', right ? 'being-cell is-number' : 'being-cell', label);

    cell.setAttribute('role', 'columnheader');
    head.append(cell);
  }

  table.append(head);

  for (const being of beings) {
    const row = el('div', 'being-row');
    const name = el('span', 'being-cell being-name');

    row.setAttribute('role', 'row');
    name.setAttribute('role', 'cell');
    name.append(avatar(being, 'xs'), nameLink(being, drawing));

    if (drawing.owned?.has(being.entity_id)) name.append(el('span', 'pill', 'Mine'));

    const kind = el('span', 'being-cell is-muted', kindLabel(being));
    const played = el(
      'span',
      'being-cell is-muted',
      playedByText(
        drawing.playedBy.get(being.entity_id),
        being.is_pc === true,
        drawing.rostersKnown,
      ),
    );

    kind.setAttribute('role', 'cell');
    played.setAttribute('role', 'cell');
    row.append(name, kind, played);

    for (const column of columns) {
      const cell = el(
        'span',
        'being-cell is-number',
        numberText(drawing.numbers.get(being.entity_id), column.name),
      );

      cell.setAttribute('role', 'cell');
      row.append(cell);
    }

    drawing.observe(row, being);
    table.append(row);
  }

  return table;
}

export function drawCards(beings: readonly ListedBeing[], drawing: Drawing): HTMLElement {
  const list = el('ul', 'being-cards');

  for (const being of beings) {
    const item = el('li', 'being-card');
    const played = drawing.playedBy.get(being.entity_id);
    const vital = drawing.numbers.get(being.entity_id)?.vitals[0];

    item.append(avatar(being, 'lg'));
    item.append(nameLink(being, drawing));
    item.append(
      el(
        'span',
        'caption',
        played?.length ? `${kindLabel(being)} · ${played.join(', ')}` : kindLabel(being),
      ),
    );

    if (vital) {
      const line = el('span', 'card-number');

      line.append(el('strong', '', vital.shown));
      if (vital.of !== null) line.append(el('span', 'is-muted', `/ ${vital.of}`));
      line.append(el('span', 'caption', vital.label.toLowerCase()));
      item.append(line);
    }

    if (drawing.owned?.has(being.entity_id)) item.append(el('span', 'pill', 'Mine'));

    drawing.observe(item, being);
    list.append(item);
  }

  return list;
}

function stepButton(label: string, glyph: 'decrease' | 'add', run: () => void): HTMLButtonElement {
  const button = el('button', 'icon-btn');

  button.type = 'button';
  button.setAttribute('aria-label', label);
  button.append(icon(glyph));
  button.addEventListener('click', run);

  return button;
}

export function drawSide(beings: readonly ListedBeing[], drawing: Drawing): HTMLElement {
  const table = el('table', 'datasheet-table');
  const caption = el('caption', 'visually-hidden', 'Numbers of the beings, side by side');
  const head = el('tr');
  const body = el('tbody');
  const corner = el('th', '', 'Stat');
  const found = beings.map((being) => drawing.numbers.get(being.entity_id) ?? undefined);

  corner.scope = 'col';
  head.append(corner);

  for (const being of beings) {
    const th = el('th');

    th.scope = 'col';
    th.append(nameLink(being, drawing), el('span', 'caption', kindLabel(being)));
    head.append(th);
  }

  const played = el('tr');
  const playedHead = el('th', '', 'Played by');

  playedHead.scope = 'row';
  played.append(playedHead);

  for (const being of beings) {
    played.append(
      el(
        'td',
        '',
        playedByText(
          drawing.playedBy.get(being.entity_id),
          being.is_pc === true,
          drawing.rostersKnown,
        ),
      ),
    );
  }

  body.append(played);

  for (const row of sideRows(found)) {
    const tr = el('tr');
    const th = el('th', '', row.label);

    th.scope = 'row';

    if (row.derived) {
      const mark = el('span', 'derived-mark');

      mark.title = 'Derived';
      mark.append(icon('formula'));
      mark.append(el('span', 'visually-hidden', ' (derived)'));
      th.append(' ', mark);
    }

    tr.append(th);

    beings.forEach((being, index) => {
      const number = found[index]?.all.find((candidate) => candidate.name === row.name);
      const td = el('td', 'is-numeric', number?.text ?? '—');

      if (
        drawing.playing &&
        number &&
        number.adjustable &&
        number.value !== null &&
        drawing.canRun(being)
      ) {
        const steppers = el('span', 'cell-steppers');

        steppers.append(
          stepButton(`Lower ${row.label} of ${being.name}`, 'decrease', () =>
            drawing.step(being, row.name, 'step-down'),
          ),
          stepButton(`Raise ${row.label} of ${being.name}`, 'add', () =>
            drawing.step(being, row.name, 'step-up'),
          ),
        );
        td.append(steppers);
      }

      tr.append(td);
    });

    body.append(tr);
  }

  const thead = el('thead');

  thead.append(head);
  table.append(caption, thead, body);

  return table;
}
