// The palette's dialog (ADR 0414): a search field, the scopes (Tab narrows), grouped results with the
// match in bold, a preview of the selected row on a wide screen, and the keys written at the bottom.
// What it finds is palette.ts's; the styles are the brand's (`dialog.palette`).

import { closeDialog, fadeOnDismiss, openDialog } from './dialog';
import {
  flatten,
  moveSelection,
  nextScope,
  type PaletteItem,
  type PalettePreview,
  type PaletteScope,
  pushRecent,
  SCOPES,
  type Section,
  search,
} from './palette';

export type PaletteUiOptions = {
  /** The commands and the apps, always there; the palette filters them. */
  items(): PaletteItem[];
  /** Entries across apps for a query. The shell does not know how; an app or the API client does. */
  entries?(query: string): Promise<PaletteItem[]>;
  /** The brand's icon sprite: `https://…/icons.svg`. */
  sprite: string;
  /** Where the recent ones are kept in this browser. */
  recentKey: string;
};

export type PaletteUi = {
  open(scope?: PaletteScope): void;
  close(): void;
  isOpen(): boolean;
};

const SVG = 'http://www.w3.org/2000/svg';

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;

  return node;
}

function icon(sprite: string, name: string): SVGSVGElement {
  const svg = document.createElementNS(SVG, 'svg');
  const use = document.createElementNS(SVG, 'use');

  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', `${sprite}#icon-${name}`);
  svg.append(use);

  return svg;
}

function readRecent(key: string): string[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(key) ?? '[]');

    return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
}

function writeRecent(key: string, recent: string[]) {
  try {
    window.localStorage.setItem(key, JSON.stringify(recent));
  } catch {
    // Private browsing: the palette simply remembers nothing.
  }
}

/** A name with the matched parts in <mark>. */
function highlighted(name: string, ranges: [number, number][]): DocumentFragment {
  const fragment = document.createDocumentFragment();
  let at = 0;

  for (const [start, end] of ranges) {
    if (start > at) fragment.append(name.slice(at, start));
    fragment.append(el('mark', undefined, name.slice(start, end)));
    at = end;
  }
  if (at < name.length) fragment.append(name.slice(at));

  return fragment;
}

