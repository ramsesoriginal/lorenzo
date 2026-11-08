import { expect, it, describe as suite } from 'vitest';
import { dayAt, describe, indexOf, keyTarget, moved, placeAt, totalDays } from '../src/strip';

const year = [
  { key: 'a', name: 'Frostwane', days: 30 },
  { key: 'f', name: 'Midwinter', days: 1, festival: true },
  { key: 'b', name: 'Thaw', days: 28 },
];

suite('the strip', () => {
  it('counts every segment in order, a festival included', () => {
    expect(totalDays(year)).toBe(59);
  });
  it('places a day and reads it back', () => {
    expect(indexOf(year, 'a', 1)).toBe(1);
    expect(indexOf(year, 'f', 1)).toBe(31);
    expect(indexOf(year, 'b', 28)).toBe(59);
    expect(dayAt(year, 31)).toEqual({ key: 'f', name: 'Midwinter', day: 1 });
    expect(dayAt(year, 32)).toEqual({ key: 'b', name: 'Thaw', day: 1 });
  });
  it('has no place for a day the year lacks, and holds a place to the ends', () => {
    expect(indexOf(year, 'a', 31)).toBeNull();
    expect(indexOf(year, 'gone', 1)).toBeNull();
    expect(dayAt(year, 500)?.day).toBe(28);
    expect(dayAt(year, -4)?.day).toBe(1);
    expect(dayAt([], 1)).toBeNull();
  });
  it('says a range in words', () => {
    expect(describe(year, null)).toBe('Any time');
    expect(describe(year, { from: 3, to: 3 })).toBe('Frostwane 3');
    expect(describe(year, { from: 3, to: 32 })).toBe('Frostwane 3 to Thaw 1');
  });
  it('moves a handle by key and stops at the ends', () => {
    expect(keyTarget('ArrowRight', 5, 59)).toBe(6);
    expect(keyTarget('ArrowLeft', 1, 59)).toBe(1);
    expect(keyTarget('PageUp', 50, 59)).toBe(59);
    expect(keyTarget('Home', 20, 59)).toBe(1);
    expect(keyTarget('End', 20, 59)).toBe(59);
    expect(keyTarget('x', 20, 59)).toBeNull();
  });
  it('maps a pointer to a place and keeps the ends of a range in order', () => {
    expect(placeAt(0, 59)).toBe(1);
    expect(placeAt(1, 59)).toBe(59);
    expect(placeAt(2, 59)).toBe(59);
    expect(moved({ from: 5, to: 10 }, 'from', 20)).toEqual({ from: 20, to: 20 });
    expect(moved({ from: 5, to: 10 }, 'to', 2)).toEqual({ from: 2, to: 2 });
    expect(moved({ from: 5, to: 10 }, 'to', 12)).toEqual({ from: 5, to: 12 });
  });
});
