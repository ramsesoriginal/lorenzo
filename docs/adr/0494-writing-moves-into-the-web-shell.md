# 0494 - Writing moves into the web shell

Status: proposed, 2026-11-18. Slice UI-E of [RFC 0050](../rfcs/0050-the-web-interface.md) for Writing. The design is [docs/design/web/writing](../design/web/writing/README.md) (WR1 to WR10, and [WR11](../design/web/writing/README.md#wr11-what-the-built-features-changed-proposed), which says where the built features differ from the drawing) and the decision is [ADR 0419](0419-writing-redesign.md); this ADR says how the app is moved to it, in what order, and what has to be decided first. Follows [ADR 0440](0440-calendars-moves-into-the-web-shell.md), [ADR 0441](0441-sessions-moves-into-the-web-shell.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which did the same for Calendars, Sessions and Maps. Nothing here is built, and the numbers of the stack's pull requests are not yet known.

## Context

Writing is feature-complete in the old interface: every slice of [RFC 0047](../rfcs/0047-lorenzo-writing.md) is built and tested end to end against the real API (2,600 lines of Playwright over about thirty scenarios). What it does not have is any of the interface that was designed: it draws its own header, its Home is a form and a list, a piece of writing is one plain text area with a column of closed panels under it, and structure is Up and Down buttons and a panel each for Move, Join, Extract and Split. The app is one page (`/`) driven by `?tenant=`, `?entry=`, `?view=outline|read` and `?review=`, written as imperative TypeScript (about 5,200 lines in `apps/writing/src/lib`), with no app-specific CSS.

Two things make this move different from Maps. The editor is the shared `@lorenzo/lorenzoscript-editor`, a `<textarea>` with a toolbar and a Preview tab, not a rich-text surface, and a page is an ordered list of text blocks, pictures and child Chapters, so the drawing's block surface has to be built around many editors, not out of one. And what is built does not support every gesture that was drawn: there is no operation that moves a block into another Chapter, and none that undoes a split, an extraction or a join (WR11, rows 3 and 6).

## Decision

- **The frame is the web shell** (`AppPage shell="web"`), as in the other apps. The page uses the `workspace` template for a work and `list-detail` for the shelf. The palette, the apps sheet and the status bar are the shell's, and the status bar holds the save state, the word count and the length goal (D18). Writing is in Build (D31).
- **A stack of nine pull requests, each on the one before and each tested and green**, with the API pull requests below as their own stack on `main` where they are needed. A PR draws only what the API already gives; where an API read is missing, the screen shows what it can and says so, and the PR that adds the read lights it up.
- **The behaviour does not change.** Autosave, conflict handling, recovery, review grants, the structural operations and their checks, counts, goals and exports are as built. Each PR moves the existing end-to-end scenarios onto the new interface, as Maps did, and does not delete one.
- **Old addresses keep working.** `?entry=` and `?view=` redirect to the new addresses. `?review=` is never changed: those links have been given to reviewers.
- **The editor stays a source editor.** A block surface is built around it: each text block has its own editor and a grip; pictures and child Chapters have a grip and a row. Enter and Backspace belong to the text area. Splitting a block is only the explicit, checked action of ADR 0346 and 0347.
- **App-specific CSS is allowed** where the shell's parts do not reach, as in Maps, in one file, with brand tokens only and the existing guard test.
- **What is not drawn until it can be built:** moving a block between Chapters and an undo for a split, an extraction or a join are asked in the questions below. Until they are decided the screens show the reduced behaviour of WR11 (rows 3 and 6).

## The stack

| PR | What it does | Needs |
| --- | --- | --- |
| W0 | **The frame.** `AppPage shell="web"`, palette, apps sheet, the status bar with the save state and word count, the legal links kept. The existing screens sit inside it unchanged. This ADR is accepted here and the tracking issue and milestone are made | nothing |
| W1 | **The shelf.** Home as Continue, then the work as a list with the filter All, Books, Chapters, Scenes, Carriers, Biographies and a search; "Start writing" at the top, asking the five kinds (Scene, Chapter, Book, Carrier, Character biography); the `empty-manuscript` slot; the library switcher is the shell's. "Shared with you to review" appears when the read in Q3 exists | Q3, Q4 |
| W2 | **A work's page and its addresses.** The page head (title, Write and Read as a switch, Details, Revisions, Count, Export, Focus); the new addresses with redirects from the old; the side views as a drawer from 1100px and a sheet below it, replacing the closed panels; the save states in the status bar and the recovered-text banner; the leave dialog (Stay, Leave anyway) beside the browser's prompt | W0 |
| W3 | **The page as blocks.** Each text block has its own editor and a grip; "Add text" and "Add picture" become a quiet plus between blocks; blocks reorder by grip and by Alt with the arrow keys, through the existing composition write; the block menu (right-click, long press, the Menu key, a tap on the grip): Split here, Make a Chapter, Make a Scene, Copy link, with the refusals in words; the selection bar for a block range; the text selection bubble (Link to an entity, Split here); focus mode | W2 |
| W4 | **The outline.** The tree pinned open from 1100px and remembered, a rail below, a panel on a phone; numbers and word counts on the rows; Move to… as the keyboard path; "Place an existing Chapter" and "Use a Scene"; the Edition menu holding Editions, Numbering, Contents, Updates and Export; a Carrier's Form and Covers sections | W3 |
| W5 | **Restructuring by gesture.** Grips on the outline rows; drag reorders, nests and promotes a Chapter and moves it between Editions, with the place among blocks and children, with a drop target that says what will happen or why not (the reviewer-set rule); the join target and Join into parent, with the dialog of WR11 row 4; extract by dragging a selected block range onto the outline; Undo for a reorder and a move, a dialog for the rest (or the undo, if Q2 is built) | W4, Q1, Q2 |
| W6 | **The side views reshaped.** Details (title, viewpoint, notes), Suggestions (the three reviews of WR11 row 8), Count (the scopes of row 13, the two targets, the timer and the session goal, and their summary in the status bar), Review (reviewers, the review address, the notes), Numbering and Contents as cards, Updates and Export as dialogs | W2, W4 |
| W7 | **Read and the reviewer.** Read as the second mode of the page; the reviewer's view with Add note under each Chapter or Scene heading, explicit Save and the sentence about who sees it; a revoked review as one sentence; the phone layouts (the outline as a panel, the side views as sheets); dark mode; the 44px targets; the axe checks | W4, W6 |
| W8 | **The audit.** Each part checked against the design and the differences written in this table's "Checked against the design" rows; the Writing README and guide, `v1.0.md`, the apps list; what is left, each in an issue | all |

### The API pull requests

Each is its own ADR and its own pull request, made before the one that draws it, only when its question is answered yes.

- **Q1, move blocks.** An operation that moves one block, a picture or a consecutive range into another Chapter, atomically, with the receipts and checks of ADR 0344, so that a block can be dragged between Chapters. Without it, a block moves within its page only.
- **Q2, undo.** An operation that restores the writing and the outline from the structural checkpoint a split, an extraction or a join leaves, so that they can be undone as a whole. Without it, those three ask first in a dialog (D26).
- **Q3, what is shared with me.** A read of the Editions that have been shared with the caller for review, so that the shelf can list them. Today a reviewer has only the review address.
- **Q4, the shelf's list.** The entry list's order and fields for the shelf: the last edited time, the kind and a count of Chapters. If the list already gives them, nothing is built.

## Questions

1. **Q1.** Build the move-blocks operation, or keep blocks in their page and move them by extracting them?
2. **Q2.** Build an undo for split, extract and join, or keep the dialog that says what is kept?
3. **Q3.** Build the read of Editions shared for review, so the shelf shows them? If not, a reviewer still arrives from the link and the shelf says nothing of reviews.
4. **Q4.** Does the shelf need a last-edited time and a kind and a count the entry list does not give?
5. **Addresses.** Are `/write/`, `/read/` and `/review/` (each with `?tenant=` and `?entry=`) the right places, with `/` as the shelf, as Maps has `/map/`?
6. **Updates.** Is "Select all clean" (ticks, never applies) the right form of what was drawn as "apply all clean"?

## Checked against the design

Filled in as each slice lands.

| Part | Slice | State |
| --- | --- | --- |
| The frame, the status bar | W0 | |
| The shelf | W1 | |
| A work's page, addresses, side views, the leave dialog | W2 | |
| The page as blocks | W3 | |
| The outline | W4 | |
| Restructuring by gesture | W5 | |
| The side views reshaped | W6 | |
| Read and the reviewer | W7 | |
| The audit | W8 | |

## Consequences

- The end-to-end scenarios of `apps/writing/tests/e2e/writing.spec.ts` drive the old controls by role and label and are moved as each part moves, as in Maps. The accessibility checks leave the shell's status bar out.
- The editor package gains no behaviour: the block surface is the app's. If a block needs something the editor does not give (a way to know its caret is at a safe boundary), it comes from the split-points read the API already has.
- The old interface is gone from the first PR in which its part is replaced, so the old panels are removed with their replacements and not kept beside them.
- The tracking issue and the milestone are made when this ADR is accepted, not before.
