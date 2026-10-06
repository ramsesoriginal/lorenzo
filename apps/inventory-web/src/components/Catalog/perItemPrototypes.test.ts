import { describe, expect, it } from 'vitest';
import type { CatalogItem } from '../../lib/types';
import { perItemPrototypeIds } from './perItemPrototypes';

function item(id: string, parents: string[], isPublic: boolean): CatalogItem {
  return { entity_id: id, prototype_ids: parents, in_public_catalog: isPublic } as CatalogItem;
}

describe('perItemPrototypeIds', () => {
  const catalog = [
    item('weapon', [], false),
    item('martial', ['weapon'], false),
    item('blade', ['weapon'], false),
    item('longsword-5e', ['martial'], false),
    item('longsword', ['blade', 'longsword-5e'], true),
    item('dagger', ['blade'], true),
  ];

  it('hides a non-public prototype whose only child is a plain item', () => {
    expect([...perItemPrototypeIds(catalog)]).toEqual(['longsword-5e']);
  });

  it('keeps categories with several children, however plain those are', () => {
    const hidden = perItemPrototypeIds(catalog);

    expect(hidden.has('blade')).toBe(false);
    expect(hidden.has('weapon')).toBe(false);
  });

  it('keeps a category whose only child is itself a prototype', () => {
    expect(perItemPrototypeIds(catalog).has('martial')).toBe(false);
  });

  it('keeps a public prototype', () => {
    const shown = catalog.map((entry) =>
      entry.entity_id === 'longsword-5e' ? item('longsword-5e', ['martial'], true) : entry,
    );

    expect(perItemPrototypeIds(shown).size).toBe(0);
  });
});
