// "2 hours ago", "yesterday": for a moment close enough that the clock time doesn't matter.
// Pure and dependency-free like format.ts; `now` is a parameter so a test can hold it still.
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

const UNITS: readonly (readonly [Intl.RelativeTimeFormatUnit, number])[] = [
  ['year', 365 * DAY],
  ['month', 30 * DAY],
  ['week', 7 * DAY],
  ['day', DAY],
  ['hour', HOUR],
  ['minute', MINUTE],
];

export function relativeTime(iso: string, now: Date = new Date(), locale = 'en'): string {
  const difference = new Date(iso).getTime() - now.getTime();
  const format = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });

  for (const [unit, size] of UNITS) {
    if (Math.abs(difference) >= size) return format.format(Math.round(difference / size), unit);
  }

  return 'just now';
}

// The full date and time, in the reader's own format: for the places that say when exactly, or
// carry it as a title behind a relativeTime.
export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString();
}
