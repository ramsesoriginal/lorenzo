# Inventory: design

A minimal redesign of Lorenzo Inventory. The board stays: its idea and its rough look are kept, and everything around it is redone on the system in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, Calendars with Sessions, Maps and Beings are decided. This page holds the brief, the questions and the decision log for this app. Bench is not redesigned.

Status: the prototype is built and ready for review (decisions IN1 to IN12 are logged here).

## What the app is for

Inventory shows what a being carries and lets people move it. A character's things are drawn as a board of columns, and every card on it is an item that exists: a sword, a bag of coins, a pack.

- **A board is the things a being controls** ([ADR 0131](../../../adr/0131-the-board-on-controlled-by.md), [0134](../../../adr/0134-board-refinements.md)). Equipped and Not carried come first and always. Then a column for every container the being controls, empty ones included. Then read-only columns for whatever else holds something of theirs, marked as read-only and saying who has it ("Not carried, with Alice"). A card that is not the being's own names its owner.
- **Groups have boards too,** and can be given things ([ADR 0124](../../../adr/0124-groups-own-things-and-moving-is-not-giving.md)). A GM can open any being's board, and the board of what nobody owns.
- **A catalog** holds what can be made: items with their prototypes, a description, stats, tags and a link name. A player reads the public part. A GM writes it and makes instances from it.
- **Unsorted** is a GM's page for things a player wrote in by hand, to be matched to the catalog ([ADR 0238](../../../adr/0238-inventory-web-not-in-the-list-and-the-unsorted-badge.md), [0241](../../../adr/0241-inventory-web-the-unsorted-view.md)).
- **An item has its own page,** for a catalog item and for an instance: description, notes, stats, tags, pictures, its ancestry, and where it is mentioned.

