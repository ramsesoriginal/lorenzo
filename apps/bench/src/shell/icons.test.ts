import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { ICON_NAMES, kindIcon } from './icons';

// The atlas the icons are drawn from, and the manifest that names where each one comes from.
const brand = (file: string) =>
  readFileSync(new URL(`../../../brand/${file}`, import.meta.url), 'utf8');
const symbols = new Set(
  [...brand('icons.svg').matchAll(/<symbol id="icon-([a-z0-9-]+)"/g)].map((m) => m[1]),
);
const manifest = new Set(
  [...brand('icons.manifest.yaml').matchAll(/^icon-([a-z0-9-]+):/gm)].map((m) => m[1]),
);

describe('the atlas', () => {
  it('has every icon Bench names', () => {
    expect(ICON_NAMES.filter((name) => !symbols.has(name))).toEqual([]);
  });

  it('and its manifest list the same icons', () => {
    expect([...symbols].filter((id) => !manifest.has(id))).toEqual([]);
    expect([...manifest].filter((id) => !symbols.has(id))).toEqual([]);
  });
});

describe('kindIcon', () => {
  it('draws the first of an entry’s kinds that has an icon', () => {
    expect(kindIcon(['being'])).toBe('kind-being');
    expect(kindIcon(['character'])).toBe('kind-being');
    expect(kindIcon(['item'])).toBe('kind-item');
    expect(kindIcon(['item_instance'])).toBe('kind-item');
    expect(kindIcon(['mystery', 'location'])).toBe('kind-location');
  });

  it('draws the kinds that are planned too, each with its own', () => {
    const planned = [
      'group',
      'location',
      'fact',
      'clock',
      'calendar',
      'connection',
      'event',
      'book',
      'chapter',
    ];
    const drawn = planned.map((kind) => kindIcon([kind]));
    expect(new Set(drawn).size).toBe(planned.length);
    for (const name of drawn) expect(name.startsWith('kind-')).toBe(true);
  });

  it('draws an entry of no known kind as a bare entry', () => {
    expect(kindIcon([])).toBe('kind-entity');
    expect(kindIcon(['unheard-of'])).toBe('kind-entity');
  });
});
