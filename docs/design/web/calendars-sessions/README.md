# Calendars and Sessions: design

A fresh design of Lorenzo Calendars and Lorenzo Sessions, together, from the jobs people do there. The system they are built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub ([account-hub](../account-hub/README.md)) and Writing ([writing](../writing/README.md)) are decided. This page holds the brief, the questions and the decision log for this pair.

Status: the brief is answered and a direction is chosen (CS1 to CS6). The prototype is built and ready for review.

## What the two apps are for

They are two apps that talk about the same thing from two sides: **when**.

- **Calendars** holds the world's time. A calendar is authored (months, festivals, weeks, moons, leap rules) and the API calculates it. On it sit Events, Facts and recurring observances, how Events are ordered and caused, who took part, who learned what, and optional clocks. It is where a world's history is read and written.
- **Sessions** holds the table's time. A Session belongs to one campaign, with a real-world date, an in-world starting period, GMs and players. A GM prepares it with reusable Scenes and notes, then records what was played. A person can also write down the order in which a being lived through Events.

The two meet in three places: a Session starts at a calendar period and covers others; a played Scene presents an Event; a reusable Scene may be tied to a period. Each link is something a person states. None is inferred. Sources: [the Calendars README](../../../../apps/calendars/README.md), [the Sessions README](../../../../apps/sessions/README.md), [v1.0.md](../../../../v1.0.md), [RFC 0046](../../../rfcs/0046-sessions-scenes-and-lived-order.md), and ADRs [0308](../../../adr/0308-authored-calendars-and-calculation.md) to [0326](../../../adr/0326-moon-phases-in-the-icon-atlas.md).

Scene is a kind shared with Writing: a reusable narrative identity that Sessions play and Writing tells. A Session appearance and a Writing telling are separate things with separate audiences.

## The jobs

Ordered by who arrives and what they need in the first minute.

### Calendars

| Who | The job | Needs from the data |
| --- | --- | --- |
| A reader | Find a date; see what happened on it, what recurs, which moon it is | the calendar, a year, permitted day notes, dated entries, observances, moon phases |
| A reader | Follow a story: browse Events, their order and causes | permitted Events, shared relationships, story order (linearized where nothing is recorded) |
| A reader | Read one Event on another clock | the readings and relationships they can see |
| A player | Add an Event or Fact, and notes on what they can see | their own entries, their own notes |
| An Author or GM | Write the world's history: periods, Events, Facts, associations, observances | the period, its Information, Fact and Event kinds |
| An Author or GM | Say how Events relate: happened before, caused, shared or private | order assertions, sharing, who may see both ends |
| An Author or GM | Record who took part and who learned what | participation, learning records, groups made from participants |
| An Author | Define a calendar: segments, weeks, moons, leap rules, with a preview | the definition, its version, what existing periods forbid |
| An Author | Clocks: a ticking or timeless clock, reckonings, readings, ratios | exact values, relationships, conversion paths |

### Sessions

| Who | The job | Needs from the data |
| --- | --- | --- |
| A player | See my Sessions, when and where, and what the GM shared | Sessions I am assigned to, shared notes |
| A GM | Plan a Session: details, roster, who plays whom, Scenes and their order | the Session, players and controlled Characters, appearances |
| A GM | Keep notes: for me, for GMs, for the group | note audiences |
| A GM | Reuse Scenes: create, link Facts, Events and Beings, tie to periods | reusable Scenes, their references |
| A GM | Record play: propose the outline as played, review, save; skipped Scenes; Events presented | played order, appearance status, presentations |
| A GM | Order the campaign's Sessions | the campaign sequence for the Sessions I manage |
| A player or GM | Write down a being's lived order of Events | the being's participations, lived-before evidence |

Roles in play: Author, GM, player, full-visibility Owner or Organizer, and a reader with no extra role. A GM role in any campaign is enough to manage Events and Facts in the library. A Session GM is assigned to one Session.

## What stays true, whatever it looks like

Rules about behaviour and honesty, not about pictures. They hold in any direction.

