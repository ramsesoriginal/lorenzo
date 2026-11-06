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
- The palette, the keyboard model and the account menu (ADR 0414) and the toasts, Undo and dialog helpers (ADR 0415) follow in the next UI-B parts.
