# 0254 - Bench: the status bar and the conflict review

Status: accepted

## Context

A conflict (a change made elsewhere to what the person also changed) or a refusal showed only as a row in the entry it concerned. A person with several entries waiting had no overview and no way to see "what was it, what did I write, what is there now" in one place.

## Decision

- **A status bar** under the workbench: the sync state (`Synced`, `Waiting to sync (n)`, `Needs attention (n)`, `Conflict (n)`, the worst first), the selection (`Name · kinds · N links`), and the connection (`Online` / `Offline`). When something needs a look, the sync state is a button.
- **A conflict review dialog** lists every conflict and refusal across entries: the entry (a link to it), the field, and for a conflict **Was / Mine / Theirs** with *Keep mine* and *Use theirs*; for a refusal the server's words with *Try again* and *Discard*. It follows the outbox while open and closes when nothing is left. It says that other entries keep syncing meanwhile, which is how the command layer already works (a conflict holds only its own entry).
- It uses the commands' existing actions (`keepMine`, `discard`, `retry`); nothing about syncing changes. The words for a field and a value are the ones the entry's own conflict row uses.
- Not in this slice: the bar's offline details ("MB kept", download progress) need B4.