- **A date never makes an order.** Real-world dates, calendar dates and `created_at` are never evidence of Event order, lived order, learning or cause. Where nothing is recorded, an order is shown as linearized and is labelled so.
- **Nothing is inferred.** No Event happened because a Scene mentions it. No one learned something because they took part. A note, a reference, a Session's start period and a play record create no Events, participation, learning or causes. An empty list means nothing is recorded, not that nothing happened.
- **Sharing is explicit and starts private.** Order assertions, relationships, readings, reckonings and presentations start private. Sharing one never opens the Events or Information at its ends. A reader needs access to both ends.
- **A hidden thing is never counted or implied** (D24). No placeholder, rank, count or pagination gap reveals a hidden Event, and a hidden Event in the middle of a path is never mentioned. Different readers may see different linearized orders.
- **Planned and played are separate.** Preparation edits never rewrite what was recorded as played. Skipped and partial play stay as recorded; nothing completes them.
- **A Session's order is the GM's to set for the Sessions they manage.** Inaccessible Sessions keep their places and are not shown.
- **Browsing creates nothing.** Opening a date or a clock creates no period or reading. A period is made only when a person writes something on it.
- **A calendar counts every segment** in authored order, festivals and absent leap segments included. A moon phase has a symbol, a name and an accessible description; the symbol is never the only carrier.
- **Notes have audiences:** me, the Session's GMs, the Session's participants. Never the whole library. Removing someone from the roster removes that route.
- **A secret is shown once** (D27, where one appears), **a dead link says one thing,** and **the API decides every permission.**
- **Words** follow identity §14.3 and the ADRs: calendar, period, segment, Event, Fact, observance, clock, reading, reckoning, Session, Scene, appearance, played, skipped, GM, player.

## Visual or structural decisions in the old documents

Named here so each can be kept or dropped on purpose. None carries over by default.

| From | What it decided | The question |
| --- | --- | --- |
| ADR 0322 | The two apps share a header and the brand base, and are separate apps | Do they stay two apps, linked by data and the palette (D16)? |
| ADR 0311 | A calendar and a year are chosen first; **Month or festival** and **Whole year** are tabs of one view | Does the year view keep that shape? |
| ADR 0311 | A month cell shows day-note snippets, dated entry names, observances and a moon symbol | Does a day carry that much? |
| ADR 0311 | On a phone, a date in the whole year opens a panel with Back to calendar | Does the day panel stay a panel? |
| ADR 0315 | **Order and causes** is an action on an Event page | Does it stay an action, or become a view? |
| ADR 0313 | An **Events** page lists Events with participant, causal and story-order filters | Where do Events live? |
| ADR 0320 | **Browse clocks** is a page of its own, and clocks are optional | Where do clocks live? |
| ADR 0317 | **Browse reusable scenes** is a page reached from a Session | Where do reusable Scenes live? |
| Sessions README | The Session page is drawn in regions that redraw on their own | Does the Session stay one page of regions? |
| ADR 0318 | Preparation and recorded play are two lists on the Session | Do they stay together, or become two modes? |
| ADR 0319 | Personal lived order is a page reached from a being | Where does it live? |

## A gap to settle first

The shell's status bar shows an **in-world date** (D18). A campaign has no *current* in-world date in the data: "today" is [not built](../../../../apps/calendars/README.md). What exists is a Session's in-world **starting period**. The bar can show that, for the Session being looked at, or nothing. A campaign-wide "now" would be new, and would need its own decision. Question 1 asks.

## Questions

1. **How do the two apps relate, and what is the in-world date?**
   - **A. Two apps, linked by data.** Each has its own Home. A Session links to its starting period and the periods it covers; a calendar day lists the Sessions that start or cover it; an Event lists where it was presented. The status bar shows the in-world date of the Session you are looking at, and nothing elsewhere.
   - **B. A shared date lens.** As A, and a library-wide "looking at" date you set, carried between the apps and shown in the status bar. It filters nothing by default and infers nothing.
   - **C. A campaign "now".** As B, but a campaign keeps a stated current date that a GM advances. This is new data and needs an ADR.
