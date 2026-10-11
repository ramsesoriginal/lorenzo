import { describe, expect, it } from 'vitest';
import type { EntryState, EntrySummary, StatDef } from '../core/transport';
import {
  add,
  cellsOf,
  defaultColumns,
  fromTsv,
  gridOrder,
  normalise,
  parseCell,
  showCell,
  stepOf,
  toTsv,
  valueSource,
  valuesOf,
} from './gridModel';

const def = (id: string, type: StatDef['type'], name = id): StatDef => ({
  id,
  name,
  type,
  enumValues: [],
});
const defs = [
  def('w', 'float', 'Weight'),
  def('p', 'int', 'Price'),
  def('t', 'text'),
  def('m', 'bool'),
];
const e = (id: string, name: string, parentIds: string[] = []): EntrySummary => ({
  id,
  name,
  kinds: [],
  parentIds,
});

describe('steps', () => {
  it('moves whole numbers by 1 and decimals by 0.1, and nothing else', () => {
    expect(stepOf('int')).toBe(1);
    expect(stepOf('float')).toBe(0.1);
    for (const t of ['text', 'bool', 'enum'] as const) expect(stepOf(t)).toBeNull();
  });

  it('adds decimals without a float tail', () => {
    expect(add(0.1, 0.2)).toBe(0.3);
    expect(add(1.5, -0.1)).toBe(1.4);
  });
});

describe('columns', () => {
  it('starts with the numeric stats, at most four', () => {
    expect(defaultColumns(defs)).toEqual(['w', 'p']);
    const many = Array.from({ length: 6 }, (_, i) => def(`n${i}`, 'int'));
    expect(defaultColumns(many)).toHaveLength(4);
  });
});

describe('typed cells', () => {
  it('reads numbers, with a comma for a decimal', () => {
    expect(parseCell('int', ' 12 ')).toBe(12);
    expect(parseCell('float', '2,5')).toBe(2.5);
    expect(parseCell('int', '1.5')).toBeUndefined();
    expect(parseCell('float', 'heavy')).toBeUndefined();
  });

  it('reads yes and no for a tag, text as it is, and nothing as none', () => {
    expect(parseCell('bool', 'On')).toBe(true);
    expect(parseCell('bool', 'no')).toBe(false);
    expect(parseCell('bool', 'maybe')).toBeUndefined();
    expect(parseCell('text', ' hi ')).toBe('hi');
    expect(parseCell('int', '  ')).toBeNull();
  });

  it('shows a value as a cell does', () => {
    expect(showCell(true)).toBe('On');
    expect(showCell(false)).toBe('Off');
    expect(showCell(1.5)).toBe('1.5');
    expect(showCell(null)).toBe('');
  });
});

describe('where a value comes from', () => {
  const entries = [e('a', 'A'), e('b', 'B', ['a']), e('c', 'C', ['b']), e('d', 'D', ['x', 'a'])];
  const ids: Record<string, string> = { Weight: 'w', Price: 'p' };
  const state = (stats: { name: string; value: number; own: boolean }[]) =>
    valuesOf({
      stats: stats.map((s) => ({ ...s, statId: ids[s.name] ?? 'z' })),
    } as unknown as EntryState);
  const values = new Map([
    ['a', state([{ name: 'Weight', value: 1.5, own: true }])],
    ['b', state([{ name: 'Weight', value: 1.5, own: false }])],
    ['c', state([{ name: 'Weight', value: 1.5, own: false }])],
    ['d', state([])],
  ]);

  it('is the entry itself when the value is its own', () => {
    expect(valueSource(entries, values, 'a', 'w')).toEqual({ kind: 'own' });
  });

  it('is the nearest entry above with a value of its own', () => {
    expect(valueSource(entries, values, 'c', 'w')).toEqual({ kind: 'inherited', from: 'a' });
  });

  it('is nowhere when nothing above has one, and a parent that is not there is skipped', () => {
    expect(valueSource(entries, values, 'a', 'p')).toEqual({ kind: 'none' });
    expect(valueSource(entries, values, 'd', 'w')).toEqual({ kind: 'inherited', from: 'a' });
  });
});

describe('selections and the clipboard', () => {
  it('lists the cells of a rectangle whichever corner it starts from', () => {
    expect(normalise({ r0: 2, c0: 3, r1: 0, c1: 1 })).toEqual({ r0: 0, c0: 1, r1: 2, c1: 3 });
    expect(cellsOf({ r0: 1, c0: 0, r1: 0, c1: 1 })).toHaveLength(4);
  });

  it('writes and reads tab separated rows', () => {
    expect(
      toTsv([
        ['1', '2'],
        ['3', '4'],
      ]),
    ).toBe('1\t2\n3\t4');
    expect(fromTsv('1\t2\r\n3\t4\r\n')).toEqual([
      ['1', '2'],
      ['3', '4'],
    ]);
    expect(fromTsv('5')).toEqual([['5']]);
  });
});

describe('the order of the rows', () => {
  const entries = [
    e('a', 'Weapon'),
    e('b', 'Sword', ['a']),
    e('c', 'Dagger', ['a']),
    e('d', 'Axe'),
  ];

  it('is a tree, children under what they inherit from, by name', () => {
    expect(gridOrder(entries, 'inherits', '').map((r) => [r.entry.name, r.depth])).toEqual([
      ['Axe', 0],
      ['Weapon', 0],
      ['Dagger', 1],
      ['Sword', 1],
    ]);
  });

  it('is A to Z flat on request, and a filtered list is flat too', () => {
    expect(gridOrder(entries, 'name', '').map((r) => r.entry.name)).toEqual([
      'Axe',
      'Dagger',
      'Sword',
      'Weapon',
    ]);
    expect(gridOrder(entries, 'inherits', 'sw').map((r) => [r.entry.name, r.depth])).toEqual([
      ['Sword', 0],
    ]);
  });
});
