# Lorenzo Calendars

Lorenzo Calendars keeps the calendars of your worlds, shows them a year at a time, and lets you attach notes, Facts and Events to their dates. This guide is for game masters and authors. Developers will find the implementation detail in [`apps/calendars/README.md`](../../apps/calendars/README.md), and the decisions in [ADR 0308](../adr/0308-authored-calendars-and-calculation.md) to [0311](../adr/0311-calendar-documents-import-and-app.md).

## What a calendar is here

A calendar is an entry in a library or repository, with a definition of its own:

- **Months and festivals**, in order, each with a number of days. A festival sits outside the month numbering.
- **Weeks**, optionally: a length, weekday names and a reference day that fixes where the weekdays fall. Each month or festival says whether its days advance the week.
- **Moons**, optionally: a cycle in days and the day of a new moon. The calendar shows eight phases.
- **Leap months and festivals**: any month or festival can appear only every N years, from a chosen year offset. In the years where it does not appear, the days simply do not exist.

Years are whole numbers and may be zero or negative. A date is a position in this one calendar: a year, a month or festival, and a day. It is not an hour or a moment in time (see [Clocks](#clocks)), and each calendar keeps its own reckoning.

A new calendar starts empty. Preview checks the definition before it is saved, and a change that would invalidate dates or recurring observances already recorded is refused.

## Choose a library or repository

Log in and the page opens in one of your libraries. The **Library or repository** menu above the page switches to another, and Calendars remembers your last choice in this browser. The calendar list shows the calendars you are allowed to see in that library; an empty list can mean there are none or none for you.

## Browse a year

Open a calendar and a year. **Previous year**, **Next year** and the year field move between years.

Two views show the same dates:

- **Month or festival** shows one month or festival at a time; a menu chooses which.
- **Whole year** shows every month and festival in the order of the definition.

Each day shows its number, its weekday column when the calendar has weeks, the phase of each moon (hover for the name), a short extract of its notes, the names of Facts and Events dated to it, and any recurring observance. The year and view are part of the address, so a link keeps them. On a phone, choosing a date in the whole-year view opens its details with a **Back to calendar** control.

Browsing creates nothing. A date appears in the saved data only when someone adds something to it.

## Open a date

Choose a day to see its notes, the Facts and Events dated to it, and the observances that fall on it. **Open date entry** opens the full page for that day. If the panel says no notes or dated entries are available to you, none exist for that date or none are visible to you.

## Notes on a date, a month or a year

A note belongs to exactly the period it was added to. The year has its own notes (the **Year ...: notes and dated entries** button), each month or festival has its own (**Month or festival notes**), and each day has its own. A note on a month is not shown on its days, and a note on a year is not shown on its months. Broader notes never apply to every day beneath them.

Owners, Organizers and Authors of a library can add a note: choose **Add a note to this date**. The first time something is added, Calendars saves the day, together with its month and year, and no others. Notes are written in the same editor as elsewhere in Lorenzo, with text and pictures, and each note has an audience of its own.

## Facts and Events, and their dates

A **Fact** is a statement the library treats as canonical. An **Event** is something that happened in the story. Both are entries with notes of their own.

From an open date, authors can **Create a fact or story event** there, or **Associate an existing fact or event**. The entry's page lists its **Dates** and lets an author remove one (**Remove date association**). To give an existing entry another date, open that date in the calendar and choose the entry.

A date association says only that the entry is connected to that date. It does not say that the Event lasted the whole day, when anyone learned of it, or what caused what. Several dates on one entry are several dates, not a span, and an association with a month alone does not invent a day.

Events can also be created without a date, from the Events page.

## Recurring observances

An observance is something that recurs: a festival day, an anniversary, a holy day. From a day, an author chooses **Create a recurring observance** and gives a name, the month or festival, the day, **Every N years** and **Year offset**. It then appears on that date in every year the rule matches.

When a year does not contain the day, as with a leap festival, the observance is skipped that year; it is never moved. Observances are worked out when a year is shown and no occurrence is stored. An observance does not claim that any particular celebration took place: to record one, create an Event for it and give it that date. The recurrence can be edited on the observance's own page.

## Who can see what

Calendars, entries and notes each have an audience of their own, and all of them start restricted. New dates created through browsing are restricted too, and so is a new calendar unless its creation form says otherwise.

- An entry's audience decides who knows it exists and what it is called. Each note on it has its own audience, so a visible Event need not show its notes, and a shared note does not open the entry it belongs to.
- Events can also be limited to the players whose beings currently take part in them (**Participants**), or opened to **Everyone in this library**. Individual characters and groups can be named in addition.
- GMs, Authors and administrators have access through their role as well.

What a reader cannot see is left out without a placeholder or a count. Two readers of the same library can therefore see different things, and that is expected; it is how audiences work rather than a sign that something is wrong. Details are in [entities, knowledge and visibility](../domain/entities-knowledge-and-visibility.md).

## The Events page

**Browse Events** on the calendar list opens the Events page. It lists the Events you can see and searches their names (**Find Events**). **Create an Event** adds an Event or a Fact that starts undated, with a visibility of Restricted, Participants or Everyone in this library. Players can create Events and Facts and write notes of their own on entries they can see; authors and GMs manage the rest.

Events can be listed by **Name** or in **Story order**. Story order and the causal filters (under **Causes**, or **Participants and causes** for authors and GMs) use the recorded relationships the reader is allowed to see:

- On an Event's page, **Order and causes** lists the relationships recorded for it: happened before, happened after, caused, was caused by. Authors and GMs add them with **Add relationship**, and **Compare Events** says how two Events relate.
- Each relationship starts private. **Share relationship** makes it visible to readers who can see both Events, and **Make relationship private** reverses that. A hidden Event or private relationship never changes what another reader is shown.
- A reader sees only shared relationships between Events they can see. When no such path exists, an Event's place in the list is labelled *linearized*: it is a display order, not evidence of what happened first. Different readers can get different display orders.
- Dates never create these relationships.

An Event's page also records which beings took part in it, and, for authors and GMs, optionally when a being learned of it (**Learning**). Each is a separate record, and neither follows from a date or a relationship.

## Clocks

A calendar dates the story in days. A **Clock** is a separate, optional entry for a flow of time of its own, such as a place where time runs faster. **Browse clocks** on the calendar list opens the Clocks page, which lists them and, for authors and GMs, creates one (**Create a clock**). A clock is ticking, or declared **timeless**; a library with no clocks works as before.

- **Reckonings.** On a ticking clock, **Clock and calendar reckonings** pairs the start of one date in a calendar with an exact reading of the clock. A clock can have several.
- **Readings.** On an Event, **Clock readings** records an exact value, a range or a calendar day (through a reckoning). Numbers may be fractions such as `1/3`.
- **Ratios.** **Clock relationships and conversion** pairs two ticking clocks with a constant ratio and, optionally, two anchor readings. Without anchors only durations convert. **Read this Event on another clock** then shows a derived reading, with the path it came by.

A derived reading is worked out when it is asked for and never saved as an entered one. Its status is **Entered**, **Derived**, **Not reckoned** (nothing to go on), **Conflicting** (recorded readings or relationships disagree; entered readings win) or **Limit reached** (too large to compute; nothing is guessed). Readings, reckonings and relationships start private and are shared on purpose, and a reader sees only those whose ends they can see. None of this creates order, cause or knowledge, and none of it follows from a date.

## Links in text

In any text written in LorenzoScript, a link name points at an entry: `[[calendar/reckoning]]` for a calendar, `[[event/arrival]]` for an Event, `[[calendar_period/first-day]]` for a dated period. A calendar date can also be written as a computed link:

| Written as | Opens |
| --- | --- |
| `{{cal reckoning 3286}}` | the year 3286 |
| `{{cal reckoning 3286/Quirm}}` | the month or festival named Quirm |
| `{{cal reckoning 3286/6/16}}` | day 16 of the sixth month or festival |
| `{{cal reckoning 3286/Quirm/16}}` | day 16 of Quirm |

Numbers count every month and festival in the order of the definition, including leap ones that are absent in that year, so a later month keeps its number. A name must match one month or festival; capitals do not matter. Use `key:segment-6` for a stable key or `name:123` for a name that is a number, and write `%2F` for a slash inside a name. A computed link opens a date as calculated, creates nothing, and reveals nothing hidden. A link to something missing or not visible to the reader stays plain text.

## Import with the command line

Calendars has no import screen. The `lorenzo calendar import` command reads a native calendar file, previews what it would change with `--dry-run`, and applies it only after the reviewed plan is confirmed. Repeating an import creates no duplicates, and imported audiences stay restricted unless chosen otherwise. Notes arrive on their dates, so look for them in the year and month they came from. The file format is in [Native calendar files](calendar-file-format.md); the command itself is in the [CLI README](../../apps/cli/README.md#calendar-files), which also covers converting a saved donjon export.

## What Calendars does not do

- It has no "today". There is no current story date, and no calendar or clock is assumed: clocks are optional and explicit.
- It does not change a clock's rate over time, branch or loop time, or work out a clock's reading from anything but readings and relationships someone entered.
- It never works out order or cause from dates. Dates, Sessions and Scenes do not create "happened before" or "caused" relationships; only people do, and only by recording them.
- It does not infer that anyone knew something because of a date.
- It does not show the state of the world as of a date.
- It does not keep private notes in the browser for offline use.

For preparing and recording sessions against these calendars, see [Lorenzo Sessions](sessions.md).
