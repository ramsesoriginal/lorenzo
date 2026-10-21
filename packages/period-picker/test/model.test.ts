import { describe, expect, it } from 'vitest';
import {
  addAll,
  type Coordinate,
  coordinateKey,
  daysBetween,
  granularityOf,
  isSelected,
  limit,
  MAX_SELECTION,
  type Picked,
  periodLabel,
  remove,
  type SegmentDays,
  summarize,
  toggle,
} from '../src/model';

const calendar = 'cal-1';

function day(d: number, segment = 'first', year = 3286, calendarId = calendar): Picked {
  return {
    coordinate: { calendarId, year, segment, day: d },
    calendarName: calendarId === calendar ? 'Pal-Vaz' : 'Other',
    segmentName: segment === 'first' ? 'First' : 'Festival',
  };
}

const segments: SegmentDays[] = [
  { key: 'first', name: 'First', days: [1, 2, 3] },
  { key: 'festival', name: 'Festival', days: [1, 2] },
  { key: 'second', name: 'Second', days: [1, 2] },
];

describe('coordinates', () => {
  it('know their granularity and a stable key', () => {
    const year: Coordinate = { calendarId: calendar, year: 1 };

    expect(granularityOf(year)).toBe('year');
    expect(granularityOf({ ...year, segment: 'first' })).toBe('month');
    expect(granularityOf({ ...year, segment: 'first', day: 4 })).toBe('day');
    expect(coordinateKey(year)).not.toBe(coordinateKey({ ...year, segment: 'first' }));
    expect(coordinateKey({ ...year, segment: 'first', day: 4 })).toBe('cal-1|1|first|4');
  });
});

describe('toggle', () => {
  it('adds and removes in a multiple choice', () => {
    const one = toggle([], day(1), 'multiple');
    const two = toggle(one, day(2), 'multiple');

    expect(two.map((p) => p.coordinate.day)).toEqual([1, 2]);
    expect(toggle(two, day(1), 'multiple').map((p) => p.coordinate.day)).toEqual([2]);
    expect(isSelected(two, day(2).coordinate)).toBe(true);
    expect(isSelected(two, day(3).coordinate)).toBe(false);
  });

  it('replaces in a single choice and clears when chosen again', () => {
    const one = toggle([], day(1), 'single');

    expect(toggle(one, day(2), 'single').map((p) => p.coordinate.day)).toEqual([2]);
    expect(toggle(one, day(1), 'single')).toEqual([]);
  });

  it('keeps days of different calendars apart', () => {
    const both = toggle(toggle([], day(1), 'multiple'), day(1, 'first', 3286, 'cal-2'), 'multiple');

    expect(both).toHaveLength(2);
  });
});

describe('addAll and remove', () => {
  it('adds only what is not chosen and never removes', () => {
    const start = [day(1)];

    expect(addAll(start, [day(1), day(2), day(2)]).map((p) => p.coordinate.day)).toEqual([1, 2]);
    expect(remove([day(1), day(2)], day(1).coordinate).map((p) => p.coordinate.day)).toEqual([2]);
  });
});

describe('limit', () => {
  it('says how many more fit and when it is over', () => {
    const many = Array.from({ length: MAX_SELECTION }, (_, i) => day(i + 1));

    expect(limit([]).remaining).toBe(MAX_SELECTION);
    expect(limit(many)).toEqual({ remaining: 0, over: false });
    expect(limit([...many, day(5000)]).over).toBe(true);
  });
});

describe('daysBetween', () => {
  it('runs through the months and festivals in order, either way round', () => {
    const forward = daysBetween(
      segments,
      { segment: 'first', day: 2 },
      { segment: 'festival', day: 1 },
    );

    expect(forward).toEqual([
      { segment: 'first', day: 2 },
      { segment: 'first', day: 3 },
      { segment: 'festival', day: 1 },
    ]);
    expect(
      daysBetween(segments, { segment: 'festival', day: 1 }, { segment: 'first', day: 2 }),
    ).toEqual(forward);
  });

  it('is one day for one day and nothing for a day the year lacks', () => {
    expect(
      daysBetween(segments, { segment: 'second', day: 2 }, { segment: 'second', day: 2 }),
    ).toEqual([{ segment: 'second', day: 2 }]);
    expect(
      daysBetween(segments, { segment: 'first', day: 1 }, { segment: 'first', day: 9 }),
    ).toEqual([]);
  });
});

describe('summarize', () => {
  it('groups days by month and never reads as a span', () => {
    const lines = summarize([day(1), day(2), day(3), day(1, 'festival')]);

    expect(lines).toEqual(['3 days in First 3286', '1 day in Festival 3286']);
  });

  it('names a month and a year as themselves, and the calendar when there are several', () => {
    const month: Picked = {
      coordinate: { calendarId: calendar, year: 3286, segment: 'first' },
      calendarName: 'Pal-Vaz',
      segmentName: 'First',
    };
    const year: Picked = {
      coordinate: { calendarId: calendar, year: 3287 },
      calendarName: 'Pal-Vaz',
    };

    expect(summarize([month, year])).toEqual(['First 3286', 'Year 3287']);
    expect(summarize([month, day(1, 'first', 1, 'cal-2')])).toEqual([
      'First 3286 (Pal-Vaz)',
      '1 day in First 1 (Other)',
    ]);
  });
});

describe('periodLabel', () => {
  it('matches the names the API gives a period', () => {
    expect(periodLabel(day(16))).toBe('16 First 3286');
    expect(
      periodLabel({
        coordinate: { calendarId: calendar, year: 3286, segment: 'first' },
        calendarName: 'Pal-Vaz',
        segmentName: 'First',
      }),
    ).toBe('First 3286');
    expect(
      periodLabel({ coordinate: { calendarId: calendar, year: 3286 }, calendarName: 'Pal-Vaz' }),
    ).toBe('Pal-Vaz 3286');
  });
});
