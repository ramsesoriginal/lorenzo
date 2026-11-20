# 0514 - `[[` name completion in the LorenzoScript editor

Status: accepted, built as B3 of [ADR 0494](0494-writing-moves-into-the-web-shell.md) (WR12). Quiet highlighting (B4) is not built.

## Context

An author who has used Obsidian types `[[` and expects the names of entries to be offered. The editor package has the `entity` tool (a button, with a review for a selection) and no client for names, which belong to each app and its API.

## Decision

- **`completeNames(query) => Promise<string[]>`**, an option of `createEditor`, off by default. After `[[` and a few letters (not after `]]`, a new line or sixty characters) the editor asks it for names, shows up to eight in a listbox under the toolbar, and the Arrow keys, Enter or Tab and Escape choose or dismiss. The choice is written with its closing `]]` through the same `apply` as every edit, so native undo works. An older answer never replaces a newer one.
- **Pure parts exported and tested:** `completionContext` and `complete`.
- **Writing passes the lookup**: the library's entries by `q`.

## Consequences

- The completion offers names; it does not check what the author is allowed to read beyond what the entries list returns for them.
- The semilive editor does not have it yet, for the reason given in ADR 0512.
