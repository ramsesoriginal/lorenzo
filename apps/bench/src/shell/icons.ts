// The few icons Bench draws, as small stroked SVGs (the same line weight and round ends the brand
// icons use). Plain DOM, no sprite: each is one element with a title-less, hidden-from-readers shape.

const NS = 'http://www.w3.org/2000/svg';

const PATHS = {
  item: [
    'M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z',
    'm3.3 7 8.7 5 8.7-5',
    'M12 22V12',
  ],
  being: ['M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2', 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z'],
  bare: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z'],
  search: ['M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z', 'm21 21-4.3-4.3'],
  plus: ['M5 12h14', 'M12 5v14'],
  x: ['M18 6 6 18', 'm6 6 12 12'],
  down: ['m6 9 6 6 6-6'],
  right: ['m9 18 6-6-6-6'],
  float: ['M15 3h6v6', 'M10 14 21 3', 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'],
  check: ['M20 6 9 17l-5-5'],
  alert: [
    'm21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z',
    'M12 9v4',
    'M12 17h.01',
  ],
  sync: [
    'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8',
    'M21 3v5h-5',
    'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16',
    'M8 16H3v5',
  ],
  star: ['M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z'],
  branch: [
    'M6 3v12',
    'M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
    'M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
    'M18 9a9 9 0 0 1-9 9',
  ],
} as const;

export type IconName = keyof typeof PATHS;

/** A 16px stroked icon; `fill` for the one that is a solid shape. */
export function icon(name: IconName, size = 16): SVGSVGElement {
  const s = document.createElementNS(NS, 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('width', String(size));
  s.setAttribute('height', String(size));
  s.setAttribute('aria-hidden', 'true');
  s.setAttribute('class', `ic ic-${name}`);
  for (const d of PATHS[name]) {
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', d);
    s.append(p);
  }
  return s;
}

/** The icon for an entry's kinds: an item, a being, or neither. */
export function kindIcon(kinds: readonly string[]): IconName {
  if (kinds.includes('being') || kinds.includes('character')) return 'being';
  if (kinds.some((k) => k === 'item' || k === 'item_instance')) return 'item';
  return 'bare';
}
