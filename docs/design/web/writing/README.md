# Writing: design

A fresh design of Lorenzo Writing, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. This page holds the brief, the questions and the decision log for this app.

Status: the brief is answered (WR1 to WR10), a direction is chosen, and the prototype is built, with the later slices of RFC 0047 drawn into it. Those slices are now built in the app, as the old one-page interface; [WR11](#wr11-what-the-built-features-changed-proposed) records where what was built differs from what was drawn, and what the design now says. The prototype and its screens are the drawing as it was before that and are not redrawn; WR11 wins where they differ.

## What the app is for

Writing is a quiet place to write stories, books and game lore, starting with prose, pictures or an outline and adding structure only when it helps. The writing is the page; everything else is asked for. Sources: [the app's README](../../../../apps/writing/README.md), [RFC 0047](../../../rfcs/0047-lorenzo-writing.md), ADRs [0327](../../../adr/0327-lorenzo-writing.md) to [0329](../../../adr/0329-writing-screen-and-local-recovery.md), 0341 to 0348, 0374, 0378 to 0383, 0393 to 0398, 0429 to 0438 and 0478, and [v1.0.md](../../../../v1.0.md).

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

### WR8. Answers to the first review

Start writing opens an untitled Scene at once and not a question, from WR12 (2026-11-18); the second bullet below is replaced by that.

- **Join** has its own target on the Chapter above while dragging, and asks before joining.
- **Start writing asks** what is being started: a Scene (a page to write on), a Chapter (put in a Book later) or a Book (with its first Edition).
- **The Edition menu** holds Editions, Numbering and Contents, and now also Updates and Export.
- **Leaving with unsent work warns** in a dialog (Stay and keep writing, or Leave anyway) and says what is and is not kept. The browser's own prompt covers closing the tab. A "Saving…" in the last second does not warn.

### WR9. The later slices are drawn in

From [issue #878](https://github.com/ramsesoriginal/lorenzo/issues/878) and the milestone "RFC 0047 - Lorenzo Writing", so each has a place before it is built:

| Slice | What | Where it is drawn |
| --- | --- | --- |
| W8a | A personal length goal ([ADR 0383](../../../adr/0383-personal-manuscript-length-goals.md), #967) | Count, and "goal 45%" in the status bar |
| W8b | A personal timer (ADR 0393, #998) | Count; the countdown shows in the status bar while it runs. Quiet: no sound, no notification |
| W8c | Net-new session goals (ADR 0394, #1000) | Count; "session +5 of 30" in the status bar. Deleting subtracts; moving earns nothing |
| W8d | Reviewed name and date suggestions | A Suggest tab, with the matches marked in the text; accepting links a word and never changes the wording; ambiguous names ask |
| W9 | Manuscript updates from a repository | A banner and the Edition menu open the updates, each compared as was, now and yours, with "apply all clean" that skips conflicts and edits |
| W10 | LorenzoScript and PDF export | An Export button, a dialog with a page preview, progress, and the file |
| W6, W7b | Carrier form and coverage; Contents and other special Chapters | Details; a Contents Chapter shows the generated list |

When this was drawn, ADR 0393 and 0394 were on another branch, and suggestions, updates and export were drawn from RFC 0047 alone, so their screens were proposals. All of them are built now (ADR 0393 to 0398, 0429 to 0438 and 0478), and they are not quite what was drawn: see WR11.

### WR11. What the built features changed (proposed)

Proposed 2026-11-18, after reading what was built against the drawing, and not yet decided with the maintainer. The first part says what the built app forces; the second what stands. Where the prototype and its screens show something this contradicts, this wins.

**What the built app is.** All the slices of RFC 0047 are built and tested, in the app's old one-page interface: the app's own header, a form and a list for Home, a plain text area per piece of writing, one column of closed panels (Word count, Details, Export, Saved revisions) under it, and Up and Down buttons and a panel each for Move, Join, Extract and Split in the outline. None of the drawn interface exists yet: no shell, no shelf, no outline beside the text, no grips, no drag, no menu, no status bar. So what follows changes the drawing only where the built behaviour is not what was drawn.

| # | Drawn | Built | The design now |
| --- | --- | --- | --- |
| 1 | A page of blocks you edit as rich text: Enter starts a block, Backspace at the start joins it to the one above, a selection can be dragged out | The editor is a `<textarea>` of LorenzoScript with a toolbar and a Preview tab ([the package](../../../../packages/lorenzoscript-editor/README.md)); there is no rich text. A page is an ordered list of pieces: text blocks, pictures and child Chapters. One text block holds many paragraphs | Each text block, picture and child Chapter has a grip in the margin and its own editor. Enter and Backspace do what a text area does and never split or join blocks. A block is split only where the API says it is safe, from "Split here" on the caret or the block menu, which shows the refusal and why. A text selection offers Link to an entity (and Split here); it is not dragged out |
| 2 | Select text and drag it out to make a Chapter or a Scene | Extraction takes whole, consecutive blocks (text, pictures and, for a Chapter, child Chapters); a Scene takes only text blocks and pictures, and refuses Chapters and tellings. Part of a block cannot be extracted, but it can be split first and the second part extracted | Click a grip to select a block, Shift-click or Shift-arrow to extend; the selection bar offers Make a Chapter and Make a Scene (the second is off, with its reason, when a Chapter or a telling is selected), and the range can be dragged onto the outline to do the same. To extract part of a block, split it first: the bar says so |
| 3 | A block can be dragged into another Chapter or another Edition | Chapters and tellings move between parents, with the place among a parent's blocks and children, and blocks reorder inside one page. There is no operation that moves a block or a picture into another Chapter | A block drags within its page only. Between Chapters a block is moved by extracting it and moving the new Chapter (decided 2026-11-18: no new operation). Whole Chapters and tellings drag anywhere the API allows, between Editions too |
| 4 | Dropping a Chapter on its neighbour joins them | A join needs adjacent siblings with matching sharing and current versions. It leaves the old Chapter's notes and history and a guarded link to its section. Join into parent is a second action ([ADR 0374](../../../adr/0374-join-chapter-into-parent.md)) | The join target appears only where a join is allowed, and says why when it is not. The dialog says what is kept (notes, history, the link) and what unsent text becomes (a read-only recovery view). Join into parent is a menu item on the Chapter |
| 5 | A move can always be dropped | A move is refused when the destination Edition would show the writing to readers the source does not ([ADR 0344](../../../adr/0344-atomic-manuscript-moves.md)); a retry acknowledges the first and is not applied twice | The drop target says "Not here: it would show this to reviewers of that Edition" and the keyboard path, Move to…, searches by title and says the same |
| 6 | Everything can be undone as a whole | Every structural change leaves a saved revision and a private structural checkpoint, and there is no operation that undoes one | Undo is offered for all of them: a reorder and a move are undone by moving back, and a split, an extraction and a join by an operation that restores the writing and the outline from the checkpoint (decided 2026-11-18, ADR 0494 Q2; built before the gestures are). It refuses, in words, if anything changed since. Until it exists those three ask first, in a dialog that says what is kept. The saved revision stays reachable from Revisions |
| 7 | Start writing asks Scene, Chapter or Book | Scene, Book, Chapter, Carrier and Character biography (a private Being entry written for use in a Scene) | Start writing asks all five, in this order of use: Scene, Chapter, Book, Carrier, Character biography. The shelf's filter gains Biographies |
| 8 | One Suggest tab with the matches marked in the text; accepting links the word | Three separate, explicit reviews, none of which marks or changes the prose: **Check names** (Scene Details) finds visible Beings and adds a private Scene reference; **Link to an entity** is chosen by hand on a selected name and keeps its wording; **Suggested periods** (Scene Details) finds full calendar period names and sets an empty Scene period after review. Any edit makes a scan stale and it must be run again | Suggestions are a card in Details with the three reviews, each stating what accepting does. Nothing is marked in the text. A name with several matches is flagged, not guessed. The text selection bubble holds the manual link |
| 9 | Updates: four changes, was / now / yours, "apply all clean" | Composition updates compare connected writing, attachments, placements, coverage, redirects, numbering and contents against the original copy; you choose, change by change, to keep or take; the chosen changes apply together, and an incomplete dependent choice refuses the lot. An old copy with no recorded original says so, and choosing establishes a baseline. A change that would widen access is refused until sharing is reviewed. Save or recover drafts first, in every tab. A simpler text-only comparison remains for plain copies | Updates open in a dialog from the banner and the Edition menu. Changes are grouped by kind (writing, structure, sharing, numbering and contents). "Select all clean" only ticks the changes that are clean, and never applies. The dialog says to save drafts first and lists the refusals in words |
| 10 | Export is a dialog with a page preview, progress and a PDF file | An in-page preview of saved writing; **Download LorenzoScript** makes a ZIP with the text, the original pictures and a manifest; **Print / Save as PDF** opens the browser's print dialog and says to choose Save as PDF and turn off headers; a large export is refused with a request for a smaller section; unsent changes are left out; a reviewer exports only the Edition they were given | The dialog is the preview with the two buttons and those sentences. There is no progress and no file for the PDF. It says "saved writing" and offers Save now when the editor has unsent changes |
| 11 | Review notes are written on any passage | A note belongs to a Chapter or Scene, is written in LorenzoScript, is saved explicitly (no autosave, never kept offline), and is seen by the reviewer and the Authors only. A revoked review closes within 30 seconds or on returning to the page | Read has an Add note button under each Chapter or Scene heading, a Save button and the sentence about who sees it. A reviewer whose access has been revoked sees one sentence, not an error |
| 12 | The timer and the session goal are in the status bar | They live inside Word count. Both belong to this browser tab, this account and this library, survive reload and moving between works, and end with the tab. A session goal counts net editing after Start; structure changes, loaded revisions and other authors' versions earn nothing; Finish keeps the result until a new session is started | Count holds the controls. The status bar shows a short, quiet summary while one runs ("session +5 of 30", the time left) and is a view of it, not a second place to set it. Starting a goal says where it is kept |
| 13 | Count shows own, with subchapters, the whole Edition and the selection | The draft's direct prose including unsent edits; in Read and a review, the assembled reading, a highlighted passage, or chosen text blocks. A repeated Carrier reference counts each time; footnote prose once per block; code, maths, notes and generated titles count nothing. Two personal targets, one for the draft and one for the reading | Count's scopes are "this page", "the reading", "the selection" and "chosen blocks". The status bar shows the target that goes with the mode (page in Write, reading in Read), as "goal 45%" |
| 14 | Numbering changes the labels live | Per-level format, start and restart-per-parent; per Chapter: an override, unnumbered, restart, or end a sequence. A Chapter hidden from the reader leaves no gap | Numbering is a card in the Edition menu with the levels and, on a Chapter's menu, its four overrides. Labels update in the outline and in Read |
| 15 | Contents saves nothing | An Edition or standalone Chapter tree sets the list, the depth and a template with `{title}` and `{number}`; each Chapter is included or left out on its own. A Contents Chapter shows the generated list before its own prose; Index and Glossary Chapters are written by hand and generate nothing | Contents is a card beside Numbering, with a per-Chapter include switch in the outline. The Chapter kinds say that Index and Glossary are not generated |
| 16 | A Carrier's form and coverage are in Details | They are in the Outline: **Carrier form** (ordinary prototype parents) and **Covered writing** (whole Editions, Chapters, Scenes, tellings, or a single block, across Books, between direct prose). Coverage grants no access and removing it leaves the source alone | A Carrier's outline has two sections, Form and Covers, in place of Details' coverage list. Coverage rows are labelled as references, with the source's name and an Open link |
| 17 | Edition copying and the review address are "shown, not built" | Both are built: a further Edition copies privately, without notes or history; a review address is shared with an existing signed-in account by email | They stand as drawn, with the sentence that a copy starts private |
| 18 | One address per work, and for Write and Read within it | The app has `?entry=` and `view=outline` or `view=read`, and `?review=` for a reviewer. Links to the last have been shared | The new addresses, `/write/`, `/read/` and `/review/` with `/` as the shelf (decided 2026-11-18), are added and the old ones keep working: `?review=` is never broken, and `?entry=` and `view=` redirect |

**What stands.** WR1 (the shelf, with the changes in row 7), WR2 and WR7 (the outline pinned open, the rail, the panel on a phone), WR3 (Write and Read as modes of one page; Preview is the editor's own tab), WR8 (join's own target, Start writing asks, the Edition menu, the leave dialog), WR10 (updates in a dialog, export in the page head and the Edition menu, the timer in Count and the status bar, suggestions as a side card) and the whole list of rules in "What stays true". The save, conflict, storage-failure and recovery states and focus mode stand as drawn, and the built app already does what they say, without the shell's status bar. The leave warning is only the browser's own prompt in the app today, so the dialog of WR8 is still to build; the 44px targets and the phone layouts are still to be checked on the new interface.

**What was open, and the answers (2026-11-18).** Moving blocks between Chapters: no new operation, so blocks move by extraction. Undo for split, extract and join: yes, built before the gestures. A list of what is shared with me, for the shelf: yes. A last-edited time for the shelf: not yet, so Continue is the work last opened in this browser. The addresses: yes. "Select all clean": yes. ADR 0494 has them.

### WR12. Three habits (proposed)

Asked 2026-11-18, and reviewed against the built app and WR11, not against the prototype: would an author who has only used Word, LibreOffice and Google Docs find it usable and familiar, a GM who lives in Obsidian feel at home, and a player who knows Overleaf apply their instincts, with no feature lost for anyone? The test is the first minute and then the first week: what each person reaches for, and what they would look for and not find.

**What already suits all three.** LorenzoScript is a Markdown dialect with `[[Name]]` links, footnotes, tables and a subset of TeX maths, so an Obsidian or an Overleaf person reads the source at once. The editor already has a split layout, source on one side and the preview on the other, as Overleaf has. Autosave with a visible "Saved", saved revisions, a word count, reviewers with their own notes, a review address that is a link to share, and "Download LorenzoScript" (a ZIP of plain text and the original pictures) are what a Docs, an Obsidian and an Overleaf person each look for first.

**What does not, today.** The surface: one plain text area with no highlighting, no find and replace, no `[[` completion and no formatting while you type; pasting from Word or the web gives plain text and loses the headings; the first screen asks a question before it lets you type. Nothing in the data or the structure has to change for any of that, except where the table says.

**One text, three layouts.** The same LorenzoScript text is shown as **Source** (as written, with quiet highlighting), **Split** (source and preview side by side, which the editor has) or **Live**. In Live every paragraph (every top-level block: a paragraph, a heading, a list, a table, a code block) is shown formatted, as a reader would see it, and the one you click or move into turns into a text area holding its source, until you leave it and it is formatted again. It is the way Logseq and Roam work, and it keeps the text a person owns as plain source with no engine behind it. A **Layout** menu in the page head chooses, remembered per person; Live is the default for a new person, and Source and Split stay for anyone who prefers them. Write and Read stay the two modes of the page (WR3); Ctrl+E switches them, as in Obsidian. Underneath, nothing changes: the text, the saving and the checks are the same in all three.

The changes, by how much they cost. **A** is design and wording inside the stack of ADR 0494, with no new capability. **B** is a small new capability in the app's own code. **C** is a new capability that needs a decision.

| | Habit (who) | Today | The design | Size |
| --- | --- | --- | --- | --- |
| A1 | One click to a blank page (Word, Docs, Obsidian) | A form with a kind to choose first | **Start writing** opens an untitled Scene at once with the caret in it, as the prototype did; the menu beside it starts a Chapter, a Book, a Carrier or a Character biography, each with one plain line ("A Scene is a piece you can reuse; a Chapter belongs to a Book"). This revisits WR8, which had Start writing ask first | A |
| A2 | A formatting bar and the usual keys (Word, Docs, LibreOffice) | B, I, H, a bullet and a few more, no labels; Ctrl+B, I and K | A style menu (Text, Heading 1 to 3) for the H button, labelled lists, link, table, footnote and picture; every tooltip names its key. Added: Ctrl+Alt+1 to 3 for headings, Ctrl+S for Save now, Ctrl+P for Export (print), Ctrl+E for Write and Read. The editor owns the keys while it is focused | A |
| A3 | Choose how to see it (Obsidian, Overleaf) | Write and Preview as tabs | The Layout menu: Source, Split and Live (A10) | A |
| A4 | A navigation pane (Word, Docs, Overleaf outline) | The outline lists Chapters only | Under each Chapter the headings of its own text, in order, click to jump; read from the text on the page, nothing stored | A |
| A5 | Quick open and a command line (Obsidian Ctrl+O and Ctrl+P, Word Go to) | The shell's palette | The palette also lists the works, Chapters and Scenes by name, and has New Scene, Go to heading and Layout | A |
| A6 | Share (Docs, Overleaf) | Review and reviewers | The page head's **Share** opens it, says the review address works as a link and says plainly that editing is not live: two people editing choose which version to keep | A |
| A7 | A preview on hover (Obsidian) | An entity link in Preview is plain text | A hover or focus card on a `[[link]]` in Preview and Read, from the preview card Maps already uses ([ADR 0350](../../../adr/0350-location-and-map-previews.md)) | A |
| A8 | Version history (Docs, Overleaf) | A list; load into a draft | Time, who, a name that can be given, **Compare with current** (a plain difference of two saved revisions, worked out in the browser) and Load into draft | A |
| A9 | Own your files (Obsidian, Overleaf) | Download LorenzoScript is one of two buttons in Export | Download LorenzoScript first, described as "plain text files and your pictures, in a ZIP"; Print / Save as PDF second | A |
| A10 | **Paragraphs formatted, the one you click as source** (Word, Docs, Obsidian, Logseq) | One text area for the whole piece | Live, as above. Clicking a paragraph puts the caret where you clicked; Up at its first line and Down at its last move to the neighbouring paragraph, Left and Right at its ends likewise, Escape leaves it, and Enter at the end of an ordinary paragraph starts a new one, as in a word processor (Shift+Enter is a line break; lists, code and tables keep their own Enter). Rendered paragraphs are focusable and Enter or a typed letter opens one. A selection across paragraphs selects whole paragraphs, which can then be cut, copied, deleted, formatted, moved or extracted; typing over such a selection does nothing, so nothing is lost by a stray key. Ctrl+Z and Ctrl+Y undo across paragraphs. Built as a package of its own, `@lorenzo/lorenzoscript-semilive-editor`, with the same options and the same editor object as `@lorenzo/lorenzoscript-editor`, so any of the eight apps that use that one can use it by changing an import; with no new dependency, and the text area stays the real editing surface. The block grips of WR11 belong to the text block of a piece, and these paragraphs are inside it | A, the largest of them |
| B1 | Paste from Word, Docs or the web | Plain text; headings, bold and links are lost | A pasted rich text keeps headings, bold, italic, lists, links and tables as LorenzoScript; Ctrl+Shift+V pastes plain. Done by turning the clipboard's HTML into markup | B |
| B2 | Find and replace (all three) | The browser's find, with no replace | Ctrl+F and Ctrl+H in the open text, with a match count and case; the browser's find still works | B |
| B3 | `[[` completion (Obsidian) | The link button wraps a placeholder | Typing `[[` offers the entries you may see by name; Enter links the exact wording kept, the same finder as the link review of ADR 0396 | B |
| B4 | Source you can read (Overleaf, Obsidian) | Plain monospace | Quiet highlighting of headings, bold, links, `[[links]]`, maths and footnote marks, line wrap and optional line numbers in Source and in the paragraph being edited. A small overlay behind the text area; optional | B |
| B5 | Backlinks (Obsidian) | The link review saves a backlink | "Links to this" and "Linked from" in the side drawer from the saved backlinks, if a read exists for them (to check) | B |
| C1 | A code-editor engine in place of the text area (for Live) | A `<textarea>` | **Not needed.** Decided 2026-11-18: no engine and no dependency. Live is A10, built on the text area, so Source and Split keep working without JavaScript as ADR 0106 asks | decided |
| C2 | Comments on a passage and suggested edits (Word, Docs, Overleaf) | Reviewers' notes belong to a Chapter or Scene; Authors cannot comment on their own text | Comments anchored to a passage, resolved or not, for Authors and reviewers; later, suggestions that an Author accepts. Needs a model for an anchor that survives editing | C |
| C3 | Bring a document in, take one out (Word, Obsidian) | A LorenzoScript ZIP out; no import at all | Import a .docx or a Markdown file, or a folder of them from a vault, as Chapters, with `[[links]]` going to the link review; export to .docx or Markdown. Each format is its own ADR | C |
| C4 | Search all writing (Obsidian Ctrl+Shift+F, Docs) | Nothing | A search over the text of everything you may read, in the palette | C |
| C5 | A second pane (Obsidian, Docs side panel) | One work at a time | "Open beside": a Scene or Chapter read-only beside the page at 1440px and up, for reference | C |
| C6 | Live shared editing (Docs, Overleaf) | Not built, and not planned (RFC 0047) | Stays so. The conflict dialog (Keep mine, Use theirs, Keep both) is the answer, and A6 says so | not planned |
| C7 | Pages, margins, headers, page numbers (Word) | Browser print only | Not drawn: advanced layout is deferred in ADR 0478 | deferred |

**No feature is lost.** Every row only adds to, or renames, something built, and Source and Split keep all the behaviour of the built editor. Everything in WR11 stands.

**What it means for the stack.** A1 to A9 are written into the PRs of ADR 0494 (A1 in W1, A2, A3 and A7 in W3, A4 and A5 in W4, A6 and A8 and A9 in W6). B1 to B3 are one small PR each after W3, so that a Word person can paste and find on day one. A10 is W3a in ADR 0494, a package of its own and three pull requests after W3. C2, C4 and C5 are stacks of their own; C3 is not yet.

**Answers (2026-11-18).** (a) Start writing opens an untitled Scene at once, with the kinds in its menu: yes, and it replaces what WR8 said about Start writing asking first. (b) A code-editor engine as a dependency (C1): no. The textarea stays, and Live is paragraphs formatted with the clicked one as source (A10), built in our own code. (c) Comments on a passage for Authors, and later suggestions (C2): yes. (d) Import and export of Word and Markdown (C3): not yet. (e) Search across all writing (C4): yes. (f) A second pane (C5): yes. C2, C4 and C5 are each a stack of their own after the one in ADR 0494, each with its own ADR, since each needs a model or a read the API does not have; they are not started.

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
- **Numbering and Contents** from the Edition menu. Numbering changes every label live. A Chapter can be a Contents Chapter, which shows the list made from the outline.
- **Count, the timer and the session goal.** The timer counts down from a duration of 1 to 1440 minutes, pauses, resumes and resets, and survives a reload in the same tab. The session goal counts the words you add and take away after Start. Both show in the status bar. A control switches browser storage to "Fails".
- **Suggestions.** Names and an explicit date are matched to entries you can see (made up here). Accepting links the word; a name with two matches asks which.
- **Updates.** "Harbour field guide" was copied from a repository. Four changes are compared three ways, resolved one by one or as "apply all clean", and the new Chapter arrives with the one inside it.
- **Export.** PDF or LorenzoScript source, a whole Edition or a Chapter, a page preview, progress, and a result. Private notes and goals are never included.
- **Carriers.** The Carrier's Details show its forms and what it covers, and add or remove coverage.
- **Leaving with unsent work** warns.
- **Read.** The assembled Edition, with the headings numbered. A reviewer sees only Read, can write a note on any passage, and the note says only they and the Authors see it.
- **Save states** in the status bar and on the page: Saving, Synced, Saved on this device, Conflict (autosave stops, Keep mine, Use theirs, Keep both), Not kept on this device, and the recovered-text banner. A failure stays visible in focus mode.
- **The outline** pinned at 1100 and up, a rail below, a panel on a phone. The controls bar switches the account (has work, new), the save state, and whether unsent text from before is kept.

### What it fakes

Where the built app differs from this (WR11), WR11 wins. All data is made up and held in memory (`wr-data.js`). Nothing calls the API, saves, or syncs; the save states are switches. The timer is real; the rest of these slices are shown, not built, and use made-up entries and a made-up repository. Export makes no file. A paragraph stands for a text block (in the real model a text block holds many paragraphs, and Split divides it at a safe boundary). Bold and italic add the marks `**` and `_` and no more. Pictures are patterned boxes. Contents saves nothing. Edition copying, the review address and revision loading are shown, not built.

### What was checked

- 79 scripted checks in Playwright, all passing. The first 46: start writing, typing and saving, dragging (a Chapter inside, refused inside itself, the join target, a block into a Chapter, a block within the page, a selection out), Alt-arrow moves with focus kept, Move to…, the right-click menu, split and its refusal, a Chapter from a selection, join and its Undo, Roman numbering, the side views, every save state, focus mode with a failure, Read, a reviewer's note, the rail at 834, and the panel and sheet at 430. The other 33: the timer (run, pause, resume, reload, finish quietly), the session goal (adds, subtracts, moving earns nothing), storage failure, suggestions (found, marked, accepted, undone, dismissed), updates (compared, apply all clean, conflicts left, resolved, the banner goes), a Contents Chapter, export (formats, progress, result), Carrier coverage, and the leave warning.
- axe-core: no violations on seven states at 1440, 834 and 430, and seven more (Count with the timer, Suggestions, Updates, Export, Carrier, Contents, the leave warning) at 1440 and 430, in light and dark (the landmark-region rule is off for the page's overlays).
- Touch targets of at least 44px at 430 on a touch device, on the shelf, Write and Read.
- No console errors.

### What was not checked

A screen reader, a real touch device (touch is emulated), colour-blindness simulation, Safari and Firefox, a very long manuscript (typing and drag speed), drag on a touch screen, and leaving the page with unsaved work (no warning is drawn).

### Findings

- A drop in the middle of a Chapter row nests, so a drop "onto its neighbour" cannot also join. Join has its own target on the Chapter above, shown while dragging.
- The right-click menu opens upward when it would run off the window; it needs the same rule in the app.
- A toast stack covers the foot of the page after a few Alt-arrow moves; a keyboard move should replace the previous toast, not add one.
- Splitting and joining blocks with Enter and Backspace, and dragging a text selection out, are drawn for a rich-text surface the app does not have; the editor is a plain text area (WR11, rows 1 and 2).
- The tertiary text colour on the selected row is below 4.5:1 (the finding in the web README); the prototype uses the secondary colour there.

### Screens

In `screens/`, 45 images (33 to 45 are the later slices: the timer, the session goal, suggestions, updates, a Contents Chapter, export, a Carrier and the leave warning); the first 32: the shelf, new and dark (01, 02, 24); Write, dark (03, 25); dragging a Chapter, to join, a block (04 to 06); the right-click menu, the Chapter menu, the selection bar, a Chapter made, Move to… (07 to 11); Details, Revisions, Review, Count, Numbering (12 to 16); conflict, storage failed, on this device, recovered text, focus mode (17 to 21); Read and a reviewer's note (22, 23); the rail at 834 (26, 27); 430 wide (28 to 32).

### WR10. Answers to the second review

The timer and the session goal show in the status bar while they run, and in Count. Updates open in a dialog. Export is both an icon in the page head and an item in the Edition menu. Suggestions stay a side tab with the matches marked in the text.

## Open questions

None for the writing app. The checks are re-run once on the final screens before the write-up.
