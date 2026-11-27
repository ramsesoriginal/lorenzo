# 0528 - UI-H: retiring the old frame, and auditing the apps

Status: proposed, 2026-11-27, asked for by the maintainer ("Let's tackle UI-H", with a design and an implementation audit of every app as its last part). Slice UI-H of [RFC 0050](../rfcs/0050-the-web-interface.md). Nothing in it is built yet.

## Context

[ADR 0426](0426-the-web-shell-grows-in-app-shell-opt-in.md) made the web shell opt-in (`AppPage shell="web"`), so each app could move in its own slice and UI-H would remove the old one-row header once none used it. The slices are done: the account hub, Calendars, Sessions, Maps, Writing, Beings, Inventory ([ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md)) and Social ([ADR 0527](0527-social-moves-into-the-web-shell.md)) draw their pages in the shell. Two web apps are not on `AppPage` at all: **Bench** (the authoring workbench, its own layout, "stays its own thing" in the design's follow-ups) and **Legal** (static notices with a layout of their own, in two languages).

A first look at the code (this ADR's survey) found:

- The old frame is still in `packages/app-shell`: `SiteHeader.astro`, `SiteFooter.astro`, the `shell` prop that defaults to it, and the calls the old header ignores (ADR 0426). Every app that uses `AppPage` now passes `shell="web"`, so that branch has no user.
- The apps carry copies of one another. Byte-identical or near-identical files in several apps: `config.ts` (five identical, nine in all), `auth.ts` (nine, about 85 lines each), `lastTenant.ts` (three), `statusLine.ts` (three), `tenants.ts` (three), `read-cache.ts` (four, although [`packages/read-cache`](../../packages/read-cache) exists), `dom.ts` (four, about 250 lines each, with eleven functions in common: `el`, `button`, `field`, `select`, `icon`, `link`, `linkButton`, `loading`, `message`, `submit`), `sign-in.ts`, `names.ts`, `prefetch.ts`. [ADR 0526](0526-the-entity-parts-package.md) did this for Beings and Inventory; the rest of the apps have not had it.
- Each app's stylesheet still has rules of its own for buttons, fields, headers and cards (`.icon-btn`, `.day-button`, `.seg-chip`, `.stat-value-btn`, `.map-point-button`, among others). Some are real components of that app; some duplicate what `apps/brand` or the shell already draws.

## Decision

UI-H is built in this order, each step its own small, tested pull request, stacked, none merged by the author:

| Step | What |
| --- | --- |
| H1 | **Retire the old frame.** `AppPage` always draws the web shell; `SiteHeader`, the old footer and the opt-in prop go; what only the old header drew (and `bindShell`'s no-op calls) goes with them. Bench and Legal are decided in H1, not assumed: either each moves onto the shell, or the ADR says why it stays and what it must still share with the shell (the legal links, the appearance, the lockup) |
| H2 | **Styles.** Each app's rules for buttons, fields, headers, footers and cards that restate the brand or the shell's are removed, and what is left is named a component of that app. A check in CI says an app's stylesheet may not define the brand's own classes again |
| H3 | **The design audit.** Every app against its design (`docs/design/web/<app>`), screen by screen, in both themes and at the three widths: what is missing, what differs on purpose, what differs by accident. Each app gets a table in this ADR, and what is a plain defect is fixed in its own pull request |
| H4 | **The implementation audit.** Functionality against what the app did before it moved and against its RFC and ADRs (nothing lost), the apps against each other (the same thing behaving the same way: sign-in and sign-out, the library switcher, the palette, Undo, refusals and 412 in words, empty and error states, keyboard, the phone), and the end-to-end suites as the net |
| H5 | **Extractions.** From H4's list, what is copied becomes packages, one pull request each, the way ADR 0526 did it: the shared sign-in and Authgear glue, the app configuration, the last-library memory, the DOM helpers, the read cache, the status line. Each is a package with its own tests that the apps import, and the copies are deleted in the same pull request |

The audit steps (H3, H4) write their findings here as tables, the way ADR 0524 and 0527 did, so what was found and what was decided is in one place. A finding that needs a decision from the maintainer is asked, not decided.

## Consequences

- When it is built, every web page is drawn by one frame and one set of styles, the apps agree with their designs or say where they do not, and the code the apps share is in packages rather than in copies.
- H1 changes `packages/app-shell`, which every app builds on: its pull request is checked against every app's end-to-end suite, not just the ones the dependency graph names.
- H5 touches every app. It goes one extraction at a time so that a regression is one revert.
- Bench and Legal are decided by H1, which may add a slice for either.
