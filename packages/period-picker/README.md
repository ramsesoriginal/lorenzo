# @lorenzo/period-picker

One control for choosing a calendar period: a day, a month or festival, a year, or several of them ([ADR 0323](../../docs/adr/0323-the-calendar-period-picker.md)). Sessions uses it for a Session's start, a Scene's period and the game time a Session covers (it replaces four flat lists of every period in a library), and Maps for its date lens. It ships its source and a stylesheet, and uses the brand's classes for everything else.

## Using it

```ts
import { createPeriodPicker } from '@lorenzo/period-picker';
import '@lorenzo/period-picker/period-picker.css';

const picker = createPeriodPicker({
  client, // a @lorenzo/api-client client
  tenantId,
  mode: 'multiple', // or 'single'
  canCreate: true, // may the person write to calendars?
  initial: session.period_ids, // periods already chosen, by id
  label: 'Game time covered',
  onChange: (selection) => {},
});

host.append(picker.element);
await picker.ready;

// When the person saves:
const periodIds = await picker.resolve(); // creates the days that do not exist yet
```

## What it does

- **Browses without writing.** It reads a year as the API calculates it (`GET .../years/{year}`) and the periods that exist (`GET .../calendar-periods`, ADR 0324); no calendar rules run in the browser ([ADR 0308](../../docs/adr/0308-authored-calendars-and-calculation.md)). Nothing is created until `resolve()`, which is one batch write per calendar (`POST .../periods/batch`).
- **A choice is a list of coordinates** (calendar, signed year, and optionally month or festival and day), at mixed granularity. Choosing a month or a year chooses that month or year, never its days.
- **A range is a gesture.** "Choose a range of days" fills the list with the days from the first to the last, within the year shown and across its months and festivals. It stores nothing about the range, and the chosen periods are described grouped by month ("7 days in Frostmoon 1100"), never as a span ([ADR 0309](../../docs/adr/0309-calendar-periods-events-and-date-associations.md)).
- **At most 1000 periods**, the limit of what one write to an entry's dates accepts; over it, the picker says so.
- **A day that does not exist yet** can be chosen when `canCreate` is true. When it is false (the person cannot edit the calendar) the day is disabled and the picker says why; days that already exist stay available.
- It opens on the year a calendar is anchored to, where it has one, else year 0; calendars have no "today".

## Tests

`mise run //packages/period-picker:test` covers the choice's rules (toggle, single and multiple, range, the limit, how a choice reads in words). The control itself is covered by the end-to-end suites of the apps that use it.
