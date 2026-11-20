import type { VocabularyEntry } from '@lorenzo/stat-values';
import { describe, expect, it } from 'vitest';
import { isListView, mapLimited, numbersOf, sideRows, vitalLine } from './listViews';

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
    const a = { all: [{ name: 'hp', label: 'HP', text: '1', derived: false }], vitals: [] };
    const b = {
      all: [
        { name: 'ac', label: 'AC', text: '2', derived: true },
        { name: 'hp', label: 'HP', text: '3', derived: false },
      ],
      vitals: [],
    };

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
    expect(vitalLine({ name: 'hp', label: 'Hit points', text: '14', derived: false })).toBe(
      '14 hit points',
    );
  });
});
