/** One segment of the year the strip draws: a month or a festival, with the days it has this year. */
export interface StripSegment {
  key: string;
  name: string;
  days: number;
  festival?: boolean;
}

/** A place on the strip: a segment and the day in it. */
export interface StripDay {
  key: string;
  name: string;
  day: number;
}

/** The days of the year, counted from 1 in the order of its segments. */
export function totalDays(segments: readonly StripSegment[]): number {
  return segments.reduce((sum, s) => sum + s.days, 0);
}

/** The place (1-based) of a segment's day on the strip, or null when the year has no such day. */
export function indexOf(
  segments: readonly StripSegment[],
  key: string,
  day: number,
): number | null {
  let before = 0;
  for (const s of segments) {
    if (s.key === key)
      return Number.isInteger(day) && day >= 1 && day <= s.days ? before + day : null;
    before += s.days;
  }
  return null;
}

/** The segment and day at a place on the strip; a place off the strip is held to its ends. */
export function dayAt(segments: readonly StripSegment[], index: number): StripDay | null {
  const total = totalDays(segments);
  if (!total) return null;
  let left = Math.min(total, Math.max(1, Math.round(index)));
  for (const s of segments) {
    if (left <= s.days) return { key: s.key, name: s.name, day: left };
    left -= s.days;
  }
  return null;
}

/** What a range says in words: "Any time", one day, or two. */
export function describe(
  segments: readonly StripSegment[],
  range: { from: number; to: number } | null,
): string {
  if (!range) return 'Any time';
  const from = dayAt(segments, range.from);
  const to = dayAt(segments, range.to);
  if (!from || !to) return 'Any time';
  const one = (d: StripDay) => `${d.name} ${d.day}`;
  return range.from === range.to ? one(from) : `${one(from)} to ${one(to)}`;
}

/** The place a handle moves to for a key, or null for a key that does nothing. */
export function keyTarget(key: string, value: number, total: number): number | null {
  const step: Record<string, number> = {
    ArrowLeft: -1,
    ArrowDown: -1,
    ArrowRight: 1,
    ArrowUp: 1,
    PageDown: -30,
    PageUp: 30,
  };
  let next: number;
  if (key === 'Home') next = 1;
  else if (key === 'End') next = total;
  else if (key in step) next = value + (step[key] ?? 0);
  else return null;
  return Math.min(total, Math.max(1, next));
}

/** The place on the strip a pointer at `fraction` (0 to 1) of its width stands on. */
export function placeAt(fraction: number, total: number): number {
  return Math.min(total, Math.max(1, Math.round(fraction * (total - 1)) + 1));
}

/** A range with its ends in order; moving one end past the other drags it along. */
export function moved(
  range: { from: number; to: number },
  which: 'from' | 'to',
  value: number,
): { from: number; to: number } {
  return which === 'from'
    ? { from: value, to: Math.max(value, range.to) }
    : { from: Math.min(value, range.from), to: value };
}
