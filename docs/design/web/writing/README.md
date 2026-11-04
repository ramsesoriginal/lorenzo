# Writing: design

A fresh design of Lorenzo Writing, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. This page holds the brief, the questions and the decision log for this app.

Status: the brief is answered (WR1 to WR7), a direction is chosen, and the prototype is built and ready for review.

## What the app is for

Writing is a quiet place to write stories, books and game lore, starting with prose, pictures or an outline and adding structure only when it helps. The writing is the page; everything else is asked for. Sources: [the app's README](../../../../apps/writing/README.md), [RFC 0047](../../../rfcs/0047-lorenzo-writing.md), ADRs [0327](../../../adr/0327-lorenzo-writing.md) to [0329](../../../adr/0329-writing-screen-and-local-recovery.md), 0341 to 0348, 0374 and 0378 to 0383, and [v1.0.md](../../../../v1.0.md).

The things a person writes, in the words of the domain:

- **Scene.** A reusable piece of narrative. A **telling** puts a Scene somewhere, sharing its text or holding its own copy ("Make independent").
- **Chapter.** Nests without a fixed depth; may stand alone (unassigned) until it is placed in an Edition.
- **Book and Edition.** A Book is a work and always has a first Edition; a further Edition is an independent copy with its own wording and outline.
- **Carrier.** A form or artefact (a codex, a scroll) that can have its own writing and can cover whole Editions, Chapters, Scenes or single blocks, across Books.

Every one has its own prose and pictures, written in LorenzoScript, apart from its description and notes.

## The jobs

Ordered by who arrives and what they need in the first minute.

| Who | The job | Needs from the data |
| --- | --- | --- |
| Someone new | Start writing at once: an untitled Scene, a Chapter, a Book | a library or repository to write in; nothing else |
| An Author | Write: prose, pictures, links to world entries; see that it is safe | the manuscript bundle, autosave state, conflict and recovery |
| An Author | Find the way around a long work: outline, reading order, contents, numbers | the composition tree, numbering rules, contents settings |
| An Author | Read the work as a reader would, continuously, and count it | the assembled manuscript, word counts, the personal length goal |
| An Author | Restructure without fear: move, promote, reorder, split, extract (a Chapter or a Scene), join, make independent | atomic operations with checkpoints, guarded links after a join |
| An Author | Make a second Edition; set a Carrier and what it covers | edition copy, prototype parents, ordered coverage |
| An Author | Give a Book to reviewers and read their notes | reviewers by email, the review address, their notes |
| A reviewer | Read an Edition and write notes only they and the Authors can see | the Edition's manuscript tree and pictures, no more |
| An Author | Recover work: unsent drafts, saved revisions | per-account local drafts, server revisions |

Roles in play: library or repository Author, and reviewer. Writing grants no campaign or inventory power. A reviewer has no library membership.

## What stays true, whatever it looks like

Rules about behaviour and honesty, not about pictures. They hold in any direction.

- **Writing is never lost quietly.** A save failure, a storage failure and a conflict are always visible, also in focus mode (RFC 0047). A conflict stops autosave until the person chooses which version to continue from; both stay available. Navigating away warns while work is unsaved.
- **Recovery says what it is.** Unsent drafts are kept in this browser for this account and come back after the person signs in again. The screen says so where recovery is offered; it is not offline browsing.
- **Restructuring is safe and reversible by history.** Every move, split, extract and join says what it will do, checks first, and leaves a saved revision. A split refuses an unsafe boundary and says why.
- **Removing a place never removes the writing.** A Chapter taken out of an outline keeps its text and subchapters.
- **A shared telling and an independent one look different,** and the person can always see which they are editing.
- **Coverage is not access.** A Carrier that covers writing grants no one the right to read it; a hidden thing is never counted (D24) and an unknown id is shown as a word, never an identifier.
- **Reviewers see only their own notes and the Edition.** Grants and review notes never leave with a copy or a release. Revoking a grant closes the review.
- **Counts say what they count.** Words are prose only, not markup, notes, code, maths or generated titles; a repeated reference counts each time it is read.
- **A secret is shown once** (the review address is not one; a token is) and **a dead link says one thing** (D27).
- **Large works stay fast.** Typing and focus do not wait on the outline, the count or the save.
- **The API decides every permission.** The screen explains a refusal in plain words.
- **Words** follow identity §14.3 and the RFC: Scene, telling, Chapter, Book, Edition, Carrier, outline, Read, Details, Review, Author, reviewer.

## Visual or structural decisions in the old documents

Named here so each can be kept or dropped on purpose. None carries over by default.

| From | What it decided | The question |
| --- | --- | --- |
| RFC 0047, ADR 0327 | No docked panes, floating windows or large menus; Outline, Read and Details open only when asked, in the page | Does "nothing permanent beside the writing" stay, or may a wide window keep an outline open by choice? |
| RFC 0047, ADR 0327 | A short toolbar, Write and Preview as tabs, a focus mode | Keep Write/Preview as tabs, or one surface with a live preview? |
| ADR 0329 | A library or repository picker, then drafts, then the editor | Does the app begin at a shelf of work, or in the last draft? |
| apps/writing README | One page, `/`, driven by `?tenant=` and `?entry=` | Does the app have addresses for work (a Book, a Chapter, Read, Review)? |
| ADR 0329 | Details and saved revisions are opened on demand | Where do they open (D26: sheet below 1100, dialog or drawer above)? |
| RFC 0047, ADR 0380 to 0382 | Numbering, Contents and Word count are controls inside the outline and Read | Do they stay in place, or gather in one "Structure" place? |

## Already decided by the system

The shell, so not asked again: the two-tier header, the app's own Home and the navigation between apps (D12 to D16); the slim status bar, which is where the **save state, the word count and the length goal** go (D18); the palette and chords (D25); toasts, undo, dialogs and sheets by the size of the loss (D26); loading, empty and error states with the mascot (D24; `empty-manuscript` is on the [illustration list](../mascot-images.md)); widths, density and type (D20, D22, D23). Writing is in the **Build** group of apps (D17).

## Questions

1. **Where does the app begin?** Three directions I would draw:
   - **A. A shelf first.** Home is what you are writing: Continue, then your Books, standalone Chapters and Scenes as a list, with "Start writing" at the top. You step into a work.
   - **B. The last draft first.** Home opens straight into the page you were on, with the shelf one step away; a new person lands on an empty page that is ready to type.
   - **C. A project at a time.** Choose a Book (or Carrier) and everything about it, outline, Editions, reviewers and counts, lives in one workspace with Write inside it; Home is a short list of projects.
2. **What sits beside the writing?** Outline, Read, Details, Review and revisions. Either they open on request in the page only (the old rule, with a sheet on a phone), or a wide window may keep the outline open beside the text when the person chooses, and remembers it. Which?
3. **Write and Read.** Keep Write and Read as two modes of one page (a switch, with Preview inside Write), or give Read its own place with its own address, so a reviewer's view and a reader's view are the same screen?
4. **Restructuring.** Move, split, extract, join and make independent live in the outline and on the selection (where they are today), or in one "Restructure" place that shows the outline and what each action would do before you choose? Reorder by drag and by keyboard is needed in both.
5. **Old decisions.** From the table above: which carry over? "All except …" is a good answer.

## Decision log

Decided with the maintainer, 2026-11-04, from the brief above.

### WR1. The app begins at a shelf

Direction A: Home is what you are writing. Continue first, then Books, standalone Chapters and Scenes as a list, with "Start writing" at the top. A person steps into a work from there. Turned down: opening straight into the last draft (B); one project at a time (C).

### WR2. A wide window may keep the outline open

On a wide window the outline, and the other side views, may stay open beside the text when the person chooses; the choice is remembered. On a narrow window they open on request, as a sheet. This replaces the old rule of nothing permanent beside the writing.

### WR3. Write and Read are modes of one page

A switch between them; Preview is inside Write. Turned down: Read as its own place.

### WR4. Restructuring is inline and seamless

The aim is a surface with as little interface as possible: dragging and dropping does as much as it can, and what dragging cannot say is offered where the person is, on the selection or the block, not in a separate place. The exact gestures are drawn in the directions.

### WR5. Old decisions

All six carry over as recommended: the outline and side views by WR2; a short toolbar and focus mode, with Preview as a mode switch inside Write (WR3); the shelf instead of a picker (WR1); an address for each work, and for Write or Read within it, instead of one page driven by `?tenant=` and `?entry=`; Details and revisions as a sheet below 1100px and a side drawer above (D26); numbering, Contents and Word count kept where the work is, with the counts also in the status bar (D18).

### WR6. The gestures of restructuring

Dragging does: reorder, nest and promote Chapters, and move writing between Editions, with a drop target that says what will happen. Selecting text and dragging it out extracts it into a Chapter or a Scene. A divider placed in the text splits it. Dropping a Chapter onto its neighbour joins them. **A right-click (or the long press and the keyboard) offers the same actions as a menu** on the block, for anyone who does not drag. Every gesture works from the keyboard and can be undone as a whole (D26).

### WR7. Direction A, with C's rail

The writing page is A: the text in the middle, an outline beside it, a grip in the margin of every block. The outline is pinned open on a wide window. On a narrower window, or when the person unpins it, it becomes C's rail: a thin strip of ticks beside the text that opens over it on hover or focus, with the same tree and the same drag. On a phone it is a panel the person opens. Turned down: B (the spine) and C (one page) as the base.

## The three directions (drawn, A with C's rail chosen)

In `directions/`: the writing page in three ways, each at rest, mid-drag and with the right-click menu, on the shell. Made-up text; nothing is saved. Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/writing/directions/index.html
```

The controls bar switches the direction and the state. All three share the same page head (title, Write/Read switch, Details, Revisions, Focus), a short toolbar and the status bar. The outline is pinned open on a wide window (WR2).

| | A. The margin | B. The spine | C. One page |
| --- | --- | --- | --- |
| Idea | The text is the page; a slim outline beside it | The outline is the work: each row tastes its Chapter; the text beside it | The whole Edition is one continuous page; Chapters are folds in it |
| Structure | A tree of titles, numbers and counts | A wide tree with the first line of each Chapter | A thin rail of ticks that opens on hover and focus |
| Drag | Grips in the margin of every block; Chapter rows take drops | Rows lift and say "Into 2 The blackout, after 2.2" | A Chapter folds to its heading while dragged |
| Cost | The least new; long works need the outline to find your place | Wide; less room for text | A very long page; moving a Chapter is a gesture on the page, not in a list |

Screens are in `directions/screens/` (`a-rest-1440.png` and so on, nine in all).

## The prototype

In `prototype/`. It links `apps/brand` in place and unchanged, and extends the shell prototype through its hooks (`ROUTES_EXT`, `PROTO_EXT`, `PROTO_CLICK`, `PROTO_SYNC`, `START_ROUTE`, `STATUS_SYNC`). The last is new: it lets an app put its own save state in the status bar. Plain HTML, CSS and JS.

### Run it

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/writing/prototype/index.html
```

A private single-page copy is built with `node build-review-copy.mjs --fragment OUT_DIR`.

### What is in it

- **The shelf (Home).** Continue, then your work as a list with a filter (All, Books, Chapters, Scenes, Carriers), and the work shared with you to review. "Start writing" opens an empty Scene at once; its chevron starts a Chapter or a Book with its first Edition. A new account sees the empty state with the `empty-manuscript` illustration slot.
- **The writing page.** Title, a Write and Read switch, Details, Revisions, Word count, focus mode, a short toolbar. A Chapter's content is an ordered list of blocks and child Chapters, so a child can sit between paragraphs. Text is editable and autosaves (the status bar says Saving, then Synced). Enter starts a new block; Backspace at the start joins it to the one above.
- **Drag and drop, by pointer.** A grip on every block, outline row and child Chapter. The drop line and a label say what will happen ("Inside “The blackout”", "After “2.1 Lamps out”"). Blocks move within the page, into a Chapter, or between Chapters (prose can sit between children). A Chapter reorders, nests and promotes. A Chapter cannot be dropped inside itself, and says why. Dragging a Chapter shows a "Join" target on the Chapter above it, which asks before joining. A selection can be dragged out by its handle onto the outline to become a Chapter. Numbers follow every move.
- **Drag and drop, by keyboard and menu.** Alt with the arrow keys moves a block or a Chapter, nests it (right) and promotes it (left). Enter on a grip opens Move to…, a list to choose a place. A right-click, the long press on a touch screen, the Menu key, or a tap on a grip opens the same actions as a menu: Move to…, make a Chapter, make a Scene, split, join with the one above, make independent, copy link, delete. A selection also shows a small bar with Make a Chapter and Make a Scene.
- **Every change can be undone as a whole** (D26), including a join and a split. A refusal says why (a split inside a list, a Chapter into itself, blocks that do not sit together).
- **Side views.** Details (title, viewpoint, numbering, private notes), Revisions (load into a draft), Review (reviewers by email, the review address, removing one), Count (own, with subchapters, the whole Edition, the selection, and the personal length goal). A drawer beside the text on a wide window, a sheet below 1100.
- **Numbering and Contents** from the Edition menu. Numbering changes every label live.
- **Read.** The assembled Edition, with the headings numbered. A reviewer sees only Read, can write a note on any passage, and the note says only they and the Authors see it.
- **Save states** in the status bar and on the page: Saving, Synced, Saved on this device, Conflict (autosave stops, Keep mine, Use theirs, Keep both), Not kept on this device, and the recovered-text banner. A failure stays visible in focus mode.
- **The outline** pinned at 1100 and up, a rail below, a panel on a phone. The controls bar switches the account (has work, new), the save state, and whether unsent text from before is kept.

### What it fakes

All data is made up and held in memory (`wr-data.js`). Nothing calls the API, saves, or syncs; the save states are switches. A paragraph stands for a text block (in the real model a text block holds many paragraphs, and Split divides it at a safe boundary). Bold and italic add the marks `**` and `_` and no more. Pictures are patterned boxes. Contents saves nothing. Edition copying, Carrier coverage, the review address, revision loading and the length goal are shown, not built.

### What was checked

- 45 scripted checks in Playwright, all passing: start writing, typing and saving, dragging (a Chapter inside, refused inside itself, the join target, a block into a Chapter, a block within the page, a selection out), Alt-arrow moves with focus kept, Move to…, the right-click menu, split and its refusal, a Chapter from a selection, join and its Undo, Roman numbering, the side views, every save state, focus mode with a failure, Read, a reviewer's note, the rail at 834, and the panel and sheet at 430.
- axe-core: no violations on seven states at 1440, 834 and 430, in light and dark (the landmark-region rule is off for the page's overlays).
- Touch targets of at least 44px at 430 on a touch device, on the shelf, Write and Read.
- No console errors.

### What was not checked

A screen reader, a real touch device (touch is emulated), colour-blindness simulation, Safari and Firefox, a very long manuscript (typing and drag speed), drag on a touch screen, and leaving the page with unsaved work (no warning is drawn).

### Findings

- A drop in the middle of a Chapter row nests, so a drop "onto its neighbour" cannot also join. Join has its own target on the Chapter above, shown while dragging.
- The right-click menu opens upward when it would run off the window; it needs the same rule in the app.
- A toast stack covers the foot of the page after a few Alt-arrow moves; a keyboard move should replace the previous toast, not add one.
- The tertiary text colour on the selected row is below 4.5:1 (the finding in the web README); the prototype uses the secondary colour there.

### Screens

In `screens/`, 32 images: the shelf, new and dark (01, 02, 24); Write, dark (03, 25); dragging a Chapter, to join, a block (04 to 06); the right-click menu, the Chapter menu, the selection bar, a Chapter made, Move to… (07 to 11); Details, Revisions, Review, Count, Numbering (12 to 16); conflict, storage failed, on this device, recovered text, focus mode (17 to 21); Read and a reviewer's note (22, 23); the rail at 834 (26, 27); 430 wide (28 to 32).

## Open questions

1. Join has its own target on the Chapter above (see the findings). Is that right?
2. Start writing opens a Scene. Should it open a Chapter, or ask?
3. The Edition menu holds Editions, Numbering and Contents. Is that the right place for them?
4. Leaving the page with unsent work: a warning dialog, or only the recovery banner on return?