2. **The calendar's main view.** Three directions to draw:
   - **A. The month.** A grid, as the classic wall calendar, with a year strip above it. Festivals and absent segments sit in the sequence.
   - **B. The whole year as one surface.** Every segment as a row of days in definition order, with marks for what is on each day (notes, Events, observances, moons). You zoom into a day.
   - **C. A line of time.** A scrolling timeline of periods and Events, with the calendar's segments as the ruler. The grid is one zoom of it.
3. **Where Events live.** Events are read in the calendar and followed by order and cause.
   - **A. Events are a tab of Calendars:** a list with filters and story order; Order and causes opens from an Event.
   - **B. Events are their own place, "Story":** a page of ordered Events, with the causal graph as a view, and the calendar as one lens on it.
   - **C. Events are everywhere they are met:** on a day, in a Session, in a Scene; one Event page they all open.
4. **The Session's shape.**
   - **A. One page of regions** (as today): details, roster, notes, references, game time, Scenes, played order.
   - **B. Two modes, Prepare and Played,** like Write and Read in Writing: the same Session, with the outline editable in one and the record in the other; notes in both.
   - **C. The campaign first:** a track of the campaign's Sessions in order, with the Session you open beside it.
5. **Old decisions.** From the table above: which carry over? "All except …" is a good answer.

## Decision log

Decided with the maintainer, 2026-11-05, from the brief above.

### CS1. Two apps, linked by data

Calendars and Sessions stay two apps, each with its own Home (D16). A Session links to its starting period and the periods it covers. A calendar day lists the Sessions that start or cover it. An Event lists where it was presented. The status bar shows the in-world date of the Session being looked at, and nothing elsewhere. There is no campaign-wide "now". Turned down: a shared date lens (B) and a campaign "now" (C).

### CS2. The calendar's main view is the month

A grid with a year strip above it; festivals and absent segments sit in the sequence. **The line of time (C) is also wanted, as a component other apps share:** a time filter, drawn once, that a list or a map can be looked at through (the date lens on Maps and Locations is the first user). It is designed here as that component and is not the calendar's main view. Turned down: the whole year as one surface as the main view (B). A year view stays available as the second view (see the old decisions).

### CS3. Events are a tab of Calendars

A list with participant, causal and story-order filters. Order and causes opens from an Event. Turned down: a place of its own (B) and Events everywhere with no home (C).

### CS4. The Session is one page of regions, and a person chooses which to show

The Session stays one page of regions (details, roster, notes, references, game time, Scenes, played record, campaign order, lived order). Each region can be hidden and shown, and the choice is remembered per person. **Prepare** and **Played** are not modes but saved views of those switches (D22): Prepare shows the details, roster, notes and Scenes; Played shows the played record and the notes. A person can make others. Hiding a region hides only the drawing; nothing is deleted and nothing about permissions changes.

### CS5. The old decisions

All as recommended: two apps (CS1); the month as the main view with a Whole year view second (CS2); a month cell shows the moon, up to two marks and "+N", with the rest in the day panel; the day panel is a bottom sheet on a phone (D26); Order and causes stays an action on an Event; Events are a tab (CS3); **Clocks are a tab of Calendars,** shown only when the library has clocks; **Scenes are a tab of Sessions;** **lived order is a tab of Sessions,** with the being chosen there and Beings linking to it. The Session page's regions and the two record lists follow CS4.

### CS6. The month is A; the Session page is C

**The month** is direction A: a calm grid with the day panel docked beside it, and a strip of segments above. On a narrow window the panel is a sheet. **The Session page** is direction C: no bar of switches, a View menu that lists the views and the parts, and regions that fold. A line at the foot says what is hidden. Turned down: the month with an agenda (B), and the Session with a bar of switches (A) or a rail (B).

## The directions (drawn; A for the month and C for the Session chosen)

