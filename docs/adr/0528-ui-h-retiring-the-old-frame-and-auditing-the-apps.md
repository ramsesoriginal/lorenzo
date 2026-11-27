# 0528 - UI-H: retiring the old frame, and auditing the apps

Status: accepted, 2026-11-27 (H1 built, the rest decided and not built), asked for by the maintainer ("Let's tackle UI-H", with a design and an implementation audit of every app as its last part). Slice UI-H of [RFC 0050](../rfcs/0050-the-web-interface.md). Nothing in it is built yet.

## Context

[ADR 0426](0426-the-web-shell-grows-in-app-shell-opt-in.md) made the web shell opt-in (`AppPage shell="web"`), so each app could move in its own slice and UI-H would remove the old one-row header once none used it. The slices are done: the account hub, Calendars, Sessions, Maps, Writing, Beings, Inventory ([ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md)) and Social ([ADR 0527](0527-social-moves-into-the-web-shell.md)) draw their pages in the shell. Two web apps are not on `AppPage` at all: **Bench** (the authoring workbench, its own layout, "stays its own thing" in the design's follow-ups) and **Legal** (static notices with a layout of their own, in two languages).

A first look at the code (this ADR's survey) found:

- The old frame is still in `packages/app-shell`: `SiteHeader.astro`, `SiteFooter.astro`, the `shell` prop that defaults to it, and the calls the old header ignores (ADR 0426). Every app that uses `AppPage` now passes `shell="web"`, so that branch has no user.
- The apps carry copies of one another. Byte-identical or near-identical files in several apps: `config.ts` (five identical, nine in all), `auth.ts` (nine, about 85 lines each), `lastTenant.ts` (three), `statusLine.ts` (three), `tenants.ts` (three), `read-cache.ts` (four, although [`packages/read-cache`](../../packages/read-cache) exists), `dom.ts` (four, about 250 lines each, with eleven functions in common: `el`, `button`, `field`, `select`, `icon`, `link`, `linkButton`, `loading`, `message`, `submit`), `sign-in.ts`, `names.ts`, `prefetch.ts`. [ADR 0526](0526-the-entity-parts-package.md) did this for Beings and Inventory; the rest of the apps have not had it.
- Each app's stylesheet still has rules of its own for buttons, fields, headers and cards (`.icon-btn`, `.day-button`, `.seg-chip`, `.stat-value-btn`, `.map-point-button`, among others). Some are real components of that app; some duplicate what `apps/brand` or the shell already draws.

## Decision

UI-H is built in this order, each step its own small, tested pull request (or a short stack), stacked, none merged by the author. An API change is first its own ADR (RFC 0050's slices are decided before they are built) and lands before the page that uses it.

| Step | What |
| --- | --- |
| H1 | **Retire the old frame.** `AppPage` always draws the web shell; `SiteHeader`, the old footer and the opt-in prop go, with what only the old header drew and `bindShell`'s no-op calls. **Legal stays as it is** (the maintainer first chose the shell, then changed their mind, 2026-11-27: moving it is work that is not needed now): it keeps its own layout, and H7 only checks that it shares the brand's styles and the legal links the apps use. **Bench stays as it is** (decided by the maintainer) and keeps sharing the shell's appearance, theme and legal links, which H7 checks |
| H2 | **Styles.** Each app's rules for buttons, fields, headers, footers and cards that restate the brand's or the shell's are removed; what is left is named a component of that app. A CI check says an app's stylesheet may not define the brand's own classes again |
| H3 | **The API the open points need,** four small slices, each its own ADR, tests and `schema.d.ts`: **A1** who may read a being (an audience on a being, as facts and calendar entries have, and a read of it); **A2** the Sessions a being takes part in, read from the play record as well as from the text; **A3** a person's preferences in the account (density, theme, motion) and saved views; **A4** a calendar's current date, a field on the calendar, and a read of the dates something is written on within a period, for the strip's ticks |
| H4 | **What those give the apps.** "Seen by" on a being; "Sessions this being takes part in" on its Where-it-appears page; the shell keeping appearance in the account (the device's value stays the fallback when signed out or offline) and saved views in Social, Maps and the lists that have filters; the strip's ticks in Social's Event chooser; the "This month" shortcut in Calendars' time filter and wherever it is used, and "today" where a calendar has one |
| H5 | **The mascots.** The maintainer prepares them in a separate branch (all the empty and device states the designs name, not only `empty-sessions` and `empty-beings`); this step merges that branch, lists every state's slot in `packages/app-shell/src/states.ts` against the art, and draws each in the places that say "the words stand" until it exists |
| H6 | **The design audit.** Every app against its design (`docs/design/web/<app>`), screen by screen, in both themes and at three widths: what is missing, what differs on purpose, what differs by accident. Each app gets a table in this ADR; a plain defect is fixed in its own pull request. The first table below is H6's starting list |
| H7 | **The implementation audit.** Functionality against what the app did before it moved and against its RFC and ADRs (nothing lost), and the apps against each other (sign-in and sign-out, the library switcher, the palette, Undo, refusals and a 412 in words, empty and error states, keyboard, the phone), with the end-to-end suites as the net |
| H8 | **Extractions.** From H7's list, what is copied becomes packages, one pull request each, as ADR 0526 did: the Authgear sign-in glue, the app configuration, the last-library memory, the DOM helpers, the read cache, the status line. Each is a package with its own tests that the apps import, and the copies are deleted in the same pull request |

The audit steps (H6, H7) write their findings here as tables, the way ADR 0524 and 0527 did. A finding that needs a decision from the maintainer is asked, not decided. H8 comes last so that the audits say what is really shared and not only what looks it.

### H1, as built

`AppPage` draws the web shell and nothing else: `SiteHeader.astro`, `SiteFooter.astro`, the `shell` prop and the branches of `bindShell` that served the old header are gone, and the eight apps no longer pass `shell="web"`. The tests of the old header are removed; the shell's own tests now render the one frame. The brand's `.site-header`, `.site-navigation` and `.brand-product` rules stay for now: the brand's static previews still draw with them, so H2 removes them together with the previews that use them. The `data-site-header` hook stays too, since the shell's own header carries it and the apps' tests and Writing's focus mode read it.

### H2, as built

The survey for H2 compared every app's stylesheet with the brand's and with each other:

- **Duplicated by Maps, Sessions and Social**: thirty-three identical rules (the page head and crumbs, a section's head, a collapsible panel, an ordered list, a checkbox with its words, how a busy or empty region looks, the touch heights of those). They are now one sheet, `packages/app-shell/src/page-parts.css`, which each of the three imports at the top of its own; their own sheets lost 200, 200 and 160 lines. It is not in the brand because Writing and Calendars define `.page-head` and `.section-head` differently, and a global brand rule would have bled into them.
- **Beings** repeated the brand's `.visually-hidden` and a touch height for `.btn` that the brand already gives; both are gone.
- **The brand's `.site-header`, `.site-navigation` and `.brand-product`** served only the old header and the brand's own preview pages. The rules left `layout.css` and `components.css`, and the previews draw their chrome with `.preview-header` from `apps/brand/preview/preview.css`, which the apps never load.
- **A check in CI.** `apps/brand/tests/class-clash.test.mjs` fails when an app (not Bench, which does not load the brand) writes a rule that is only a brand class, for example `.btn { … }` or `.text-input:disabled { … }`. Grouped selectors that add to a list (a touch height) and scoped ones (`.panel .btn`) are an app's own and pass.
- **Left for H8**, because they are shared components and not restated brand: `.home-tiles` (account hub and Calendars), and the stat bar, the search field and the descriptions of Beings and Inventory. Bench keeps its own styles.

## Open points in the earlier UI ADRs

Read from ADR 0409 to 0527, the design's follow-ups and issues #1129 and #1020. The maintainer chose (2026-11-27) to pull the API and art work in as well, so most of what waited is now H3 to H5. What is still outside UI-H is the last table.

### Done in UI-H's audits (nothing outside the web apps is needed)

| Point | From | Done in |
| --- | --- | --- |
| The apps' own copies of components, helpers and sign-in code become packages | [0524](0524-beings-and-inventory-move-into-the-web-shell.md), this ADR's survey | H8 |
| Add a note as a dialog, in Beings (it is inline) | 0524 | H6 |
| Libraries in the account hub: the design's cards and the "Libraries / name" crumb | #1129 | H6 |
| Campaigns in the account hub as drawn (a "New campaign" button that opens the form; players, links and notifications as one scroll, not tabs in a card) | #1129 (screens 06 to 08) | H6 |
| The hub's Author variant of People compared with screen 11; the hub's pages at 834 and 2200 px wide, with a screen reader, in Safari and Firefox (the checks the design did not cover) | #1129 | H6 |
| The `/debug/me` link; the repository listing for reading that `/beings` kept in the hub and the Beings app's test for it | #1129 | H7 |
| A "Where it appears" page for an Inventory item, as a being and a Fact have (BN11); ADR 0524 lists it as "Inventory's pages (I6)", though slice I6 itself is built | 0524 | H6, from the existing backlinks read |
| All beings / Mine as the shell's two tabs, not a toolbar choice: the shell tells tabs apart by path only | 0524 | H6, with a small change to the shell |
| The design's "starts Greening 3" and "Not placed in order" on a Session row in Sessions | [0441](0441-sessions-moves-into-the-web-shell.md) | H6 (a read of each Session's start; if it is too many reads, H6 says so and the row stays) |
| "Groups that disagree" in Problems (Social), and an entry's page linked from other apps | 0527 | H6, once the maintainer says what "disagree" means; the links once a first app asks for one |
| The new matrix control "New cells are" as its own select | 0527 | H6 |

### Pulled into UI-H by the maintainer (API and art)

| Point | From | Done in |
| --- | --- | --- |
| "Seen by" on a being | 0524 | A1 (H3), then H4 |
| The Sessions a being takes part in without being named in their text | 0524 | A2 (H3), then H4 |
| Appearance (density, theme, motion) and saved views kept in the account | #1129, [0411](0411-web-widths-containers-density-and-type.md) | A3 (H3), then H4 |
| The strip's ticks in Social's Event chooser | 0527 | A4 (H3), then H4 |
| The "This month" shortcut: a calendar's current date as a field of the calendar | [0440](0440-calendars-moves-into-the-web-shell.md) | A4 (H3), then H4 |
| The mascots, all of them, from the maintainer's branch (`empty-sessions` and `empty-beings` among them) | [0441](0441-sessions-moves-into-the-web-shell.md), 0524 | H5 |

### Still outside UI-H

| Point | From | Why |
| --- | --- | --- |
| A stored preview of a Map on save | [0465](0465-maps-moves-into-the-web-shell.md) | Only if drawing in the browser proves too slow in a large library |
| Undo of a hand over (Beings, Inventory) | 0524 | A way to take an item back that the API offers; nothing asks yet |
| The "Restricted" chip of an Event | 0440 | Left out on purpose: a hidden Event is never shown |

H6 turns the first table into pull requests, each named for one app and one screen, so that a reviewer can look at one thing at a time.

## Consequences

- When it is built, every web page is drawn by one frame and one set of styles, the apps agree with their designs or say where they do not, and the code the apps share is in packages rather than in copies.
- H1 changes `packages/app-shell`, which every app builds on: its pull request is checked against every app's end-to-end suite, not just the ones the dependency graph names.
- H8 touches every app. It goes one extraction at a time so that a regression is one revert.
- Legal and Bench stay out of the shell and out of H1 and H2; H7 checks only what each should still share with it (the brand's styles, the appearance and theme, the legal links).
