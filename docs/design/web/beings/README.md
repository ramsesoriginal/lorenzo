# Beings: design

A fresh design of Lorenzo Beings, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, Calendars with Sessions and Maps are decided. This page holds the brief, the questions and the decision log for this app.

Status: the brief is answered (BN1 to BN5). Three directions for the being page are drawn and wait for a choice.

## What the app is for

Beings holds the characters of a library: player characters, non-player characters, creatures, crew. A being is one entry with a page. The page shows what a person may know about it, in the order they need it at a table: who it is, what is written about it, what it can do, what it carries.

- **Stats are generic.** A stat is a number, a line of text or a set of tags, chosen by the library's Settings. Nothing assumes a system, a genre or a vocabulary. A stat is either set directly or derived from others, and the page can say how.
- **Notes have four audiences:** GM only, Everyone, Some characters, and a Player note. A note a person may not read is absent, with no count.
- **A being is played by someone,** and the GM can hand it over.
- **Play changes numbers live** (a hit point, a use, a resource) in steps that can be undone.

Sources: [the app's README](../../../apps/beings/README.md), ADRs [0270](../../adr/0270-beings-app.md) to [0272](../../adr/0272-beings-editing-stats-and-handing-over.md), [0281](../../adr/0281-sheet-settings-and-the-sheet-read.md) to [0284](../../adr/0284-beings-sheet-datasheet.md), [0296](../../adr/0296-being-stat-group.md), [0297](../../adr/0297-beings-stat-selection.md), [0302](../../adr/0302-deleting-a-being.md), [0304](../../adr/0304-atomic-information-audiences.md) to [0306](../../adr/0306-information-bundles-and-their-editors.md) and [0313](../../adr/0313-event-participation-browsing-and-calendar-addresses.md). Defining which stats a library has is Settings' job and is not designed here.

## Already decided

- **The shell** (D12 to D29): the header, the app's own Home, the status bar, the palette, overlays, loading, empty and error states. `empty-beings` is on the [illustration list](../mascot-images.md).
- **The list template** (D21) and **density and saved views** (D22): search, filters, selection with a bulk bar, saved views, density.
- **Undo and confirmation** (D26): Undo for what can be reversed, a confirmation that names the consequence for what cannot, and the name typed for the biggest.
- **Words and gestures from Writing and Maps:** inline editing where it can be seamless, a menu twin for every drag, a refusal that says why, the history as the undo surface.

## The jobs

Ordered by who arrives and what they need in the first minute.

| Who | The job | Needs from the data |
| --- | --- | --- |
| A GM at the table | Run a creature: read what it does, change its numbers, note what happened | the stats, Play, the notes |
| A player at the table | See my character, change my hit points and uses, one-handed on a phone | the pinned numbers, steppers, Undo |
| A player in a skirmish | Read many beings at once as a compact datasheet | the datasheet |
| An author | Write a character that is only prose: no stats, no fuss | About and Notes without empty stat sections |
| A heist crew | Keep a roster and see who has what | the list, a kind, a campaign |
| A new player | Make a character | the Settings' stat set and a form that does not ask what the library does not use |
| A GM | Hand a being to a player, or take it back | who plays it |
| A GM | Delete a being, knowing what goes with it | the consequence, in words |
| A reader | Find a being by name, kind or campaign; see only mine | the list and its filters |
| A reader | See the events a being takes part in | participation, for full-visibility only |

Roles in play: Author, GM, full-visibility Owner or Organizer, the player of a being, and everyone else.

## What stays true, whatever it looks like

Rules about behaviour and honesty, not about pictures. They hold in any direction.

- **A hidden thing is absent** (D24). A note or a stat a person may not read has no placeholder and no count, in the page, the list, a search result or an error.
- **The API decides every permission.** A control that the API would refuse is not shown, and a refusal that happens anyway is shown as it is given.
- **Audience badges are neutral,** not colours that suggest a verdict (identity §14.3). They say who, in words.
- **One live region announces only the change,** not the page.
- **Play can be undone,** in steps, and says what it undid.
- **Deleting names its consequence** and asks for the name (D26).
- **Direct and derived stats look different,** and a person can ask why a derived number is what it is. Colour is never the only carrier.
- **No page-level Save.** A change is kept where it is made, and a refusal keeps the draft.
- **Library words win.** Stat names, kinds and audiences are the library's own, never a built-in vocabulary.

## What the old documents decided

[The earlier Beings design](../../beings/README.md) made these choices, and [its "As built" answers](../../beings/README.md) record what shipped. They are listed here so each is decided again on purpose and not by habit. Nothing is taken from the current screens.

| Old decision | What it was | Asked in |
| --- | --- | --- |
| Three modes, two layouts | Read, Play and Edit, each as Sheet or Datasheet | Q2 |
| A sticky bar | Pinned numbers and the mode switch stay in view while the page scrolls | Q3 |
| A rail | Who plays it, and Hand over, beside the page | Q3 |
| Read order | About, Notes, Stats, Inventory | Q5 |
| Pinned stats | A flag on the stat definition puts a number in the sticky bar | Q5 |
| Stat tiles | Numbers as tiles on a muted surface, text as rows, tags as chips | Q4 |
| Solid and dashed | Solid is set directly, dashed is derived; a "why" panel explains | Q5 |
| The datasheet | Only on the page, never on the list | Q4 |
| Play without steppers | Offered to people who may not edit, as a read-only Play | Q5 |
| No mode memory | The page opens in Read every time | Q5 |
| Undo scope | Play only, 30 steps | Q3 |
| No page-level Save | Each change stands where it is made | Q5 |
| Row shape | Compact rows with a small portrait preview | Q1 |

## Questions

Five questions. The first four change the screens; the fifth is the table above.

**1. How does the list begin?**

- **A. Rows only.** One table: portrait, name, kind, campaign, who plays it, a few pinned numbers. Densest, easiest to scan and sort.
- **B. Cards only.** A grid of portraits with name and kind. Friendlier for a few characters, poor for forty creatures.
- **C. Both, one switch.** Rows by default, a cards view for a person who wants it, remembered per person, with the same search, filters and "Mine".

My recommendation: C. A heist crew of six wants cards, a bestiary of two hundred wants rows, and the shell already has a per-person view setting.

**2. How are modes expressed?**

- **A. Three modes, as before.** Read, Play and Edit in a switch; Edit turns the whole page into a form.
- **B. Read and Play are modes, Edit is in place.** Reading is the page. A section that a person may edit has its edit control on the section, as in Writing, and saves as it goes. Play stays a mode because it changes numbers live and needs steppers and Undo.
- **C. No modes.** Everything is always live for people who may change it.

My recommendation: B. It removes the form-versus-page jump and matches how Writing works, while keeping Play's risky controls out of Read.

**3. Where do Play's quick actions and Undo live?**

- **A. In the sticky bar,** with the pinned numbers. One place, always in view. Crowded on a phone.
- **B. In a dock at the bottom on a phone,** and in the sticky bar on wider screens. Thumb reach where it matters.
- **C. On the number itself.** Each tile has its own stepper; Undo is the shell's toast, with the history for more.

My recommendation: C for the steppers, with the 30-step history as the undo surface (as in Maps), and the pinned numbers in the sticky bar for reading. A dock only if testing shows the phone cannot reach the tiles.

**4. How do the stats and the datasheet relate to density?**

- **A. Datasheet stays a layout switch** beside Sheet, as before.
- **B. Datasheet is what Dense looks like** for the stats area: the shell's Dense setting turns tiles into the compact table, so there is one control, not two.
- **C. Datasheet becomes a separate view** that lists several beings side by side, which is what a skirmish needs.

My recommendation: A for the page, and C as the list's third view in Question 1, so a skirmish reads many beings at once. That is new, so say if it is wanted.

**5. Which old decisions carry over?**

My recommendation is that every row in the table above carries over, except these:

- **Mode memory** — remember the last mode per being for the person who plays it, because a player at a table lands in Play every time.
- **Datasheet only on the page** — see Question 4.
- **Row shape** — see Question 1.

Say which others to change; no answer means "as recommended".

## Decision log

### BN1. The list has rows and cards, one switch

Rows by default, a cards view for a person who wants it, remembered per person, with the same search, filters and "Mine" in both.

### BN2. Read and Play are modes; Edit happens in place

Reading is the page. A section a person may change has its edit control on the section and saves as it goes, with no page-level Save. Play stays a mode, because it changes numbers live and needs steppers and Undo.

### BN3. Play's steppers sit on the numbers

Each number has its own stepper. The 30-step history is the undo surface, with the shell's Undo toast for the last step. Pinned numbers stay in a sticky bar for reading. A dock is added only if testing shows the phone cannot reach the numbers.

### BN4. The datasheet is a layout switch on the page, and a third view of the list

The page keeps Sheet and Datasheet. The list gains a side-by-side view that reads many beings at once, for a skirmish.

### BN5. The old decisions

Every row of the old-decisions table carries over, except mode memory: the page opens in the last mode used by the person who plays that being, so a player at a table lands in Play. The datasheet and the row shape are BN4 and BN1.

## The directions (drawn; waiting for a choice)

In `directions/`: the list in its three views (BN1, BN4) and three layouts for the being page, each in Read, Play and Read with About being edited (BN2, BN3), on the shell. The data is made up. The list views and the modes are the same in all three directions; what differs is how the page is arranged. Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/beings/directions/index.html
```

The controls bar switches the screen and the mode. Screens are in `directions/screens/` (12 images, at 1440).

| | A. Column | B. Sheet | C. Band |
| --- | --- | --- | --- |
| Shape | One reading column in the old order (About, Notes, Stats, Inventory), a rail on the right | Stats on the left, prose on the right, the rail under the prose | A band of the pinned numbers over tabs: About, Notes, Stats, Inventory, Events; the rail on the right |
| Pinned numbers | A sticky bar that follows the scroll, with the steppers and the mode switch | In the stats area; scroll away with it | A band that stays at the top of the page, large |
| Play | Steppers in the sticky bar and on the tiles | Steppers on the tiles, all in view with no scroll | Steppers on the big tiles, and the other stats under Stats |
| Edit in place | On each section | On each section | On the section in the open tab |
| Best for | Reading a character top to bottom; a phone | A table with a wide screen: numbers and the story at once | A GM who runs many beings and jumps between sections |
| Cost | A long page; the stats are far down | Two columns need 1100 px; on a phone it becomes A | Prose is one click away; the band takes height |

What is not drawn yet: the phone widths, dark mode, the empty and refused states, "Hand over" and delete, the history list, and the datasheet in each direction beyond the one table. None of these have been run through the checks.

## Open questions

Which direction (or which parts of two) is the being page?
