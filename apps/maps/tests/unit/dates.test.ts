import { describe, expect, it } from 'vitest';
import { dateQuery, leftWords, TIE_WORDS } from '../../src/lib/date-words';

describe('the words of the date lens', () => {
  it('says tied to, never existed at', () => {
    expect(TIE_WORDS).toEqual({
      tied: 'Tied to this date',
      untied: 'Not tied to a date',
      other: 'Tied to other dates',
    });
    for (const words of Object.values(TIE_WORDS)) expect(words).not.toMatch(/existed/i);
  });

  it('asks for nothing without a date, and for coordinates with one', () => {
    expect(dateQuery(null, false)).toEqual({});
    expect(dateQuery(null, true)).toEqual({});
    expect(dateQuery({ calendarId: 'c', year: -5 }, false)).toEqual({
      tied_calendar: 'c',
      tied_year: -5,
    });
    expect(dateQuery({ calendarId: 'c', year: 3286, segment: 'first', day: 16 }, true)).toEqual({
      tied_calendar: 'c',
      tied_year: 3286,
      tied_segment: 'first',
      tied_day: 16,
      exclude_other: true,
    });
  });

  it('says how many are left', () => {
    expect(leftWords(1)).toBe('1 Map left.');
    expect(leftWords(4)).toBe('4 Maps left.');
  });
});
