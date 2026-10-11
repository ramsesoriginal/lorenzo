# 0251 - Bench: editing a text where it is drawn

Status: accepted

## Context

A description or a note was a field with its preview beside it. The design ([prototype](../design/bench/README.md)) shows the text as it reads, and the maintainer's brief for it is: the block with the caret is source and editable, the rest is drawn; clicking a block shows its source, and moving into it with the keyboard does the same. There is no edit button.

## Decision

- **A text is a list of blocks** (`shell/blocks.ts`): paragraphs, lists, headings, code and quotes, told apart by blank lines (a blank line inside a fenced code block does not end it). An empty text is one empty block.
- **One block is source at a time.** Clicking a drawn block turns it into a text field holding its source, with the caret at the end. The arrow keys leave a block at its first or last line (and Left at the start, Right at the end) into the one before or after, which turns into source with the caret at the near end. Tabbing into the text puts the caret in the first block.
- **Enter** ends a paragraph and starts the next, with what was after the caret in it. In a list it goes on with the list (the same marker, the next number) and on an empty item ends it; in a fenced block it is a line break; Shift+Enter is always a line break. **Backspace** at the start of a block joins it to the one before. **Escape** leaves the source and draws the block again. A block left empty is dropped.
- **Each block is drawn on its own,** through the same link resolver as before ([ADR 0233](0233-bench-links-to-entries-in-text.md)), so links, pictures and `my/` links work. What links across blocks (a footnote and its definition) is drawn as two separate blocks; that is the cost of drawing one block at a time.
- **Writing it down.** Typing marks the text changed; leaving the text (the focus going elsewhere, Escape, or following a link) writes it, once, as the blocks joined with one blank line, and only if it differs from what it was. Looking at a text, or clicking into it, writes nothing. The picker (`[[`, `![[`) and the link buttons work in the block being written; the note about links that stay text is kept under the editor.
- **A page drawn again while writing** (another change arrived) puts the block back as source with the caret where it was: the editor remembers its blocks and which was source, by its key, until it is written.

## Not in scope

Placing the caret where a drawn block was clicked (it goes to the end of the block); selecting across blocks; the stat chips of the next slice.

## Consequences

- A text field for a description or a note exists only while its block is source, so a test or a screen reader reaches it by activating the block first. The drawn text has the label "Description, as it reads".
