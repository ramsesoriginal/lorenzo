# @lorenzo/time-filter

A strip of a calendar's year to look a list through, drawn once for the apps to share ([the calendars and sessions design](../../docs/design/web/calendars-sessions/README.md), CS2 and CS7). Calendars' Events list is the first user; Maps' date lens is the next.

It draws the brand's `.time-filter` (the strip, its segment bar, the ticks and the handles come from `apps/brand`), so it ships no stylesheet.

```ts
import { createTimeFilter } from '@lorenzo/time-filter';

const filter = createTimeFilter({
  segments: [{ key: 'frostwane', name: 'Frostwane', days: 30 }, { key: 'midwinter', name: 'Midwinter', days: 1, festival: true }],
  marks: [['frostwane', 12]], // the days something is dated on: a tick each, taller where there is more
  onChange: (range) => {}, // { from, to } as places on the strip (1 is the first day), or null for any time
});
host.append(filter.element);
```

- A range is two places on the year, counted from 1 over every segment in the calendar's order, festivals included. `indexOf` and `dayAt` turn a segment and day into a place and back.
- The ends are handles (`role="slider"`): drag across the strip, or Arrow keys (one day), Page Up and Page Down (thirty), Home and End. Moving one end past the other drags the other along.
- `mode: 'point'` is one handle for one date (the date lens on Maps and Locations): `onChange` gets `{ from, to }` with both the same place, or null.
- **Any time** clears the range. The filter narrows a list in the browser and changes nothing in the data; it infers no order from a date.

`mise run //packages/time-filter:test` covers the strip's arithmetic (places, words, keys, the pointer and the range's order); the control is covered by the end-to-end suite of Calendars.