In `directions/`: the month view in two ways and the Session page in three, on the shell, with made-up data. Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/calendars-sessions/directions/index.html
```

The controls bar switches the direction and the view (All, Prepare, Played). The region switches on the Session page work. Screens are in `directions/screens/` (11 images). In the Session directions the status bar shows the in-world date of the Session (CS1); on the calendar it shows none.

**The month** (CS2). Both have a strip or rail of segments with a density mark, festivals and an absent leap day in the sequence, a moon on each day, and no "today".

| | A. Grid and panel | B. Grid and agenda |
| --- | --- | --- |
| Idea | A calm grid with a day panel docked beside it | A fuller grid over a list of what is on in the month |
| Day | The moon, up to two marks, "+N"; the rest in the panel | The moon and up to two lines of text; the rest in the list below |
| Segments | A strip across the top | A rail down the left (hidden on a narrow window) |
| Narrow window | The panel becomes a sheet | The list is the panel; a day opens in it |
| Cost | The panel is always open, so the grid is narrower | A tall page; the grid is read before the detail |

**The Session page** (CS4). All three show the same nine regions, hidden and shown by the person, with Prepare and Played as saved views.

| | A. Switches above | B. A rail | C. Folds and a View menu |
| --- | --- | --- | --- |
| Idea | A bar of switches over the page, one per region, and the views | A rail of the parts beside the page, each with an eye, and the views at its top | No bar; a View menu lists the views and the parts, and each region folds |
| Seeing what is hidden | Dashed switches say so | Struck-through names say so | A line at the foot lists what is hidden |
| Cost | A bar of nine switches is wide, and wraps on a phone | Takes a column | The hidden parts are one step away |

## The prototype

In `prototype/`. It links `apps/brand` in place and unchanged, and extends the shell prototype through its hooks (`ROUTES_EXT`, `PROTO_EXT`, `PROTO_CLICK`, `PROTO_SYNC`, `START_ROUTE`, `TAB_HIDE`, `INWORLD`). `INWORLD` is new: it lets an app decide what the status bar says about the in-world date (CS1). Plain HTML, CSS and JS.

### Run it

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/calendars-sessions/prototype/index.html
```

A private single-page copy is built with `node build-review-copy.mjs --fragment OUT_DIR`. The controls bar switches the role (a GM, a player, a reader) and whether the library has clocks.

### Calendars

- **The month (CS6, A).** A strip of segments with a density mark, a grid with a moon on every day and up to two marks and "+N", and the day panel beside it; a bottom sheet on a narrow window. The festival and the absent leap day sit in the sequence; an absent one says so and cannot be opened. Arrow keys move through days, Page Up and Page Down change segment. There is no "today".
- **Writing on a day.** Opening a day creates nothing; a status line says whether the period exists. Add a note, an Event (with who can see it), a Fact, an existing Event or Fact, or, for a GM, a recurring observance. Every write can be undone as a whole, and writing a note on an empty day is the only thing that makes its period. A player can add notes, Events and Facts but not observances; a reader adds nothing.
- **Whole year.** The second view: every day as a square, darker for more written on it.
- **Events (CS3).** A tab with a name search, who took part, causes and effects, and a story-order switch that marks each Event **recorded** or **linearized**. The time filter narrows it by date. A reader sees only what is open to everyone.
- **An Event.** When (dates, clock readings), who took part, learning (GMs), information, and **Order and causes**: the relationships you can see, share or make private (starting private), add (a loop is refused with a reason), and **Compare Events**, which finds a recorded causal chain or ordering or says the display order is linearized and is not a claim. A player sees only shared relationships between Events they can see. Also: a group made from the people who took part, learning records, a clock reading and **Read this Event on another clock**, which is derived and never saved.
- **Clocks.** A tab shown only when the library has clocks: ticking and timeless clocks, reckonings, relationships, a converter, and sharing.
- **The calendar definition.** An Author's page: segments in order (add, rename, move, remove), weekday names, a preview of the year, and a refusal when an edit would strand a written period ("Greening has 4 periods written on it").
- **The time filter (CS2).** A strip of the year with a marked density. A range (Events) or a single date (a date lens). Drag across it, or use the arrow keys, Page Up, Page Down, Home and End on a handle. It is a shared component; the **date lens** route shows it filtering a Locations list the way Maps would, from stated dates only.

### Sessions

