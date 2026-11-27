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
| H1 | **Retire the old frame.** `AppPage` always draws the web shell; `SiteHeader`, the old footer and the opt-in prop go; what only the old header drew (and `bindShell`'s no-op calls) goes with them. **Legal moves onto the shell** (decided by the maintainer, 2026-11-27): its two languages and its operator profile stay, its own layout goes. **Bench stays as it is** (decided likewise): it has its own workbench frame, and keeps sharing the shell's appearance, theme and legal links, which H4 checks |
| H2 | **Styles.** Each app's rules for buttons, fields, headers, footers and cards that restate the brand or the shell's are removed, and what is left is named a component of that app. A check in CI says an app's stylesheet may not define the brand's own classes again |
| H3 | **The design audit.** Every app against its design (`docs/design/web/<app>`), screen by screen, in both themes and at the three widths: what is missing, what differs on purpose, what differs by accident. Each app gets a table in this ADR, and what is a plain defect is fixed in its own pull request |
| H4 | **The implementation audit.** Functionality against what the app did before it moved and against its RFC and ADRs (nothing lost), the apps against each other (the same thing behaving the same way: sign-in and sign-out, the library switcher, the palette, Undo, refusals and 412 in words, empty and error states, keyboard, the phone), and the end-to-end suites as the net |
| H5 | **Extractions.** From H4's list, what is copied becomes packages, one pull request each, the way ADR 0526 did it: the shared sign-in and Authgear glue, the app configuration, the last-library memory, the DOM helpers, the read cache, the status line. Each is a package with its own tests that the apps import, and the copies are deleted in the same pull request |

The audit steps (H3, H4) write their findings here as tables, the way ADR 0524 and 0527 did, so what was found and what was decided is in one place. A finding that needs a decision from the maintainer is asked, not decided.

## Open points in the earlier UI ADRs

Read from ADR 0409 to 0527, the design's follow-ups and issues #1129 and #1020. Each is sorted by what stops it. The first group is done in the course of UI-H, as part of the audit steps named; the others wait for something and say for what.

**Can be done in UI-H (nothing outside the web apps is needed)**

| Point | From | Done in |
| --- | --- | --- |
| The apps' own copies of components, helpers and sign-in code become packages | [0524](0524-beings-and-inventory-move-into-the-web-shell.md), this ADR's survey | H5 |
| Add a note as a dialog, in Beings (it is inline) | 0524 | H3 |
| Libraries in the account hub: the design's cards and the "Libraries / name" crumb | #1129 | H3 |
| Campaigns in the account hub as drawn (a "New campaign" button that opens the form; players, links and notifications as one scroll, not tabs in a card) | #1129 (screens 06 to 08) | H3 |
| The hub's Author variant of People compared with screen 11; the hub's pages at 834 and 2200 px wide, with a screen reader, in Safari and Firefox (the checks the design did not cover) | #1129 | H3 |
| The `/debug/me` link; the repository listing for reading that `/beings` kept in the hub and the Beings app's test for it | #1129 | H4 |
| All beings / Mine as the shell's two tabs, not a toolbar choice: the shell tells tabs apart by path only | 0524 | H3, with a small change to the shell |
| The design's "starts Greening 3" and "Not placed in order" on a Session row in Sessions | [0441](0441-sessions-moves-into-the-web-shell.md) | H3 (a read of each Session's start; if it is too many reads, H3 says so and the row stays) |
| "Groups that disagree" in Problems (Social), and an entry's page linked from other apps | 0527 | H3, once the maintainer says what "disagree" means; the links once a first app asks for one |
| The new matrix control "New cells are" as its own select | 0527 | H3 |

**Waits for an API**

| Point | From | Waits for |
| --- | --- | --- |
| "Seen by" on a being | 0524 | An entry's audience can be read only for facts and calendar entries, not for beings |
| The Sessions a being takes part in without being named in their text | 0524 | A read of its own |
| Appearance (density, theme, motion) and saved views kept in the account | #1129, [0411](0411-web-widths-containers-density-and-type.md) | An API for a person's preferences |
| Dates on the Events list rows with the strip's ticks in Social | 0527 | A read of every Event's dates, which Calendars does one by one |
| A stored preview of a Map on save | [0465](0465-maps-moves-into-the-web-shell.md) | Only if drawing in the browser proves too slow in a large library |
| Undo of a hand over (Beings, Inventory) | 0524 | A way to take an item back that the API offers |
| Inventory's pages (I6) | 0524 | Decided there, not scheduled |

**Waits for art or a decision**

| Point | From | Waits for |
| --- | --- | --- |
| The `empty-sessions` and `empty-beings` mascots | [0441](0441-sessions-moves-into-the-web-shell.md), 0524 | The brand's art |
| The design's "This month" shortcut on the time filter | [0440](0440-calendars-moves-into-the-web-shell.md) | A calendar having a current date, which is not built |
| The "Restricted" chip of an Event | 0440 | Nothing: left out on purpose, a hidden Event is never shown |

H3 turns the first table into pull requests, each named for one app and one screen, so that a reviewer can look at one thing at a time.

## Consequences

- When it is built, every web page is drawn by one frame and one set of styles, the apps agree with their designs or say where they do not, and the code the apps share is in packages rather than in copies.
- H1 changes `packages/app-shell`, which every app builds on: its pull request is checked against every app's end-to-end suite, not just the ones the dependency graph names.
- H5 touches every app. It goes one extraction at a time so that a regression is one revert.
- Legal is rebuilt on `AppPage`, which needs the shell to draw a page with no sign-in and no library (the legal pages are public); H1 settles that. Bench is left out of H1 to H3, and is audited in H4 only for what it should share with the shell.
