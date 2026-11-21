import { describe, expect, it } from 'vitest';
import {
  carriedWeight,
  columnLine,
  shownNumber,
  totalWeight,
  weightLine,
  weightOf,
  withUnit,
} from './boardWeights';

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
