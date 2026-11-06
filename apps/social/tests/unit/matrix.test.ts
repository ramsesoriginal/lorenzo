import { expect, test } from 'vitest';
import {
  batches,
  buildCells,
  type Cell,
  cellKey,
  isConflict,
  moveFocus,
  parseInput,
  planOperations,
  type Tie,
  visibleRange,
  WINDOW,
  windows,
} from '../../src/lib/matrix';

const tie = (id: string, a: string, b: string, oneWay: boolean): Tie => ({
  id,
  name: id,
  endA: a,
  endB: b,
  oneWay,
});

test('a one-way relationship fills its own cell and a two-way one both cells of its pair', () => {
  const cells = buildCells(
    [tie('r1', 'a', 'b', true), tie('r2', 'b', 'c', false)],
    new Map([['r1', { value: 3, own: true }]]),
    new Set(['a', 'b', 'c']),
    new Set(['a', 'b', 'c']),
  );
  expect(cells.get(cellKey('a', 'b'))?.value).toEqual({ value: 3, own: true });
  expect(cells.get(cellKey('b', 'a'))).toBeUndefined();
  expect(cells.get(cellKey('b', 'c'))?.ties[0]?.id).toBe('r2');
  expect(cells.get(cellKey('c', 'b'))?.ties[0]?.id).toBe('r2');
});

test('only the cells of the window are filled, and two ties for one cell are a conflict', () => {
  const cells = buildCells(
    [tie('r1', 'a', 'b', true), tie('r2', 'a', 'b', true), tie('r3', 'a', 'z', true)],
    new Map(),
    new Set(['a']),
    new Set(['b']),
  );
  expect(cells.size).toBe(1);
  const cell = cells.get(cellKey('a', 'b')) as Cell;
  expect(isConflict(cell)).toBe(true);
  expect(cell.value).toBeNull();
  expect(isConflict(undefined)).toBe(false);
});

test('what a person types is bounded by the stat: empty clears, a whole number inside the scale sets', () => {
  const honor = { valueType: 'int', min: -10, max: 10, name: 'Honor' };
  expect(parseInput('', honor)).toEqual({ ok: true, value: null });
  expect(parseInput(' 7 ', honor)).toEqual({ ok: true, value: 7 });
  expect(parseInput('-10', honor)).toEqual({ ok: true, value: -10 });
  expect(parseInput('11', honor)).toMatchObject({ ok: false });
  expect(parseInput('-11', honor)).toMatchObject({ ok: false });
  expect(parseInput('2.5', honor)).toMatchObject({ ok: false, reason: 'Type a whole number.' });
  expect(parseInput('abc', honor)).toMatchObject({ ok: false });
  expect(parseInput('99', { ...honor, min: null, max: null })).toEqual({ ok: true, value: 99 });
  expect(parseInput('1', { ...honor, valueType: 'float' })).toMatchObject({ ok: false });
});

test('an edit is a create on an empty cell, a set or clear on a relationship, and nothing on a conflict', () => {
  const existing: Cell = { ties: [tie('r1', 'a', 'b', true)], value: { value: 1, own: true } };
  const conflict: Cell = {
    ties: [tie('r2', 'a', 'c', true), tie('r3', 'a', 'c', true)],
    value: null,
  };
  const { planned, skipped } = planOperations({
    edits: [
      { row: 'a', col: 'b', before: existing, value: 5 },
      { row: 'a', col: 'd', before: undefined, value: 2 },
      { row: 'a', col: 'e', before: undefined, value: null },
      { row: 'a', col: 'c', before: conflict, value: 9 },
    ],
    stat: 'honor',
    type: { id: 'ty', name: 'Honors' },
    directed: true,
    nameOf: (id) => id.toUpperCase(),
    versions: new Map([['r1', '"v1"']]),
  });
  expect(skipped).toEqual([cellKey('a', 'c')]);
  expect(planned.map((p) => p.operation.op)).toEqual(['set', 'create']);
  expect(planned[0]?.operation).toEqual({
    op: 'set',
    relationship_id: 'r1',
    stat_definition_id: 'honor',
    value: 5,
    if_match: '"v1"',
  });
  expect(planned[1]?.operation).toMatchObject({
    op: 'create',
    name: 'A - Honors - D',
    one_way: true,
    prototypes: ['ty'],
    is_public: false,
    stats: [{ stat_definition_id: 'honor', value: 2 }],
  });
});

test('the two cells of one two-way relationship are one operation, the later edit winning', () => {
  const both: Cell = { ties: [tie('r1', 'a', 'b', false)], value: null };
  const { planned } = planOperations({
    edits: [
      { row: 'a', col: 'b', before: both, value: 3 },
      { row: 'b', col: 'a', before: both, value: null },
    ],
    stat: 'trust',
    type: null,
    directed: false,
    nameOf: (id) => id,
    versions: new Map([['r1', '"x"']]),
  });
  expect(planned).toHaveLength(1);
  expect(planned[0]?.operation.op).toBe('clear');
  expect(planned[0]?.cells).toEqual([cellKey('a', 'b'), cellKey('b', 'a')]);
});

test('a save goes in batches of at most a hundred and the members in windows of a hundred', () => {
  expect(batches(Array.from({ length: 250 }, (_, i) => i)).map((b) => b.length)).toEqual([
    100, 100, 50,
  ]);
  expect(batches([])).toEqual([]);
  expect(windows(0)).toEqual([[0, 0]]);
  expect(windows(WINDOW + 1)).toEqual([
    [0, WINDOW],
    [WINDOW, WINDOW + 1],
  ]);
});

test('a scroll position shows only the cells it needs, and the keys move the focus inside the grid', () => {
  expect(visibleRange(0, 300, 30, 1000)).toEqual([0, 13]);
  expect(visibleRange(3000, 300, 30, 1000)).toEqual([97, 113]);
  expect(visibleRange(99_999, 300, 30, 50)).toEqual([50, 50]);
  const size = { rows: 5, cols: 4, page: 3 };
  expect(moveFocus({ row: 0, col: 0 }, 'ArrowUp', size)).toEqual({ row: 0, col: 0 });
  expect(moveFocus({ row: 1, col: 1 }, 'ArrowRight', size)).toEqual({ row: 1, col: 2 });
  expect(moveFocus({ row: 1, col: 1 }, 'End', size)).toEqual({ row: 1, col: 3 });
  expect(moveFocus({ row: 1, col: 1 }, 'Home', size)).toEqual({ row: 1, col: 0 });
  expect(moveFocus({ row: 3, col: 1 }, 'PageDown', size)).toEqual({ row: 4, col: 1 });
  expect(moveFocus({ row: 1, col: 1 }, 'x', size)).toBeNull();
});
