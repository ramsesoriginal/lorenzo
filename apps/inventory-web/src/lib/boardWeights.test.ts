import { describe, expect, it } from 'vitest';
import {
  carriedWeight,
  columnLine,
  dropVerdict,
  shownNumber,
  totalWeight,
  weightLine,
  weightOf,
  withUnit,
} from './boardWeights';
import type { ItemInstance } from './types';

describe('weightOf and totalWeight', () => {
  it('weighs a stack by its quantity, and counts the unweighed as nothing', () => {
    expect(weightOf({ weight: 1, quantity: 6 })).toBe(6);
    expect(weightOf({ weight: 2, quantity: null })).toBe(2);
    expect(weightOf({ weight: null, quantity: 3 })).toBeNull();
    expect(
      totalWeight([
        { weight: 3, quantity: 1 },
        { weight: 1, quantity: 6 },
        { weight: null, quantity: 1 },
      ]),
    ).toBe(9);
  });
});

describe('weightLine', () => {
  it('says only the weight with no limit', () => {
    expect(weightLine(5, null, 'lb')).toBe('5 lb');
    expect(weightLine(5, null, null)).toBe('5');
  });

  it('says how much room is left, full, or over', () => {
    expect(weightLine(3, 4, 'lb')).toBe('3 of 4 lb · 1 lb free');
    expect(weightLine(12, 12, 'lb')).toBe('12 of 12 lb · full');
    expect(weightLine(14, 12, 'lb')).toBe('14 of 12 lb · 2 lb over');
  });
});

describe('numbers', () => {
  it('are written as people write them', () => {
    expect(shownNumber(2.5)).toBe('2.5');
    expect(shownNumber(2.504)).toBe('2.5');
    expect(shownNumber(3)).toBe('3');
    expect(withUnit(2.5, 'kg')).toBe('2.5 kg');
  });
});

describe('columnLine', () => {
  it('puts the weight first and where the column is after it', () => {
    const fixed = { fixed: true, dropTarget: 'being', note: null, title: 'Equipped' };

    expect(columnLine(fixed, '5 lb', 'Imani')).toBe('5 lb · Imani holds these');
    expect(columnLine({ ...fixed, dropTarget: null, title: 'Not carried' }, '10 lb', 'Imani')).toBe(
      '10 lb · Set down',
    );
    expect(
      columnLine(
        { fixed: false, dropTarget: 'bag', note: 'Imani has these', title: 'Backpack' },
        '12 of 12 lb · full',
        'Imani',
      ),
    ).toBe('12 of 12 lb · full · Imani has these');
    expect(
      columnLine({ fixed: false, dropTarget: null, note: null, title: 'Chest' }, '3 lb', null),
    ).toBe('3 lb');
  });
});

describe('carriedWeight', () => {
  it('adds up the columns the being carries', () => {
    const column = (carried: boolean, weight: number) =>
      ({ carried, items: [{ weight, quantity: 1 }] }) as never;

    expect(carriedWeight({ columns: [column(true, 5), column(false, 10), column(true, 12)] })).toBe(
      17,
    );
  });
});

describe('dropVerdict', () => {
  const item = (title: string, weight: number | null, quantity = 1): ItemInstance =>
    ({ entity_id: title, title, weight, quantity, prototype_ids: [] }) as unknown as ItemInstance;
  const base = { unit: 'lb', columnName: 'Backpack', joins: null };

  it('says what a column would weigh with it', () => {
    expect(
      dropVerdict({ ...base, moved: [item('Lantern', 3)], there: [item('Rope', 10)], limit: null }),
    ).toEqual({ kind: 'ok', text: 'Makes 13 lb' });
  });

  it('says it against a limit', () => {
    expect(
      dropVerdict({ ...base, moved: [item('Lantern', 3)], there: [item('Rope', 6)], limit: 12 }),
    ).toEqual({ kind: 'ok', text: 'Makes 9 of 12 lb' });
  });

  it('refuses what is too heavy, with the sum', () => {
    expect(
      dropVerdict({ ...base, moved: [item('Anvil', 5)], there: [item('Rope', 10)], limit: 12 }),
    ).toEqual({
      kind: 'refuse',
      text: 'Too heavy: the backpack holds 12 lb, this would make 15',
    });
  });

  it('says when it joins a stack', () => {
    expect(
      dropVerdict({
        ...base,
        moved: [item('Rations', 1, 2)],
        there: [item('Rations', 1, 6)],
        limit: null,
        joins: item('Rations', 1, 6),
      }),
    ).toEqual({ kind: 'join', text: 'Joins Rations × 6, making 8' });
  });

  it('has nothing to add when nothing weighs anything', () => {
    expect(dropVerdict({ ...base, moved: [item('Note', null)], there: [], limit: null })).toEqual({
      kind: 'ok',
      text: 'Goes here',
    });
  });
});
