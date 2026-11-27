// What the apps do around the strip, apart from drawing it: the strip's segments from a calculated
// year, a tick for each day something is dated on, and the period an Events read is asked for
// (ADR 0442). Pure, so Calendars and Social share one reading of it and the tests need no page.

import { dayAt, type StripSegment } from './strip';

/** A segment of a calculated year, as the API gives it (a month has an ordinal, a festival has none). */
export interface YearSegment {
  key: string;
  name: string;
  days: readonly unknown[];
  month_ordinal: number | null;
}

/** The strip's segments for a calculated year, in the calendar's order, festivals marked. */
export function stripOf(segments: readonly YearSegment[]): StripSegment[] {
  return segments.map((s) => ({
    key: s.key,
    name: s.name,
    days: s.days.length,
    festival: s.month_ordinal === null,
  }));
}

/** A date an entry has, as the API gives it. */
export interface DatedOn {
  calendar: string;
  year: number;
  segment: string | null;
  day: number | null;
}

/** The days of one calendar's year that something is dated on: a tick each on the strip. */
export function marksOf(
  dates: readonly DatedOn[],
  calendar: string,
  year: number,
): Array<[string, number]> {
  const marks: Array<[string, number]> = [];
  for (const d of dates) {
    if (d.calendar === calendar && d.year === year && d.segment && d.day !== null) {
      marks.push([d.segment, d.day]);
    }
  }
  return marks;
}

/** The period part of an Events read: the year, and the range on the strip when there is one. */
export interface PeriodQuery {
  dated_calendar_id: string;
  dated_year: number;
  dated_from_segment: string;
  dated_from_day: number;
  dated_to_segment: string;
  dated_to_day: number;
}

/**
 * What to ask `GET /events` so it keeps the Events dated in the strip's range, or nothing at all
 * without a calendar, a strip and a range: "any time" is no filter.
 */
export function periodQuery(
  calendar: string,
  year: number,
  strip: readonly StripSegment[],
  range: { from: number; to: number } | null,
): PeriodQuery | Record<string, never> {
  if (!range || !calendar || strip.length === 0) return {};
  const from = dayAt(strip, range.from);
  const to = dayAt(strip, range.to);
  if (!from || !to) return {};
  return {
    dated_calendar_id: calendar,
    dated_year: year,
    dated_from_segment: from.key,
    dated_from_day: from.day,
    dated_to_segment: to.key,
    dated_to_day: to.day,
  };
}
