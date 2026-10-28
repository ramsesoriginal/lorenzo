import { describe, expect, it } from 'vitest';
import { kindLabel, statText } from '../src/words';

describe('kindLabel and statText', () => {
  it('names the most specific kind in the words of the product', () => {
    expect(kindLabel(['being', 'character'])).toBe('Character');
    expect(kindLabel(['item_instance'])).toBe('Inventory item');
    expect(kindLabel(['item'])).toBe('Item');
    expect(kindLabel([])).toBe('Entry');
  });

  it('has words for a Location and a Map, in the order the registry prefers', () => {
    expect(kindLabel(['location'])).toBe('Location');
    expect(kindLabel(['map'])).toBe('Map');
    expect(kindLabel(['location', 'map'])).toBe('Location');
    expect(kindLabel(['being', 'location'])).toBe('Being');
    expect(kindLabel(['item', 'location'])).toBe('Item');
    expect(kindLabel(['scene'])).toBe('Entry');
  });

  it('writes a stat as a name and a value', () => {
    expect(statText({ name: 'hit_points', value: 9 })).toBe('hit points 9');
  });
});
