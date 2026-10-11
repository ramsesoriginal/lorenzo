# 0256 - Bench: the pack editor

Status: accepted

## Context

A pack's contents are a strict list in its description ([ADR 0145](0145-pack-contents-in-the-description-and-handing-a-pack-out.md)): `- N x [Label](slug)`, two spaces per level, at most three levels, a line without a link being plain text. Editing it by hand in Markdown works but is easy to get wrong. The prototype edits it as rows.

## Decision

- **A Pack pane** reads the selected entry's description with the ADR 0145 grammar (`shell/packModel.ts`, pure and tested) and shows the list as rows: count, name (a button that opens the entry; plain text is marked), weight, and ↑ ↓ ← → and ×. Anything that does not parse as a row stays exactly where it was: the prose before and after the list is kept, and every change writes the whole description back through `setDescription`, so it is a command, undone and synced like a text edit.
- **Moves keep the structure.** A row moves with what is inside it past the next row of its level; → puts it (and its contents) into the row above, ← takes it out; at most three levels; removing a container lifts its contents. Alt+↑/↓/→/← do the same from the keyboard on the row itself, and the cursor stays on the row.
- **Adding:** an entry from the repository (linked by its link name; plain text if it has none), or a line of plain text. **Make this an item** turns a plain row into a link to a chosen entry.
- **Show as text** edits the same description as Markdown; the rows reread it.
- **Total weight:** each linked row's weight (the entry's Weight stat, inherited included, read once per link name through `resolve`) times its count and the counts of the containers it is in; it says how many rows have a weight.
- **A list with other text between its lines** is shown but not edited as rows (editing could not keep that text in place); it says where to edit it.

## Consequences

- No change to the API or to how a pack is given out. The grammar is as strict as before, so a row the pane cannot parse is not handed out either.
- A renamed link name is not followed (ADR 0145's note stands).