export function mountPalette(options: PaletteUiOptions): PaletteUi {
  const dialog = el('dialog', 'palette');
  const input = el('input');
  const tabs = el('div', 'p-tabs');
  const list = el('div', 'p-list');
  const preview = el('div', 'p-prev');
  const live = el('div', 'visually-hidden');

  dialog.setAttribute('aria-label', 'Search or run a command');
  input.type = 'text';
  input.placeholder = 'Search or run a command';
  input.setAttribute('aria-label', 'Search');
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'true');
  input.autocomplete = 'off';
  list.id = 'shell-palette-list';
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', 'Results');
  input.setAttribute('aria-controls', list.id);
  tabs.setAttribute('role', 'tablist');
  live.setAttribute('role', 'status');
  live.setAttribute('aria-live', 'polite');

  const head = el('div', 'p-in');

  head.append(icon(options.sprite, 'search'), input, el('kbd', undefined, 'Esc'));

  const scopeButtons = new Map<PaletteScope, HTMLButtonElement>();

  for (const scope of SCOPES) {
    const button = el('button', undefined, scope);

    button.type = 'button';
    button.setAttribute('role', 'tab');
    button.addEventListener('click', () => {
      state.scope = scope;
      state.index = 0;
      refresh();
      input.focus();
    });
    scopeButtons.set(scope, button);
    tabs.append(button);
  }

  const body = el('div', 'p-body');
  const foot = el('div', 'p-foot');

  body.append(list, preview);
  for (const [keys, label] of [
    ['↑ ↓', 'move'],
    ['Enter', 'open'],
    ['Tab', 'narrow'],
    ['Esc', 'close'],
  ] as const) {
    const hint = el('span');

    hint.append(el('kbd', undefined, keys), ` ${label}`);
    foot.append(hint);
  }
  foot.append(el('span', 'p-foot-end', '? for all shortcuts'));
  dialog.append(head, tabs, body, foot, live);
  document.body.append(dialog);
  fadeOnDismiss(dialog);

  const state = {
    scope: 'Everything' as PaletteScope,
    query: '',
    index: 0,
    found: [] as PaletteItem[],
    asked: 0,
    recent: readRecent(options.recentKey),
  };
  let sections: Section[] = [];

  function choose(item: PaletteItem) {
    state.recent = pushRecent(state.recent, item.id);
    writeRecent(options.recentKey, state.recent);
    closeDialog(dialog);
    item.run();
  }

  function drawPreview(item: PaletteItem | undefined) {
    preview.replaceChildren();
    if (!item) return;

    const shown: PalettePreview = item.preview ?? {
      title: item.name,
      ...((item.app ?? item.kind) ? { subtitle: (item.app ?? item.kind) as string } : {}),
    };

    preview.append(el('strong', undefined, shown.title));
    if (shown.subtitle) preview.append(el('p', 'status-text', shown.subtitle));
    if (shown.blurb) preview.append(el('p', undefined, shown.blurb));
  }

  function refresh() {
    sections = search([...options.items(), ...state.found], state.query, state.scope, state.recent);
    const rows = flatten(sections);

    state.index = moveSelection(state.index, 0, rows.length);

    for (const [scope, button] of scopeButtons) {
      button.setAttribute('aria-selected', String(scope === state.scope));
    }

    list.replaceChildren();
    let n = 0;

    for (const section of sections) {
      list.append(el('div', 'p-group', section.group));
      for (const row of section.rows) {
        const index = n++;
        const option = el('div', 'p-opt');
        const item = row.item;

        option.id = `shell-palette-opt-${index}`;
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', String(index === state.index));
        if (item.icon) option.append(icon(options.sprite, item.icon));

        const name = el('span', 'grow');

        name.append(highlighted(item.name, row.ranges));
        option.append(name);
        if (item.danger) option.append(el('span', 'meta', 'Asks first'));
        if (item.kind) option.append(el('span', 'meta', item.kind));

        const end = el('span', 'p-end');

        if (item.keys) end.append(el('kbd', undefined, item.keys));
        else if (item.app) end.textContent = item.app;
        if (end.hasChildNodes()) option.append(end);

        option.addEventListener('click', () => choose(item));
        list.append(option);
      }
    }

    if (rows.length === 0) {
      list.append(
        el(
          'div',
          'p-empty',
          state.query ? `Nothing found for “${state.query}”.` : 'Nothing to show.',
        ),
      );
    }

    const selected = rows[state.index];

    input.setAttribute('aria-activedescendant', selected ? `shell-palette-opt-${state.index}` : '');
    drawPreview(selected?.item);
    document
      .getElementById(`shell-palette-opt-${state.index}`)
      ?.scrollIntoView?.({ block: 'nearest' });
    live.textContent =
      rows.length === 0
        ? 'No results'
        : `${rows.length} ${rows.length === 1 ? 'result' : 'results'}`;
  }

  input.addEventListener('input', async () => {
    state.query = input.value;
    state.index = 0;
    refresh();

    if (
      !options.entries ||
      state.query.trim() === '' ||
      state.scope === 'Apps' ||
      state.scope === 'Actions'
    ) {
      state.found = [];

      return;
    }

    const asked = ++state.asked;

    try {
      const found = await options.entries(state.query);

      // A slower answer to an earlier query is not this one's.
      if (asked !== state.asked) return;
      state.found = found;
    } catch {
      state.found = [];
    }
    refresh();
  });

  dialog.addEventListener('keydown', (event) => {
    const rows = flatten(sections);

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      state.index = moveSelection(state.index, event.key === 'ArrowDown' ? 1 : -1, rows.length);
      refresh();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const row = rows[state.index];

      if (row) choose(row.item);
    } else if (event.key === 'Tab') {
      event.preventDefault();
      state.scope = nextScope(state.scope, event.shiftKey ? -1 : 1);
      state.index = 0;
      refresh();
    }
  });

  return {
    open(scope = 'Everything') {
      state.scope = scope;
      state.query = '';
      state.index = 0;
      state.found = [];
      state.recent = readRecent(options.recentKey);
      input.value = '';
      refresh();
      openDialog(dialog);
      input.focus();
    },
    close() {
      closeDialog(dialog);
    },
    isOpen() {
      return dialog.open;
    },
  };
}