- **Home.** The next Session, then Sessions by campaign with a status. A GM makes a Session (the roster starts empty). A reader with no Session sees an empty state.
- **The Session page (CS4, CS6, C).** Nine regions: details, roster, notes, references, game time, Scenes, played, campaign order, lived order. A **View** menu lists the views (Prepare, Played, All, and your own) and the parts. Each region folds and hides, and the foot says what is hidden. **Save this view** names the current set; it is remembered in this browser and is the person's own.
- **In the regions.** Edit the details (the in-world start moves the status bar's date); add or remove a player with a Character; notes for me, the Session's GMs or its participants; references that start private; game time covered, apart from the start; Scenes in order (up and down, or Alt with the arrows), each appearance with its own audience and notes, and added new or reused; the **played record** proposed from the outline as a draft, with played or skipped and the Events presented, saved on purpose and untouched by later preparation; the campaign order, for the Sessions you manage only.
- **Scenes** and **Lived order** are tabs, for GMs. A Scene has a link name, a date, references and where it is played. Lived order lists a being's participations to reorder or leave out, a ruling that can be removed, and saving refuses an order that contradicts a ruling.
- **A player** sees fewer regions, only shared Scenes and references, no controls to change them, and no campaign order.
- **The status bar** shows the in-world date of the Session being looked at and nothing on the calendar (CS1).

### What it fakes

All data is made up and held in memory (`cs-data.js`). The calendar's arithmetic (days, moon phases, recurrence) is a few lines, where the real app asks the API. Nothing is saved except the person's own views, in `localStorage`. Clocks use a simple ratio. The date lens uses a made-up list of places.

### What was checked

- 71 scripted checks in Playwright, all passing: the month and its keys, absent segments, writing and undoing on a day, an Event with its audience, the whole year, three roles, Events and every filter, the time filter by key and drag, an Event's order and causes (share, compare, a loop refused, what a player sees), learning kept after a participant is removed, a reading converted, clocks, the date lens, the calendar definition and its refusal, Sessions and every region, the view menu and saved views, the played record staying fixed, the campaign order, a player's view, an empty state, lived order and its refusal.
- axe-core: no violations on twenty states (the month, whole year, Events, an Event, its order dialog, clocks, a clock, the lens, the definition, Sessions, a Session in two views, the played dialog, Scenes, a Scene, lived order, the menus, the day sheet and an empty state) at 1440 and 430 wide, in light and dark (the landmark-region rule is off for the page's overlays).
- Touch targets of at least 44px at 430 wide on a touch device, on thirteen routes.
- No console errors.

### What was not checked

A screen reader (the month is an ARIA grid and needs one), a real touch device (touch is emulated), colour-blindness simulation, Safari and Firefox, a calendar with hundreds of marks, a Session with many Scenes, and a very large library of Events.

### Findings

- A Session or an Event that a person cannot see must not appear on a calendar day or in a count. The prototype filters the day panel and the day marks by what the role may see.
- The shell's in-world date (D18) is no longer shown on every screen. The account hub and Writing prototypes still show the old placeholder and need it removed in the write-up.
- There is no illustration for "no Session yet" on the list in [mascot-images.md](../mascot-images.md); the prototype uses a slot named `empty-sessions`, which should be added.
- Heavy per-day marks make the time filter noisy. A density band, not a tick for every marked day, would be calmer in the real component.

### Screens

In `screens/`, 31 images: the month and a day written, the add menu, the whole year (01 to 04); Events, story order, the time filter (05 to 07); an Event, its order and causes, a linearized comparison (08 to 10); a clock, the date lens, the calendar definition refused (11 to 13); Sessions, a Session by view, the View menu, a fold, the played draft, a player, a Scene, lived order (14 to 24, 18 to 23); dark (25, 26); 834 (27); 430 (28 to 32).

## Open questions

1. The Session's **Prepare** and **Played** views are built in. Should a GM's first visit to a Session open Prepare, or the view they last used?
2. The calendar's **Add to this day** menu offers a note, an Event, a Fact, an existing one and an observance. Is that the right set, in that order?
3. The time filter shows a density mark for every marked day. Keep, or a calmer band?
4. The **date lens** is drawn on a Locations list. Should Maps and the other lists share exactly this component, or have their own?
