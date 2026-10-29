# Lorenzo Beings: sheet design brief

A design pass on the being page of [`apps/beings`](../../../apps/beings) ([ADR 0270](../../adr/0270-beings-app.md) to [0272](../../adr/0272-beings-editing-stats-and-handing-over.md)). This is a design for something a person can play, read and write at, for any game system. The brief was written when the page was a single column of separate sections and editing a stack of separate forms; the sheet it describes is now built, see [As built](#as-built).

The prototype is plain HTML, CSS and JS in [`prototype/`](prototype/index.html). **It is a reference for layout and behaviour, not code to ship.** It runs on made-up data and changes only an in-memory copy. It asks for **no API change**.

To run it, serve the repository root (the page links `apps/brand` in place, and the icon sprite is fetched):

```bash
python3 -m http.server 8731    # from the repository root
# open http://localhost:8731/docs/design/beings/prototype/index.html
```

The bar at the top ("Prototype") picks the being, who is viewing, the theme, and restores the example data. It is not part of the design.

To open it without serving anything, [`prototype/build-single-file.mjs`](prototype/build-single-file.mjs) builds one self-contained HTML file (brand CSS, icon sprite and lockups inlined): `node docs/design/beings/prototype/build-single-file.mjs OUT.html`.

## Who it is for

Nobody comes first. The same page has to serve:

| Someone               | What they open it for                                              |
| --------------------- | ------------------------------------------------------------------ |
| A GM running an NPC   | What does Orla want, what does she know, where is her number       |
| A player at the table | Hit points, armour, what I carry, one tap to change a number       |
| A skirmish player     | The operative's datasheet: a stat line, a weapons table, abilities |
| An author             | Prose, a timeline, notes; no numbers at all                        |
| A heist crew          | Preparing a plan together before anyone rolls                      |

So the page does not pick a use. It lets the person pick how they are looking at the being.

## Three modes and two layouts

**Mode** (Read, Play, Edit) says what you are doing. **Layout** (Sheet, Datasheet) says how dense the being is drawn. They are independent.

|         | Read                           | Play                                                 | Edit                                      |
| ------- | ------------------------------ | ---------------------------------------------------- | ----------------------------------------- |
| Order   | About, Notes, Stats, Inventory | Stats, Inventory, Notes, About (collapsed)           | Same as Read, so the page does not jump   |
| Numbers | Still                          | Own numbers have − and +; tags toggle                | Every value is a field                    |
| Notes   | Read, and add one              | Read, and add one                                    | Reorder, edit, delete, change audience    |
| Header  | Name, kind, tags               | Same, and the sticky bar keeps three numbers in view | Name, link name and picture become fields |

- **In-place editing outside Edit.** What people do during play is small: change a number, switch a condition, jot a note. Those work in Read and Play without entering Edit. Edit is for building the being. Changes save as you go; there is no page-level Save.
- **Play changes can be undone.** Every change in Play (a number, a tag) shows what it did ("Hit points 31 → 24") with **Undo**, also on Ctrl or Cmd+Z, up to 30 steps. The changed tile is highlighted and shows the amount (−7) for a moment. A screen reader hears only the change, through one small live region, not the page.
- **Edit is offered only to those the API will allow** (a GM, or a player of the being). Otherwise the control is disabled with its reason. The API still decides every write.
- **Datasheet** (a quieter control than the mode switch) draws the same data as a datasheet: each stat group is one line of labelled cells, inventory with stat columns becomes a table (weapons, for an operative with item stats), and notes become "Abilities and notes". It adds no data; it is a different density. It shares the header's frame instead of sitting as a second card under it.

## The page

- **Identity header.** Picture, name (the one place the serif is used, [identity §5.2](../../brand/identity.md)), kind, who plays it, link name, tags, the two switches.
- **Sticky bar.** Appears when the header scrolls away: the name, the pinned numbers (what a table needs at a glance), links to the sections, and **the mode switch**, so changing mode never means scrolling back up. Section links replace tabs: nothing hides behind a click. On a phone the bar has two rows (name and switch, then the numbers) and drops the links.
- **Rail.** Who plays it (and Hand over, in Edit, for a GM) and the details. On a phone it moves under the content.
- **Sections.** About, Notes, Stats, Inventory. Each has a title, a count where there is one, and its own action at the right (Add a note, Open the board).

## Stats, drawn generically

No game system is assumed. A group is its stat definitions, and a stat is drawn by its type:

- **Numbers** are tiles: label, large tabular value, an optional unit or caption ("of 9", "+3"). Tiles are the quick-scan form.
- **Text and enums** are rows under the tiles.
- **Tags** (bool stats) are chips in the header: on, off, or inherited.

### The stat area

Stats sit on a surface of their own (`--surface-muted`) with the tiles in `--surface-default` on it, so the page has one clear place for the numbers. Sections are told apart by a larger title and a rule under it. Tiles in a row share their label, value, caption and foot rows (CSS subgrid), so numbers line up even when one label wraps ("Hit point maximum"). A **Key** beside the title opens what solid and dashed mean, instead of a sentence under every heading.

### Where a value comes from

The grammar of [identity §18](../../brand/identity.md#18-information-visualization-grammar): **solid is direct, dashed is derived.** A tile with its own value has a solid border. An inherited value (from a prototype such as Dwarf) or a calculated one is dashed, and also says so in words ("From Dwarf", "Calculated"). Calculated values open a small panel that shows the parts that add up to the value, so "why is my armour 15?" is one tap. The data for this already exists (`own`, the source entry, the formula and its parts); nothing new is asked of the API.

### What is not here yet

- **Pairs** such as hit points over a maximum are two stats today and two tiles. A template could say one stat is the other's maximum and draw them as one. The prototype does not pretend.
- **Dots, tracks and clocks** for small whole numbers (Blades in the Dark actions, stress) are a visual template, as are weapon tables for a particular game. They belong to entity templates, which are later work.
- **Which stats are vitals.** The prototype marks a few stats as pinned (`pin: true` in the sample data) for the sticky bar, and falls back to the first three numbers of the first group. A template should choose them. Built since as a flag on the stat definition, see [As built](#as-built).

## Notes and who can read them

Four audiences, as [ADR 0271](../../adr/0271-beings-the-page-and-its-notes.md): GM only, Everyone, Some characters, Player note. Visibility is **neutral by the brand's rule**: no colour, a small badge with an icon and a label, and nothing at all for Everyone ([§6.6](../../brand/identity.md)). The form lists the audiences the viewer may use, each with one line saying who reads it. Notes the viewer may not read are absent, not hidden behind a placeholder, so their number is not a leak.

Switch "Viewing as" in the prototype bar to see the same being as the GM, as its player, and as another player.

## Brand: what is reused and what is new

The prototype links [`apps/brand`](../../../apps/brand) in place (tokens, fonts, normalize, base, layout, components, motion, the icon sprite and the lockups). **It defines no token, colour, radius or font of its own**, and `sheet.css` contains no literal colour or size from the brand's scales.

| Reused from `apps/brand`                                                               | Used for                                                                                                    |
| -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `tokens.css`                                                                           | Every colour, space, radius, font, `--target-min`; the dark theme                                           |
| `.site-header`, `.brand-mark`                                                          | The header and lockup                                                                                       |
| `.card`, `.btn`, `.btn-primary`, `.btn-secondary`, `.text-input`, `.field`, `fieldset` | Cards, buttons, forms                                                                                       |
| `.chip`, `.badge-visibility`, `.key-values`, `.caption`, `.status-text`, `.lede`       | Tags, audiences, details, small print                                                                       |
| `.ls-content`                                                                          | Description and notes (LorenzoScript)                                                                       |
| `.icon` and the sprite                                                                 | Every icon (`icon-private`, `icon-kind-groups`, `icon-formula`, `icon-inherited-from`, `icon-inventory`, …) |

New in [`prototype/sheet.css`](prototype/sheet.css), each a candidate for `apps/brand` **once a second app needs it** ([ADR 0098](../../adr/0098-branding-css-app-and-package.md)):

- **`.segmented`**: a segmented radio control (Read, Play, Edit). `.tabs` is an underline control for switching content; this one switches how it is drawn.
- **`.stat-tile` and `.stat-grid`**: a number with a label and where it came from. Bench's compare grid and inventory-web's stat editor show the same thing.
- **`.icon-btn`**: a square, labelled icon button.
- **`.sticky-bar`**, **`.why`** (the calculation panel), **`.datasheet`**, **`.bar`**.

Gold is deliberately not used: nothing on a being's page is canonical in the brand's sense. The spark is not used for any state. Burgundy appears only where something would be destroyed.

## Phones

One breakpoint, 720 px ([§8.5](../../brand/identity.md)). One column; the rail moves under the content; section links drop out of the sticky bar (the sections are one scroll apart); anything pressed is at least 44 px; the datasheet's stat lines stack their label above their cells and its table scrolls inside itself, not the page. Nothing depends on hover: the calculation panel is a native `<details>`.

## Screens

Rendered at 1280 px (phones at 390 px) with Playwright. If a screen and the prototype disagree, the prototype wins.

|                                                                                                    |                                                                      |
| -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| [01 Read](screens/01-read.png)                                                                     | A GM reads a character: prose first, every audience visible          |
| [02 Play](screens/02-play.png)                                                                     | The same character at the table: numbers first, steppers, conditions |
| [03 Edit](screens/03-edit.png)                                                                     | Name, link name, tags, description, stats and notes as fields        |
| [04 Datasheet](screens/04-datasheet.png)                                                           | A skirmish operative: stat line, weapons, abilities                  |
| [05 Heist prep](screens/05-heist-prep.png)                                                         | A crew member and a plan shared with part of the crew                |
| [06 NPC with GM secrets](screens/06-npc-gm-secrets.png)                                            | A bare NPC, run by the GM                                            |
| [07 Author's character](screens/07-author-prose.png)                                               | Prose, a timeline, no stats at all                                   |
| [08 Another player](screens/08-another-player.png)                                                 | Only what is shared, Edit disabled                                   |
| [09 Phone, Play](screens/09-phone-play.png), [10 Phone, datasheet](screens/10-phone-datasheet.png) | One column                                                           |
| [11 Dark theme](screens/11-dark-play.png)                                                          | The same through `[data-theme="dark"]`                               |
| [12 Where a number comes from](screens/12-why-popover.png)                                         | Armour class, in parts                                               |
| [13 Sticky bar](screens/13-sticky-play.png)                                                        | Three numbers and the section links, kept in view                    |
| [14 Play after damage](screens/14-play-after-damage.png)                                           | Play mode after a change, with undo offered                          |
| [15 Phone, sticky mode](screens/15-phone-sticky-mode.png)                                          | The sticky bar with the mode switch on a phone                       |
| [16 Phone, adjuster](screens/16-phone-adjuster.png)                                                | The number adjuster on a phone                                       |

## What the prototype fakes

The API, saving, who may do what (it follows the rules of ADR 0271 and 0272 only in outline), the LorenzoScript renderer and editor, link previews, pictures (initials stand in), hand-over, the inventory board, and every "not in the prototype" toast.

## Open questions for the maintainer

1. **Pinned numbers.** Right place to choose them? Today it is sample data; a template would own it.
2. **Notes before stats in Read.** A long set of notes pushes stats down; the section links help. Is prose-first right for Read, or should Read and Play share one order?
3. **Datasheet as a layout.** Should it be reachable from the list (a being's card as a datasheet), or only on the page?
4. **Play for people who cannot edit.** It is shown, without steppers. Should it exist for them?
5. **Mode memory.** Remember the last mode per library, per being, or not at all?
6. **Undo scope.** Play changes only, for now. Should note and tag edits in Edit also be undoable?

## As built

The design is built in `apps/beings` ([RFC 0043](../../rfcs/0043-the-being-sheet.md), [ADR 0282](../../adr/0282-beings-sheet-shell-modes-and-sections.md) to [0284](../../adr/0284-beings-sheet-datasheet.md)). Where this brief asked, the answers were:

1. **Pinned numbers** are a flag on the stat definition (`pin`); with none, the first three numbers of the first group.
2. **Notes before stats in Read**: kept; the section links in the sticky bar are the answer to a long set of notes.
3. **Datasheet as a layout** of the page only, for now; not from the list.
4. **Play for people who cannot edit**: the mode is offered; without a stepper, since there is nothing they may change.
5. **Mode memory**: none. A page opens in Read and as a sheet.
6. **Undo scope**: Play changes only.

Differences from the prototype: the datasheet's notes say only "Not for everyone" where a note is not public (the sheet's notes keep the full audience); a library with no weapon group gets "Carried", the names and counts of what the being owns; the stat vocabulary is readable by every participant so a player's sheet can be drawn. The prototype remains the reference for anything not listed.
