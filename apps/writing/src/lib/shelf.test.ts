import { describe, expect, it } from 'vitest';
import { shown, type Work } from './shelf-list';

const works: Work[] = [
  { id: '1', name: 'The Long Water', kind: 'book' },
  { id: '2', name: 'Across the water', kind: 'scene' },
  { id: '3', name: 'A telling', kind: 'scene_telling' },
  { id: '4', name: 'Ferryman', kind: 'biography' },
];

describe('the shelf', () => {
  it('shows everything for All and no words', () => {
    expect(shown(works, 'all', '')).toHaveLength(4);
  });

  it('filters by kind, Scenes holding the tellings too', () => {
    expect(shown(works, 'book', '').map((w) => w.id)).toEqual(['1']);
    expect(shown(works, 'scene', '').map((w) => w.id)).toEqual(['2', '3']);
    expect(shown(works, 'biography', '').map((w) => w.id)).toEqual(['4']);
  });

  it('searches every word, whatever the case', () => {
    expect(shown(works, 'all', 'WATER').map((w) => w.id)).toEqual(['1', '2']);
    expect(shown(works, 'all', 'water across').map((w) => w.id)).toEqual(['2']);
    expect(shown(works, 'book', 'across')).toEqual([]);
  });
});
