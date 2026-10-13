# 0259 - Bench: the quiet interface

Status: accepted

## Context

Bench was built slice by slice, and each slice drew its own controls: native selects and bordered buttons, a system font, a bordered box around every pane and field. Together they looked like a data-entry form, which is the opposite of what the design agreed on a prototype ([docs/design/bench](../design/bench/README.md)): chrome nearly invisible, the text and the work in front. It was also slow with a real repository: the whole page was drawn again for every change, and the compare grid did work for each cell that grew with the number of entries.

## Decision

- **The prototype's tokens and type, from the brand package.** Geist for the interface at 13px, Newsreader for names and texts (a person can switch texts to sans with *Aa*), Geist Mono for link names and values. The palette is the brand's own (`--surface-*`, `--text-*`, `--border-*`, `--action`), so dark mode follows.
- **Chrome is one hairline and a soft fill.** Groups have a right and a bottom line, not a box; a tab is its title, with an accent line when active; buttons have no border (a soft fill on hover, a solid one only for the one main action); fields draw a border only on hover and focus where they are not the point; chips and pills are the one rounded form. Dialogs, the palette and cards are the only things with a shadow.
- **The title bar** carries the brand mark, the repository menu, one "find an entry or do anything" button (the palette), the layouts and *Aa*. Pane names follow the design: *Entries*, *Properties*, *Links*.
- **The entry is a document.** Breadcrumb of what it inherits from, the name set large, a line of kind chips with the link name and sync state, the description as it reads with the picture beside it, then *Inherits from* and *Notes* under quiet labels. Insert buttons and the "add" controls show when they are used.
- **The explorer** has a search, a count with *+ New* (the form opens only when asked for), the order, and rows with a kind icon.
- **The inline editor** is sized to its text, wrapped lines included, and an empty text says what to write ("Write a description…") instead of grabbing the focus.
- **The ancestry** is the entry's line only: what it inherits from and what is directly under it, as names with a pale mark on the entry itself. No boxes, no siblings.
- **Faster.** The page is drawn at most once per frame, however many changes arrive (reading many entries or pictures told the screen again and again); the list of entries is worked out once between changes and the entries are found by id; the compare grid finds where an inherited value comes from by id rather than by searching the list for each cell. A repository of 1,200 entries could not be opened in the compare layout before (it did not finish in 100 seconds); it now draws in about 0.2 seconds.

## Consequences

- Tests that named controls by their old titles use the new ones (*Entries*, *Properties*, *Links*); making an entry opens the *New* form first.
- The drawing is still the whole page per change. Drawing only the panes that changed is the next step if a very large repository needs it.