Sources: [the app's README](../../../../apps/inventory-web/README.md) and the ADRs it links, among them [0108](../../../adr/0108-lorenzoscript-in-inventory-web.md), [0112](../../../adr/0112-inventory-web-the-whole-item.md), [0113](../../../adr/0113-inventory-web-slugs-and-player-notes.md), [0115](../../../adr/0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md), [0132](../../../adr/0132-setting-things-down.md), [0133](../../../adr/0133-merging-what-is-identical.md), [0187](../../../adr/0187-inventory-web-adding-an-item-to-a-board.md), [0189](../../../adr/0189-inventory-web-unpacking-a-pack.md), [0263](../../../adr/0263-inventory-web-editing-stat-values.md), [0304](../../../adr/0304-atomic-information-audiences.md) and [0306](../../../adr/0306-information-bundles-and-their-editors.md).

## What stays

The maintainer's rule: the board concept, what it is and roughly how it looks, stays.

- **A board of columns of cards,** left to right, with Equipped and Not carried first, then containers, then read-only columns.
- **Cards are item instances,** dragged between columns to move them, as the shell's board template already draws it (D21, [screens 12 and 13](../screens/12-board-1440.png)).
- **Read-only columns are marked** and a foreign card names its owner. Colour is not the only carrier.
- **The board opens on your character:** the last one you opened here, or your only one.
- **The board is full width** (D21).

## What stays true, whatever it looks like

- **A hidden thing is absent** (D24). An item or a note a person may not read is not there: no placeholder, no count, no unreadable card.
- **The API decides every permission.** A move the API refuses is shown as it is given, the card goes back, and nothing else changes.
- **Moving is not giving.** A move keeps ownership; a give changes it, and says so before it is done. "Hand it over" is a separate, plain choice.
- **Setting down asks first** when a stack would become single items (ADR 0132).
- **Every drag has a menu twin** and works from the keyboard, as in Writing and Maps.
- **Undo for what can be reversed** (D26); giving to someone else and deleting say what they do first.
- **Notes keep their audience** ("Who can read this"), and audience changes are atomic and versioned (ADR 0304).
- **An unsorted item wears a badge** until a GM matches it.

## The jobs

| Who | The job | Needs from the data |
| --- | --- | --- |
| A player | See what my character carries; put something in a bag, take it out, set it down | the board, containers |
| A player | Give something to another character | the tenant's characters |
| A player | Add something I found, from the catalog or by hand | the public catalog, self-service on or off |
| A player | Read an item: what it does, my notes on it | the item page |
| A GM | Open any being's board, a group's board, or what nobody owns | search, groups, the unowned board |
| A GM | Give out loot to several beings at once | bulk give |
| A GM | Match unsorted things to the catalog | the unsorted view |
| A GM | Write the catalog: items, prototypes, descriptions, stats, tags, link names | catalog CRUD |
| A GM | Unpack a pack into what it lists | a dry run, then the move |

## What the old app decided

Named from the documents, so each is decided again on purpose. Nothing is taken from the current screens or styles.

| Old decision | What it was | Asked in |
| --- | --- | --- |
| The board | Columns of cards, drag to move | kept |
| One column per container, empty ones too | A container always has a column | kept |
| A single-slot Undo | The last give, move, split or merge only | Q4 |
| Search within the loaded board | By item name | Q1 |
| Multi-select, then give or move together | One call for many cards | Q4 |
| The item opens as a detail view | Over the board | Q3 |
| A page for every item | Shareable, "Copy link" | Q3 |
| Catalog, Unsorted and the board as separate pages | Reached from the board | Q1 |
| A GM's catalog forms | Create, edit, delete with forms | Q5 |
| A notification bell in this app's header | Unread count, latest ten | decided (D12 shell: account menu) |
| Add an item under the search | Pick, name, lands in Not carried, with Undo | Q4 |
| "Not in the list?" | A name, notes, weight and value, then the Unsorted badge | Q4 |

## Already decided

- **The shell** (D12 to D29): the header, the app's own Home, the status bar, the palette, overlays, loading, empty and error states. `empty-inventory` is on the [illustration list](../mascot-images.md) at priority 1.
- **The board template** (D21): full width, with the page's own controls above it.
- **Selection and the bulk bar, Undo toasts, confirmation dialogs, sheets on a phone** (D21, D22, D26).
- **Words and gestures from Writing, Maps and Beings:** a menu twin for every drag, edit in place where it can be seamless, the shell's Undo toast, a refusal that says why.
- **The notification bell** is the shell's (account menu and notifications), not the app's.

## Questions

**1. How is the app laid out?**

- **A. The board is Home; Catalog and Unsorted are tabs.** The app opens on the board, the tabs are Board, Catalog, and Unsorted for a GM. The board's search finds items on it.
- **B. Home is a list of boards** (my characters, my groups) and a board is a page one step in.
- **C. One page, the board, with Catalog and Unsorted as side panels.**

My recommendation: A. The old app already opens on your character, and the maintainer wants the board first. A tab is one step; B puts a list between a player and their things.

**2. How does the board work on a phone?**

- **A. Columns side by side, scrolling sideways,** with the fade at the edges that the shell uses for wide strips. Same as the wide board, narrower.
- **B. One column at a time,** with a row of column names to switch, and Move to… as the way to move a card.
- **C. Columns stacked** as sections that open and close.

My recommendation: B on a phone, A everywhere else. Dragging a card across a sideways-scrolling board with a thumb is the hardest thing on the page; one column plus Move to… is exact. The wide board keeps its look.

**3. Where does an item open?**

- **A. A panel beside the board** (a third pane on a large screen, a side sheet on a tablet, a sheet on a phone, D21), with "Open the page" for the full item.
- **B. Always the full page,** back to the board with the browser's Back.
- **C. A dialog** over the board.

My recommendation: A. You see what a card is without losing the board; the full page stays for editing and sharing.

**4. Where do the actions live, and how is Undo done?**

The actions are Give, Move, Set down, Note, Unpack, Split, Merge, Add an item and Not in the list.

- **A. On the card's menu and in the panel,** with the shell's bulk bar for several cards, and the shell's Undo toast for every reversible one. No separate Undo slot.
- **B. A toolbar above the board** of the same actions, acting on the selection.
- **C. Both,** with the toolbar as the first place on a phone.

My recommendation: A. It is the same model as Beings and Maps. The Undo toast is the single-slot Undo with a timer, and it covers more.

**5. How are the catalog and the item page edited?**

- **A. In place,** as in Writing and Beings: the description is an editor that saves as you type, stats and tags are fields on the page, and a refusal keeps the draft.
- **B. Forms with a save bar,** as in settings: a change is made, then saved or discarded.
- **C. A mix:** in place for the description and notes, a save bar for the link name, prototypes and audience, which are structural.

My recommendation: C. Writing is a place for seamless prose; a link name or a prototype can break links, so it is worth an explicit save with the shell's save bar (D21).

Say which of the old decisions in the table to change; no answer means "as recommended".

## Decision log

### IN1. The board is Home; Catalog and Unsorted are tabs

The app opens on the board of your character (the last one you opened, or your only one). The tabs are Board, Catalog, and Unsorted for a GM. The board's search finds items on that board.

### IN2. A phone shows one column at a time

On a phone the board is one column, with a row of column names to switch between, and Move to… is the way to move a card. On a tablet and wider the columns sit side by side, scrolling sideways with the fade at the edges when there are more than fit.

### IN3. An item opens in a panel; on smaller screens it is the page

A panel beside the board on a large screen, a side sheet on a tablet, and the full page on a phone. It is one component with one content: the same description, notes, stats, tags, actions and links, shown in a panel or as a page. "Open the page" in the panel goes to the shareable page, which has the same content with room to edit.

### IN4. Actions are on the card and in the panel

Give, Move to…, Set down, Add a note, Split, Merge, Unpack, Add an item and Not in the list are on the card's menu and in the panel, with the shell's bulk bar for several cards and the shell's Undo toast for everything reversible. There is no separate Undo slot.

### IN5. The catalog and the item page: in place, with a save bar for structure

A description and notes are written in place and save as you type. Stats and tags are fields on the page. The link name, the prototypes an item is made from and whether it is in the public catalog are kept with an explicit save bar (D21), because they can break links.

### IN6. The GM and author features are part of the design

Everything a GM does is drawn, not left to the old app: opening any being's board, a group's board and the board of what nobody owns; making an item from the catalog for a being, with an optional owner and link name; reassigning, unassigning and deleting an instance; adding an item to any board; creating, editing and deleting catalog items, with several prototypes, a public flag and "used as a prototype by"; editing stat values; the Unsorted page with its matching; unpacking a pack; and the notes' audiences. A player sees none of these controls, and what they may do on their own board follows self-service, with a note saying so when it is off.


### IN7. The board's name is a switcher

Direction A. The board's name is a button; its menu lists your characters and groups, and for a GM a search for any being and the unowned things. A player with one character has nothing to choose. The last board you opened is remembered.

### IN8. Every column shows its weight

Each column says what it holds, in weight, in its header line ("12 of 12 lb" for a container with a limit, "5 lb" for the rest), above the board's carried weight. A move that would go over a container's limit is refused in words and the card stays.

### IN9. The board fills the page, and its columns are as tall as the tallest

With no panel open the board spans the whole width. The columns are all as tall as the tallest one, and no taller than the space on the screen. A column with more cards than fit scrolls inside itself, and the board's sideways scroll sits at the bottom of the screen, just above the status bar.

### IN10. Equipped and Not carried have a rotating gold ring

The two columns a character always has carry a gold ring that turns slowly and a soft glow. With reduced motion the ring is still. No other column has it.

### IN11. A column with a limit says how much room is left

"3 of 4 lb · 1 lb free", or "12 of 12 lb · full". A column with no limit shows only its weight.

Error toasts stay until they are closed, as in the whole shell.

### IN12. A drag shows where the card would land

While a card is dragged, the column under it is highlighted, and a ghost of the card, a dashed outline with its name, sits in that column where the card would go. The column grows or scrolls to show the ghost, so a tall column opens at the ghost. The ghost says what the move makes ("Makes 13 lb", "Makes 9 of 12 lb"), and when the card would join an identical stack, it says so and the stack is outlined ("Joins Rations × 6, making 8"). The dragged card is dimmed where it was. A column that cannot take the card is outlined in the danger colour with the reason in the ghost ("Too heavy: the backpack holds 12 lb, this would make 15"), and it cannot be dropped on. Read-only columns show nothing. Everything goes when the drag ends. The same words are given to a screen reader, and Move to… stays the path for a keyboard and for touch.

## The directions (drawn; A chosen)

In `directions/`: three layouts for the board page, each as a player and as a GM, and the GM's other pages, which are the same in all three: the catalog, Unsorted, and an item's page. They are on the shell with made-up data. The board is drawn from the documents; the shell's board template was the starting point, so **where this board differs from the one you like, say so.** Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/inventory-web/directions/index.html
```

The controls bar switches the screen, the panel and the open switcher. "You are" switches between a GM and a player. Screens are in `directions/screens/` (10 images, at 1440).

| | A. Switcher | B. Rail | C. Strip |
| --- | --- | --- | --- |
| How a board is chosen | The board's name is a button; its menu lists your characters, your groups, and for a GM a search for any being and the unowned things | A rail of boards beside the board: characters, groups, and for a GM a search and the unowned things | A strip of chips above the board, with "Find a being" and "Unowned" for a GM |
| What it costs | Nothing on the page; one click to see the choices | 14 rem of width, and the board gets narrower with the panel open | One row of height; a long list of boards scrolls sideways |
| A player with one character | Sees no choices to make; the switcher still shows | A rail of one | One chip, which can be hidden |
| A GM with forty beings | A search, not a list | A search at the foot of the rail | A search chip |
| Best for | The board as the page; the player who has one board | A GM who moves between boards all day | Two or three boards, switched often |

The GM pages:

- **Catalog** is a list and a panel (the shell's list-and-detail template). The panel has the description in place, stats, tags, "Make one" and "Used as a prototype by", and the structure fields with the save bar at the foot.
- **Unsorted** is a list of names players wrote, with a panel for the holders and their notes, the suggested catalog matches, and the three choices: give the ticked ones to a catalog item, make a new catalog item, or keep it for now.
- **The item page** is the panel's content at a page's width.

What is not drawn yet: the phone's one-column board, the Unsorted badge's states, the dialogs (Give, Move to…, Make from catalog, Reassign, Unpack, Not in the list), a drag, the empty states, and dark mode. None of it has been through the checks.

## The prototype

In `prototype/`, on the shell, with made-up data. Run it from `prototype/index.html`; `prototype/build-review-copy.mjs OUT_DIR` writes a single page that runs without the repository. "You are" switches between a GM and a player; "Self-service" switches what a player may add.

### The board (IN1, IN2, IN7, IN8)

- Columns: Equipped, Not carried, each container, then read-only columns (dashed, marked, "Not carried, with Mara Quill"). A card that is not theirs names its owner. Each column shows its count, its weight, and where it has a limit, the room left. Equipped and Not carried have the gold ring (IN10). The columns fill the width and the height, and a long column scrolls inside itself (IN9).
- A card is moved by dragging it to a column (with a ghost and a highlight, IN12), or by **Move to…**; a stack keeps its count and joins an identical one. A refusal (a container's limit) is shown as given and the card stays. Read-only cards cannot be dragged.
- **Select** turns on a bulk bar: Move to…, Give…, and Merge for stacks of the same item.
- The search narrows the cards on this board and says how many are shown.
- On a phone the board is one column at a time with a row of column names; on a tablet and wider the columns sit side by side.

### The item (IN3, IN4)

- A panel beside the board on a large screen, a sheet on a tablet, the page on a phone: the same content. The panel has the actions, the notes the person may read, and "Open the page".
- **Move to…, Give…** (a recipient, a number, "Hand it over"; it says that giving changes the owner), **Set down** (a stack asks first, then becomes single items), **Add a note** ("Everyone can read this"), **Split**, **Unpack** (a dry run first; the pack goes), **Add an item** (from the list, or "Not in the list", which adds it with the Unsorted badge). Every change gives the shell's Undo toast.
- A player's self-service can be off; Add an item and Unpack then say so and are disabled.

### The GM and author features (IN6)

- **Any board:** the switcher's "Find any being…", a group's board, and the board of unowned things.
- **Make from catalog:** an item, an owner and an optional link name. **Reassign…, Unassign, Delete…** on an item, each with Undo.
- **Catalog:** a list and a panel. The description saves as you type; weight, value and tags are fields; the link name, what it is made from and the public flag are kept with a save bar. A duplicate link name refuses the save and keeps the draft; leaving with unsaved changes is refused in words; deleting an item that has been made is refused in words; "Used as a prototype by" lists what depends on it. A player reads the catalog and edits nothing.
- **Unsorted:** groups by the name a player wrote, the holders and their notes with tick boxes, suggestions (including another spelling of the name), and the three choices: give the ticked to a catalog item, make a new catalog item, keep for now.
- **The item page** has the description in place and the weight as a field, for a GM.

### What it fakes

The data is made up and kept in the page. Weights are plain numbers. Containers have limits but no nesting. Nothing is saved or sent, and the API's other refusals are not drawn. The catalog's prototypes are a typed list. Import and export, and the notification page, are not drawn.

### What was checked

88 scripted checks pass (Playwright, 1440, 834 and 430 wide): the board and its columns, weights and read-only columns; search; the switcher, any being and the unowned board; the panel; Move to…, drag, a refused move, split and merge, give, set down, note, unpack, add an item, make from catalog, unassign and delete, each with Undo where it applies; the item page and its in-place edits; the catalog's save bar, its refusals and a new item; Unsorted, its suggestions and its choices; a player's board with no GM controls, no Unsorted tab, a read-only item and self-service off; the board's width with no panel, the gold ring, equal heights, a tall column scrolling inside itself with the board reaching the footer, and the room left, the ghost, the highlight, the refusal and their going; a phone's one column and pages, and a tablet's sheet. axe-core finds no violations on 19 states at 1440 and 430, light and dark (76 runs; the landmark-region rule is off for overlays). There are no console errors.

### What was not checked

A screen reader, a real phone or touch device, colour-blindness simulation, Safari and Firefox. The drag was tested with scripted drag events, not by hand, and not with a touch screen; the menu twin is the path for touch and keyboard. A board with a hundred cards has not been tried.

### Findings

- An error toast stays until closed, and the first scripted run found it sitting over the next menu. The checks close it first; the shell's rule stays (IN11).
- On a tablet and a phone the catalog and Unsorted had no way to open an item, because the panel is only drawn on a large screen. They are now pages with the panel's content.
- A selected card's secondary text failed contrast on the tint; secondary text on a card or a row is now the secondary colour.

### Screens

In `screens/` (22 images): the board as a GM with the panel, the switcher, a card menu, a refused move, a drag with its ghost and a refused drag, a selection, the add and unpack dialogs, the item page, the catalog with unsaved changes, Unsorted, an empty board, a player's board and read-only item and catalog, dark, a phone's column and item page, and a tablet's sheet.

## Open questions

None are open.
