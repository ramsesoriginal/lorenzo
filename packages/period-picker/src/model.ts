// What the picker chooses and how a choice changes, with no page and no API: so it can be tested
// alone (ADR 0323). A choice is a list of coordinates in a calendar; a range is only a gesture
// that fills that list with days, never something stored.

/** A day, a month or festival, or a whole year, in one calendar. */
export type Coordinate = {
  calendarId: string;
  year: number;
  /** The month or festival's stable key; absent for a year. */
  segment?: string;
  /** The day number; absent for a month or a year. */
  day?: number;
};

export type Granularity = 'year' | 'month' | 'day';

/** One chosen period, with the names needed to say what it is. */
export type Picked = {
  coordinate: Coordinate;
  calendarName: string;
  segmentName?: string;
  /** The period's id when it already exists; absent until the choice is saved. */
  periodId?: string;
};

/** The most periods one choice may hold: what one `PUT /entities/{id}/dates` accepts. */
export const MAX_SELECTION = 1000;

export type Mode = 'single' | 'multiple';

export function granularityOf(coordinate: Coordinate): Granularity {
  if (coordinate.day !== undefined) return 'day';

  return coordinate.segment !== undefined ? 'month' : 'year';
}

export function coordinateKey(c: Coordinate): string {
  return [c.calendarId, c.year, c.segment ?? '', c.day ?? ''].join('|');
}

export function isSelected(selection: readonly Picked[], coordinate: Coordinate): boolean {
  const key = coordinateKey(coordinate);

  return selection.some((picked) => coordinateKey(picked.coordinate) === key);
}

/** Adds the period, or removes it when it is already chosen; a single choice is replaced. */
export function toggle(selection: readonly Picked[], item: Picked, mode: Mode): Picked[] {
  const key = coordinateKey(item.coordinate);
  const has = selection.some((picked) => coordinateKey(picked.coordinate) === key);

  if (mode === 'single') return has ? [] : [item];

  return has
    ? selection.filter((picked) => coordinateKey(picked.coordinate) !== key)
    : [...selection, item];
}

/** Adds the periods that are not chosen yet, in order; never removes one. */
export function addAll(selection: readonly Picked[], items: readonly Picked[]): Picked[] {
  const keys = new Set(selection.map((picked) => coordinateKey(picked.coordinate)));
  const added = items.filter((item) => {
    const key = coordinateKey(item.coordinate);

    if (keys.has(key)) return false;

    keys.add(key);

    return true;
  });

  return [...selection, ...added];
}

export function remove(selection: readonly Picked[], coordinate: Coordinate): Picked[] {
  const key = coordinateKey(coordinate);

  return selection.filter((picked) => coordinateKey(picked.coordinate) !== key);
}

/** How many more periods the choice may take, and whether it is over. */
export function limit(selection: readonly Picked[]): { remaining: number; over: boolean } {
  return {
    remaining: Math.max(0, MAX_SELECTION - selection.length),
    over: selection.length > MAX_SELECTION,
  };
}

export type SegmentDays = { key: string; name: string; days: number[] };

export type DayRef = { segment: string; day: number };

/**
 * The days from `from` to `to` inclusive, in the order of the year's months and festivals and
 * whichever way round they were given. A day that is not in the year (a leap festival that is
 * absent) ends the range there: it returns nothing.
 */
export function daysBetween(segments: readonly SegmentDays[], from: DayRef, to: DayRef): DayRef[] {
  const all: DayRef[] = segments.flatMap((segment) =>
    segment.days.map((day) => ({ segment: segment.key, day })),
  );
  const index = (ref: DayRef) =>
    all.findIndex((d) => d.segment === ref.segment && d.day === ref.day);
  const a = index(from);
  const b = index(to);

  if (a < 0 || b < 0) return [];

  return all.slice(Math.min(a, b), Math.max(a, b) + 1);
}

/**
 * What a choice says in words, grouped so that it never reads as a span: "7 days in Frostmoon
 * 1100", a month or festival as itself, a year as the year. A calendar's name follows when the
 * choice has more than one calendar.
 */
export function summarize(selection: readonly Picked[]): string[] {
  const calendars = new Set(selection.map((picked) => picked.coordinate.calendarId));
  const lines: string[] = [];
  const days = new Map<string, { count: number; text: string }>();

  for (const picked of selection) {
    const { calendarId, year, segment } = picked.coordinate;
    const where = calendars.size > 1 ? ` (${picked.calendarName})` : '';

    switch (granularityOf(picked.coordinate)) {
      case 'year':
        lines.push(`Year ${year}${where}`);
        break;
      case 'month':
        lines.push(`${picked.segmentName ?? segment} ${year}${where}`);
        break;
      default: {
        const key = `${calendarId}|${year}|${segment}`;
        const group = days.get(key) ?? {
          count: 0,
          text: `${picked.segmentName ?? segment} ${year}${where}`,
        };

        group.count += 1;
        days.set(key, group);
      }
    }
  }

  for (const { count, text } of days.values()) {
    lines.push(`${count} ${count === 1 ? 'day' : 'days'} in ${text}`);
  }

  return lines;
}

/** The name the API gives a period, which the picker shows for one it has not saved yet. */
export function periodLabel(picked: Picked): string {
  const { year, day } = picked.coordinate;

  switch (granularityOf(picked.coordinate)) {
    case 'year':
      return `${picked.calendarName} ${year}`;
    case 'month':
      return `${picked.segmentName} ${year}`;
    default:
      return `${day} ${picked.segmentName} ${year}`;
  }
}
