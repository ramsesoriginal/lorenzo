# 0440 - Calendars moves into the web shell

Status: accepted, decided with the maintainer on 2026-11-08. Part of [RFC 0050](../rfcs/0050-the-web-interface.md); it implements the Calendars part of UI-E ([#1016](https://github.com/ramsesoriginal/lorenzo/issues/1016)) with [ADR 0420](0420-calendars-and-sessions-redesign.md) and the design in [docs/design/web/calendars-sessions](../design/web/calendars-sessions/README.md), on the shell of [ADR 0426](0426-the-web-shell-grows-in-app-shell-opt-in.md), as the hub did in [ADR 0428](0428-the-account-hub-moves-into-the-web-shell.md).

## Context

Calendars draws its own page as a one-row header, a `wrap` and a footer, and moves between its pages with Astro's client router, so what it holds in memory (the read cache, prefetched Events) lives from one page to the next. The design (CS1 to CS7) puts the month, Events and Clocks in the web shell's frame, with the month as a grid beside a day panel.

## Decision

- **The frame is the web shell** (`AppPage shell="web"`, the `list-detail` template). The tabs are Calendar, Events and Clocks. Calendar stays the current tab on a calendar's page and on an entry (`NavItem.also`). Clocks is offered to a library that has a clock and to anyone who can write, since the first clock is made there.
- **The shell can be bound again.** An app with a client router binds the shell on every page. `bindShell` now lets go of what the previous page held on the document and the window (the keys, the docked sheet's Escape and outside press, the unsent warning, the clock) before it binds, so nothing answers for a header that is gone.
- **The account button's name holds the letters it shows** ("DO, account menu"), which is what a screen reader and WCAG 2.5.3 want, and which the shell's accessibility check found.
- **A page that says its own loading and a page that has a welcome both work;** Calendars keeps its welcome, which is what a signed-out visitor sees.
- **The library switcher, the palette, the apps sheet and the status bar** are the shell's. The status bar says "Synced" with the time; the in-world date is for a Session (CS1), so Calendars shows none.
- **Appearance is the shell's dialog.** The old light/dark toggle is gone; a signed-in person chooses in Appearance (the account menu), and a signed-out visitor has the system's.

## Consequences

- The e2e tests that drove the old header (the toggle, the "Account" link, "Log out") drive the account menu and the Appearance dialog instead.
- The pages' contents move to the design in the slices that follow, each its own pull request on the one before.
