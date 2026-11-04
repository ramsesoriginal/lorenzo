# Writing: design

A fresh design of Lorenzo Writing, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. This page holds the brief, the questions and the decision log for this app.

Status: the brief and its questions. No direction is chosen yet.

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

Nothing is decided here yet.
