# 0224 - Bench: the description and the notes

Status: accepted, decided with the maintainer on 2026-10-09. The third part of slice B3 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md). Builds on [ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md), [ADR 0222](0222-ids-made-by-the-client.md) (ids made by the client) and [ADR 0223](0223-bench-making-entries-and-what-waits-for-them.md).

## Decision

- **Three commands.** `description.set-text` changes the text of the entry's description; `note.add` adds a note; `note.set-text` changes the text of one of its notes. Each carries a base and a new text like every command, and the text is LorenzoScript, kept exactly as written.
- **What an entry holds.** The entry detail the panes read already lists the information the caller may read. Bench takes the one of type `description` as the description and those of type `note` as the notes, each with the text of its first text payload. What is not text (a picture, a number) and other types (a rumour) are left alone; they are not shown, and not touched.
- **Where a text is written.** An existing text is a `PATCH` of its payload, with the payload's own `updated_at` as a weak `If-Match` (ADR 0108), the route inventory-web's editor uses. A description that is not there yet, and a note, are made as new information under an id the client made (ADR 0222), restricted (not public) by default, in the person's browser language. Making one twice is a replay, not a second note.
- **The compare is the one of ADR 0221.** Before a text is written the runner reads the entry and compares the text three ways: the server has mine (synced, nothing sent), has the base (send), or has something else (**Conflict**, with their text shown and the choice of Keep mine or Use theirs). A description deleted elsewhere is a conflict, not a silent re-creation. A note that is gone is **needs attention**. Text is never merged by Bench (RFC 0039 section 5); the line-by-line review is B5.
- **What waits for what.** A note's later edits wait for the command that makes it, so a note added offline and edited again is sent in that order. Cancelling an unsent note takes its edits with it. A sent note is not undone here (that is deleting; RFC 0041 K9), but an edit of a text is, by queuing its inverse. Two changes to a description that is not there yet make it once and write the second.
- **The screen.** Each text is a field and, beside it, what it reads as, from `@lorenzo/lorenzoscript`, which escapes everything it renders. The preview follows what is typed; the change is written down as a command when the field loses focus, so a half-typed sentence is never sent. Typing survives the page redrawing for another entry's change. Entity links in a text show as plain text until Bench resolves them (the links and images of RFC 0042 W-C); the toolbar of `@lorenzo/lorenzoscript-editor` comes with that.
- **Not in this slice**: deleting a note, a note's title, who may read a note (public or restricted), several languages, a description's own place in a repository's update (what a copy carries of the text is RFC 0037's).

## Consequences

- A person can now write what an item is and keep notes on it, offline, in Bench; nothing else of an entry's text is lost to it.
- Titles of notes are fixed ("Note"). A note someone else titled keeps its title and shows it in its label.
- The read of the information is the viewer's: a text restricted from the person is not shown and is not touched, so a description they cannot see can show as empty and a first write would be a second description. That is not possible for an author of a repository, who reads all of it, and is the reason Bench is repository-first (RFC 0039).
