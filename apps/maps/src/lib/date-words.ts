// What the Maps list says of a Map seen through a date (ADR 0373), and the request the choice makes.
// Pure, so the page and the tests share it. It is always *tied to*, never *existed at*.
export type Tie = 'tied' | 'untied' | 'other';

export const TIE_WORDS: Record<Tie, string> = {
  tied: 'Tied to this date',
  untied: 'Not tied to a date',
  other: 'Tied to other dates',
};

export type DateChoice = { calendarId: string; year: number; segment?: string; day?: number };

/** The query a date makes on the Maps list; none when no date is chosen. */
export function dateQuery(choice: DateChoice | null, excludeOther: boolean) {
  if (!choice) return {};

  return {
    tied_calendar: choice.calendarId,
    tied_year: choice.year,
    ...(choice.segment !== undefined ? { tied_segment: choice.segment } : {}),
    ...(choice.day !== undefined ? { tied_day: choice.day } : {}),
    ...(excludeOther ? { exclude_other: true } : {}),
  };
}

/** *3 Maps left*, said when the Maps tied only to other dates are left out. */
export function leftWords(count: number): string {
  return `${count} ${count === 1 ? 'Map' : 'Maps'} left.`;
}
