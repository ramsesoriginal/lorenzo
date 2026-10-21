# 0323 - One calendar-period picker

Status: accepted, decided with the maintainer on 2026-10-22. Builds on ADR 0308, 0309 and 0317; its reads are ADR 0324.

## Context

Sessions has four copies of a period picker (`views.ts` twice, `scenes.ts`, `context.ts`). Each loads every `calendar_period` entry of the library into one flat `<select>` or checkbox list. An entry reads only `id`, `name`, `kinds` and `parent_ids`, so a list mixes years, months and days of every calendar, names such as "3 Frostmoon 1100" collide across calendars, and a manager's page load asks for the list three times. A day nobody has saved yet cannot be chosen at all, because only saved periods are listed. Calendars browses periods through its own year, month and day grid and has no picker.

Three rules already bind any picker. The web apps render the API's `YearPreview` and run no second calendar evaluator ([ADR 0308](0308-authored-calendars-and-calculation.md)). Browsing creates no rows, periods exist only through explicit writes, and several selected days never imply a continuous span ([ADR 0309](0309-calendar-periods-events-and-date-associations.md), [ADR 0317](0317-sessions-scenes-and-collaborative-planning.md)). Creating a period requires write access to the calendar entry, which a Session GM does not generally have.

## Decision

- **A package, `packages/period-picker`**, plain TypeScript with the brand's classes and no framework, used by Sessions and by any Calendars screen that selects a period. ADR 0098's second-consumer rule is met by the four sessions copies. It reads through `packages/api-client`.
- **One control with four modes**: a day, a month or festival, a year, or several of these. It moves from a calendar (a select, only when there is more than one) to a year (a number field with previous and next) to the year's months and festivals and then their days, drawn from `YearPreview`, the layout of Bench's calendar screen. A saved period is marked in words ("has notes", "saved") as well as by style.
- **The value is an explicit list of period coordinates**: calendar, signed year, and optionally segment key and day, at mixed granularity. A month or a year chosen as such stays a month or a year period; it is never expanded into its days.
- **A range is a gesture, not a value.** Choosing a first and a last day inside one calendar selects the days between them as an explicit list, shows how many days that is and how many periods saving would create, and stops at 1000, the limit of `PUT /entities/{id}/dates`. Nothing records that the days were chosen as a range. A saved set is shown grouped by month ("7 days in Frostmoon 1100"), never as "from X to Y".
- **Existing and unsaved days.** The picker lists every day of the year's preview. A day with no saved period is selectable when the person can write to the calendar; saving then creates it, and its parents, through the existing explicit write (or the batch write of ADR 0324). Otherwise the day is disabled with the reason, "Only someone who can edit this calendar can add this date". A Session start and a Scene period are single selections; "Game time covered" is a multiple selection.
- **A selected period is shown by name and coordinates**, with its calendar's name, read in one request from ADR 0324, so a name never has to be unique to be understood.
- **No writes while browsing.** The picker creates no period before the consumer's save, and prefetch never creates one ([ADR 0313](0313-event-participation-browsing-and-calendar-addresses.md)).
- **Consumers.** The four sessions pickers are replaced. Calendars adopts the picker where it needs to add a date to an entry (the entry page lists and removes dates today but does not add one); if that turns out to need no new control, Calendars is left alone.

## Not in scope

A stored range or interval; a "today" date; selecting across calendars in one control; changing how a date association means "associated with" and nothing more.

## Consequences

- One loading path and one set of tests for the control that four screens had copied.
- The flat entity lists and their repeated requests disappear from Sessions.
- A Session GM without calendar access can choose only dates that already exist and sees why the others are unavailable.
- The package owns the 1000-day cap and its wording; a consumer cannot offer more.
