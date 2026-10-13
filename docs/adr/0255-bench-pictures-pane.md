# 0255 - Bench: the Pictures pane and the inherited picture

Status: accepted

## Context

An entry's main picture can be set in the entry pane ([ADR 0243](0243-bench-the-main-picture.md)). The prototype also had a pane for pictures: it shows the picture an entry gets from above, takes a dropped or pasted file with a look first, and lists every picture.

## Decision

- **The inherited picture is a reading, not a stored fact.** The API holds only an entry's own picture. The pane shows the entry's own picture, else the nearest one above it (first parent first; `pictureSource`, a pure function with tests), and says so ("Shows Ashfang's picture, which it inherits."). "Use its own picture…" chooses a file for the entry itself. Nothing is written to make an entry inherit.
- **A file is seen before it is sent.** Choosing, dropping or pasting a PNG, JPEG, WebP or GIF stages it with a preview, its name and size; *Use this picture* sends it through the existing path (`Pictures.set`), *Cancel* drops it. Another type is said, not sent.
- **An overview** of the repository's entries as tiles with their small picture (*All pictures* / *Entries without their own*); a tile opens the entry. Pictures are read 48 at a time ("Show more"), each once, so the overview does not read the whole repository.
- Online only and not a command, as in ADR 0243. The gallery (several pictures per entry) is not part of this.

## Consequences

- An entry's inherited picture shows in this pane only; the entry pane and text links still use its own.
