import { describe, expect, it } from 'vitest';
import { byRecent, editedWords, shown, type Work } from './shelf-list';

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

describe('the shelf by time', () => {
  const at = (iso: string) => new Date(iso);
  it('puts the most recently changed first and the unknown last', () => {
    const list: Work[] = [
      { id: 'a', name: 'A', kind: 'scene', edited: '2026-11-01T10:00:00Z' },
      { id: 'b', name: 'B', kind: 'scene' },
      { id: 'c', name: 'C', kind: 'scene', edited: '2026-11-10T10:00:00Z' },
    ];
    expect(byRecent(list).map((w) => w.id)).toEqual(['c', 'a', 'b']);
  });

  it('says when in plain words', () => {
    const now = at('2026-11-19T12:00:00');
    expect(editedWords('2026-11-19T01:00:00', now)).toBe('Edited today');
    expect(editedWords('2026-11-18T23:00:00', now)).toBe('Edited yesterday');
    expect(editedWords('2026-11-15T12:00:00', now)).toBe('Edited 4 days ago');
    expect(editedWords('2026-10-01T12:00:00', now)).toMatch(/^Edited .*2026/);
    expect(editedWords(undefined, now)).toBe('');
  });
});
