// The icons Bench draws, from the brand atlas (`apps/brand/icons.svg`, identity §17): one shared
// sprite, one Lorenzo-owned name for each. `<use>` points at the sprite as a file the bundler
// emits, so the drawings are not repeated in the page.
import spriteUrl from '@lorenzo/brand/icons.svg?url';

const NS = 'http://www.w3.org/2000/svg';

/** Every atlas icon Bench names, without the `icon-` the sprite's ids start with. A test checks each is in the sprite. */
export const ICON_NAMES = [
  // Window chrome
  'close',
  'search',
  'add',
  'decrease',
  'expand',
  'next',
  'up',
  'down',
  'outdent',
  'indent',
  'float',
  'dock',
  'inherited-from',
  // State
  'select-item',
  'warning',
  'error',
  'pending',
  'offline',
  'refresh',
  'ancestry',
  // Who can read a note: the lock on one that is Everyone's
  'private',
  // The panes and the layouts
  'edit',
  'stat',
  'link',
  'table',
  'compare',
  'formula',
  'picture',
  'pack',
  'list',
  'kinds',
  'sort',
  'layout-write',
  'layout-inspect',
  'layout-compare',
  // Things done
  'undo',
  'login',
  'logout',
  // Kinds
  'kind-entity',
  'kind-entities',
  'kind-item',
  'kind-being',
  'kind-group',
  'kind-location',
  'kind-fact',
  'kind-clock',
  'kind-calendar',
  'kind-connection',
  'kind-event',
  'kind-book',
  'kind-chapter',
] as const;

export type IconName = (typeof ICON_NAMES)[number];

/** A stroked icon of the atlas, `size` pixels square; it takes the colour of its text. */
export function icon(name: IconName, size = 16): SVGSVGElement {
  const s = document.createElementNS(NS, 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('width', String(size));
  s.setAttribute('height', String(size));
  s.setAttribute('aria-hidden', 'true');
  s.setAttribute('class', `ic ic-${name}`);
  const use = document.createElementNS(NS, 'use');
  use.setAttribute('href', `${spriteUrl}#icon-${name}`);
  s.append(use);
  return s;
}

/**
 * The icon of each entry kind. A kind not here (a new one) is drawn as a bare entry until it has
 * its own; the kinds that have no part of the app yet are listed so they arrive with an icon.
 */
const KIND_ICONS: Readonly<Record<string, IconName>> = {
  character: 'kind-being',
  being: 'kind-being',
  item: 'kind-item',
  item_instance: 'kind-item',
  group: 'kind-group',
  location: 'kind-location',
  fact: 'kind-fact',
  clock: 'kind-clock',
  calendar: 'kind-calendar',
  connection: 'kind-connection',
  event: 'kind-event',
  book: 'kind-book',
  chapter: 'kind-chapter',
};

/** The icon for an entry's kinds: the first of its kinds that has one, else the bare entry's. */
export function kindIcon(kinds: readonly string[]): IconName {
  for (const kind of kinds) {
    const known = KIND_ICONS[kind];
    if (known) return known;
  }
  return 'kind-entity';
}

/**
 * A button that is only an icon: it is named and titled by `label`, the drawing is hidden from
 * readers. `className` is the button's own, so each pane keeps its look.
 */
export function iconButton(
  name: IconName,
  label: string,
  onClick: (event: MouseEvent) => void,
  className = 'btn',
  size = 14,
): HTMLButtonElement {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = className;
  b.setAttribute('aria-label', label);
  b.title = label;
  b.append(icon(name, size));
  b.addEventListener('click', onClick);
  return b;
}

/** The icon of each pane, for its tab, its title line and the palette. */
const PANE_ICONS: Readonly<Record<string, IconName>> = {
  explorer: 'kind-entities',
  entry: 'edit',
  props: 'stat',
  links: 'link',
  ancestry: 'ancestry',
  table: 'table',
  grid: 'compare',
  formula: 'formula',
  pictures: 'picture',
  pack: 'pack',
  vocabulary: 'list',
};

export function paneIcon(pane: string): IconName | null {
  return PANE_ICONS[pane] ?? null;
}

/** The icon for how an entry's changes are doing; the words beside it say it (identity §17.8). */
export function statusIcon(
  status: 'synced' | 'waiting' | 'offline' | 'conflict' | 'attention',
): IconName {
  switch (status) {
    case 'synced':
      return 'select-item';
    case 'waiting':
      return 'pending';
    case 'offline':
      return 'offline';
    case 'conflict':
      return 'warning';
    case 'attention':
      return 'error';
  }
}

/** The layout presets' icons. */
export const LAYOUT_ICONS = {
  write: 'layout-write',
  inspect: 'layout-inspect',
  compare: 'layout-compare',
} as const satisfies Record<string, IconName>;
