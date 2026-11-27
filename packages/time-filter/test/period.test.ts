import { describe, expect, it } from 'vitest';
import { marksOf, marksOfDays, periodQuery, segmentRange, stripOf } from '../src';

const year = [
  { key: 'frostwane', name: 'Frostwane', days: new Array(30).fill(0), month_ordinal: 1 },
  { key: 'midwinter', name: 'Midwinter', days: [0], month_ordinal: null },
  { key: 'thaw', name: 'Thaw', days: new Array(28).fill(0), month_ordinal: 2 },
];

describe('the strip of a calculated year', () => {
  it('has a segment for each month and festival, with its days, festivals marked', () => {
    expect(stripOf(year)).toEqual([
      { key: 'frostwane', name: 'Frostwane', days: 30, festival: false },
      { key: 'midwinter', name: 'Midwinter', days: 1, festival: true },
      { key: 'thaw', name: 'Thaw', days: 28, festival: false },
    ]);
  });
});

describe('the ticks of a strip', () => {
  const dated = [
    { calendar: 'a', year: 1200, segment: 'frostwane', day: 12 },
    { calendar: 'a', year: 1200, segment: 'frostwane', day: 12 },
    { calendar: 'a', year: 1199, segment: 'thaw', day: 3 },
    { calendar: 'b', year: 1200, segment: 'thaw', day: 4 },
    { calendar: 'a', year: 1200, segment: null, day: null },
  ];

  it('keeps the days of this calendar and this year that name a segment and a day', () => {
    expect(marksOf(dated, 'a', 1200)).toEqual([
      ['frostwane', 12],
      ['frostwane', 12],
    ]);
  });
});

describe('the period an Events read is asked for', () => {
  const strip = stripOf(year);

  it('is nothing for any time, and nothing without a calendar or a strip', () => {
    expect(periodQuery('a', 1200, strip, null)).toEqual({});
    expect(periodQuery('', 1200, strip, { from: 1, to: 2 })).toEqual({});
    expect(periodQuery('a', 1200, [], { from: 1, to: 2 })).toEqual({});
  });

  it('names the calendar, the year and the segment and day at each end of the range', () => {
    // Place 31 is the festival, place 32 the first day of Thaw.
    expect(periodQuery('a', 1200, strip, { from: 31, to: 32 })).toEqual({
      dated_calendar_id: 'a',
      dated_year: 1200,
      dated_from_segment: 'midwinter',
      dated_from_day: 1,
      dated_to_segment: 'thaw',
      dated_to_day: 1,
    });
  });
});

describe("marks from the year's dated days, and this month", () => {
  const segments = [
    { key: 'first', name: 'First', days: 10 },
    { key: 'fest', name: 'Feast', days: 2, festival: true },
    { key: 'second', name: 'Second', days: 5 },
  ];

  it('ticks each day by how many Events are on it, and none for a whole segment or year', () => {
    expect(
      marksOfDays([
        { segment: null, day: null, count: 1 },
        { segment: 'first', day: null, count: 2 },
        { segment: 'first', day: 3, count: 2 },
        { segment: 'second', day: 1, count: 9 },
      ]),
    ).toEqual([
      ['first', 3],
      ['first', 3],
      ['second', 1],
      ['second', 1],
      ['second', 1],
      ['second', 1],
    ]);
  });

  it('takes this month as the whole segment today is in, as places on the strip', () => {
    expect(segmentRange(segments, { segment: 'first', day: 4 })).toEqual({ from: 1, to: 10 });
    expect(segmentRange(segments, { segment: 'fest', day: 2 })).toEqual({ from: 11, to: 12 });
    expect(segmentRange(segments, { segment: 'second', day: 5 })).toEqual({ from: 13, to: 17 });
  });

  it('has no range when today is not in this year', () => {
    expect(segmentRange(segments, { segment: 'gone', day: 1 })).toBeNull();
    expect(segmentRange(segments, { segment: 'first', day: 11 })).toBeNull();
  });
});
