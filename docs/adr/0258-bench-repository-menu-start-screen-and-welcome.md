# 0258 - Bench: the repository menu, the start screen and the first-run welcome

Status: accepted

## Context

The title bar chose a repository with a plain `<select>`, which showed no role and gave a person with no repository nothing to read. Nothing told a new person what Bench does or where to start.

## Decision

- **A repository menu** (a button naming the open repository, `aria-haspopup="menu"`, arrows, Escape, a check on the open one) lists the repositories the person authors with their role (Owner, Organiser, Author) and ends in **Your repositories…**. Choosing another remembers it and reloads, as the select did. The palette keeps "Open repository …" for each.
- **A start screen** ("Your repositories", a dialog) lists them with an *Open* button each (the open one says *Open now*). It opens from the menu or the palette, and by itself when a signed-in person has no repository: it says how one is made (the `lorenzo` command line, or an organiser giving them the author role) instead of leaving an empty editor.
- **A first-run welcome** is a strip under the title bar (not a modal, so nothing is blocked behind it) with four points: changes show at once and can be undone, Ctrl+K, tabs and layouts, `[[` and `{weight}`. *Got it* remembers it on the device (`bench:welcomed`); "Show the welcome" in the palette brings it back.
- **The sample page shows the same menu and start screen** with one sample repository, so they can be tried and tested without sign-in.
- Not in this slice: pinning, a repository "kept offline" and download progress (B4), and creating a repository from Bench (the API route exists; the form is its own slice).

## Consequences

- The `Repository` `<select>` is gone; anything that drove it (the palette commands) calls the same remember-and-reload directly.
