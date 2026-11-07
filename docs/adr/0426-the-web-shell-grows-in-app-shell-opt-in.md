# 0426 - The web shell grows in app-shell, opt-in

Status: accepted, decided with the maintainer on 2026-11-06. Part of [RFC 0050](../rfcs/0050-the-web-interface.md), slice UI-B. Builds on [ADR 0322](0322-calendars-and-sessions-share-a-header-and-the-brand-base.md) and [ADR 0410](0410-the-web-shell-header-navigation-and-status-bar.md).

## Context

ADR 0410 decides what the web shell is: two header tiers, a state strip, a status bar, a phone tab bar and an apps drawer. `@lorenzo/app-shell` already draws the head, the header and the page frame for Calendars, Sessions, Maps, Writing and Social, with a one-row header. The shell has to reach those apps without changing five of them at once, and it needs code a test can reach.

## Decision

- **The shell is built in `@lorenzo/app-shell`**, not in a second package: one place draws the frame for every app.
- **It is opt-in.** `AppPage` takes `shell="web"`; without it an app keeps the one-row header. Each app moves over in its own slice (UI-D to UI-G), and UI-H removes the old header once none uses it. `bindShell` serves both: the calls only the web shell draws (`apps`, `statusBar`, `strip`, `notifications`) do nothing in the old header.
- **The notifications bell is drawn only when an app supplies it** (`shell.notifications({ count, href })`). Only Account Hub has a notifications source today, so there is no empty bell.
- **Nothing is claimed that the app has not said.** The status bar's sync state stays hidden until `statusBar({ sync })` is called.
- **The apps are listed from `GET /app-links`** ([ADR 0273](0273-app-links-registry.md)), by job from a table in the package (D17); an app with no address is not listed, and neither is an empty group.
- **The dialog closing fade lives in one helper** (`dialog.ts`): `data-closing`, wait for `animationend`, close; a reopen wins. A native close stays instant for every dialog that does not use it.
- **Tests:** the pure logic under Vitest, and the markup and `bindShell` together, by rendering the real `AppPage` with Astro's container API in a jsdom window. Real-browser checks come with each app's own end-to-end tests when it moves over. No new CI job.

## Consequences

- The package gains `astro`, `jsdom` and `@types/jsdom` as development dependencies, and a `vitest.config.ts` that uses Astro's Vite config.
- Until the last app has moved, the package carries two headers.
- The palette and the keyboard model (ADR 0414) are the second UI-B part; toasts, Undo, confirmations, menus and the account menu (ADR 0415, ADR 0416) are the third.
- **The palette:** the shell lists the apps, its own actions and an app's declared commands; entries across apps come from a function the app gives it, since the shell has no search of its own. Its keys are a pure keymap with the single-key shortcuts behind a switch kept in this browser.
- **Feedback and the account menu:** `toast`, `undoable` and `confirm` are on the shell; a toast leaves after ten seconds (paused while the pointer or focus is on it, restarted in full afterwards), an error stays, at most three show. In the web shell the header's account controls are one avatar button opening a menu; its hub pages (Profile, Notifications, Libraries and people, Access tokens and devices) are addressed from the hub's address as the hub is today, and UI-D changes them with the hub. The theme toggle stays in the header, hidden, so the existing binding keeps working; the menu and `G T` reach it. An app tells the shell what is only on the device with `unsent()`, and signing out then asks first.

## Addendum: the shell as drawn (2026-11-07)

A check of the built shell against the design found it two-tier and wordmark-first at every width, a modal sheet where D18 draws a docked drawer, and a strip beside the page. It now follows the design:

- **The header is one row until the library switcher is shown** (D29): the spark, the app's icon and name, its links, then search, the bell and the account; with several libraries (`shell.libraries`) it is two tiers and the wordmark, 28px high, sits beside the switcher. On a phone the app's name stays beside the mark and the links are the tab bar.
- **"Apps and about" is a drawer docked over the status bar** (D18) above the phone: not modal, the page undimmed, the bar visible, closed by Escape, a press outside or the same button. It lists the apps by job with their icons and a check on the one the person is in, then About, and a foot line: the product, its version, the licence and the date. On a phone it stays a modal bottom sheet, in one column.
- **The window's scrollbar gutter is not held open** on a page that has the shell, so the bars and the sheet run to the edge.
- **The status bar can say when it last synced** (`statusBar({ sync, syncedAt })`, "Synced 19:40") and writes the date as the design does, "Wed 4 November at 20:59".
- **The account menu** shows a name over the address, and the unread count beside Notifications.

Not in this step: the Appearance dialog of ADR 0416 (density and a system choice of theme); the theme is still a toggle.
