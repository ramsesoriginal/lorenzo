# 0419 - Lorenzo Writing, redesigned

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/writing](../design/web/writing/README.md), WR1 to WR10, and D31. Follows [RFC 0047](../rfcs/0047-lorenzo-writing.md).

## Context

Lorenzo Writing is built in slices from RFC 0047. The maintainer asked for its interface to be designed as a whole, with the later slices drawn in, so each has a place before it is built.

## Decision

- **The app begins at a shelf** (WR1): Home is what you are writing, with Continue first, then Books, standalone Chapters and Scenes, and "Start writing" at the top, which asks what is being started (a Scene, a Chapter or a Book with its first Edition).
- **Write and Read are modes of one page** (WR3), with Preview inside Write. Each work has an address, and so do Write and Read within it.
- **The page is the text in the middle, an outline beside it and a grip in the margin of every block** (WR7). The outline is pinned open on a wide window (WR2) and the choice is remembered; on a narrower window, or when unpinned, it is a rail of ticks that opens over the text with the same tree and drag; on a phone it is a panel.
- **Restructuring is inline and seamless** (WR4, WR6): dragging reorders, nests and promotes Chapters and moves writing between Editions, with a drop target that says what will happen; selecting text and dragging it out extracts it into a Chapter or a Scene; a divider in the text splits it; dropping a Chapter onto its neighbour joins them, after asking. **A right-click, a long press and the keyboard offer the same actions as a menu.** Every gesture can be undone as a whole.
- **Details and revisions** are a sheet below 1100px and a side drawer above; the Edition menu holds Editions, Numbering, Contents, Updates and Export. Leaving with unsent work warns and says what is and is not kept.
- **The later slices are drawn** (WR9): a personal length goal, a personal timer and net-new session goals in the status bar; a Suggest tab for names and dates that links a word and never changes the wording; manuscript updates compared as was, now and yours; export with a preview.
- **Writing is in Build** (D31).

## Consequences

- The timer and session goal follow ADRs 0393 and 0394, which are on another branch; suggestions, updates and export are drawn from RFC 0047 alone, so their screens are proposals.
- The old one-page-driven-by-query-string design is replaced by addresses for each work.
