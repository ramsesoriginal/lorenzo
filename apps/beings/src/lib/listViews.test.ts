import type { VocabularyEntry } from '@lorenzo/stat-values';
import { describe, expect, it } from 'vitest';
import {
  columnsOf,
  hintIdsOf,
  isListView,
  mapLimited,
  numbersOf,
  sideRows,
  vitalLine,
} from './listViews';

const entry = (name: string, extra: Record<string, unknown> = {}) =>
  ({
    group: 'Numbers',
    definition: { id: name, name, value_type: 'int', ...extra },
    hints: {},
  }) as unknown as VocabularyEntry;

describe('isListView', () => {
  it('knows the three views', () => {
    expect(['rows', 'cards', 'side'].every(isListView)).toBe(true);
    expect(isListView('grid')).toBe(false);
    expect(isListView(null)).toBe(false);
  });
});

describe('mapLimited', () => {
  it('keeps the order and never runs more than the limit at once', async () => {
    let running = 0;
    let most = 0;
    const out = await mapLimited([1, 2, 3, 4, 5], 2, async (n) => {
      running++;
      most = Math.max(most, running);
      await new Promise((resolve) => setTimeout(resolve, 5));
      running--;
      return n * 10;
    });

    expect(out).toEqual([10, 20, 30, 40, 50]);
    expect(most).toBe(2);
  });
});

describe('sideRows', () => {
  it('lists each number once, in the order first met', () => {
    const a = {
      all: [{ name: 'hp', label: 'HP', text: '1', derived: false }],
      vitals: [],
    } as never;
    const b = {
      all: [
        { name: 'ac', label: 'AC', text: '2', derived: true },
        { name: 'hp', label: 'HP', text: '3', derived: false },
      ],
      vitals: [],
    } as never;

    expect(sideRows([a, undefined, b]).map((row) => row.name)).toEqual(['hp', 'ac']);
  });
});

describe('numbersOf', () => {
  it('has the numbers only, with the first as the vital when none is pinned', () => {
    const vocabulary = [entry('hp'), entry('body')];
    const found = numbersOf(vocabulary, {
      stats: [
        { name: 'hp', value: 14 },
        { name: 'body', value: 3 },
      ],
    } as never);

    expect(found.all.map((n) => n.name)).toEqual(['hp', 'body']);
    expect(found.vitals.length).toBeGreaterThan(0);
    expect(vitalLine({ name: 'hp', label: 'Hit points', text: '14' } as never)).toBe(
      '14 hit points',
    );
  });
});

describe('hints and columns', () => {
  const vocabulary = [
    entry('max'),
    entry('hit_points', { max_hint_id: 'max', pin: true }),
    entry('body'),
    entry('armour', { pin: true }),
  ];

  it('knows which stats only sit beside another', () => {
    expect([...hintIdsOf(vocabulary)]).toEqual(['max']);
  });

  it('leaves them out of a being’s numbers', () => {
    const found = numbersOf(vocabulary, {
      stats: [
        { name: 'max', value: 20 },
        { name: 'hit_points', value: 14 },
        { name: 'body', value: 3 },
      ],
    } as never);

    expect(found.all.map((n) => n.name)).toEqual(['hit_points', 'body']);
    expect(found.all[0]?.text).toBe('14 / 20');
  });

  it('takes the pinned numbers as the columns, then the others, two in all', () => {
    expect(columnsOf(vocabulary).map((c) => c.label)).toEqual(['Hit points', 'Armour']);
    expect(columnsOf([entry('body'), entry('mind'), entry('reach')]).map((c) => c.name)).toEqual([
      'body',
      'mind',
    ]);
    expect(columnsOf(vocabulary.slice(0, 3)).map((c) => c.name)).toEqual(['hit_points', 'body']);
  });
});
