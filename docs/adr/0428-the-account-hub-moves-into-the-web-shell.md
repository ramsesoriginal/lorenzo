# 0428 - The account hub moves into the web shell

Status: accepted, decided with the maintainer on 2026-11-06. Part of [RFC 0050](../rfcs/0050-the-web-interface.md); it implements UI-D ([#1015](https://github.com/ramsesoriginal/lorenzo/issues/1015)) with [ADR 0416](0416-first-run-the-account-menu-and-joining.md), [0417](0417-account-hub-redesign.md) and [0418](0418-profile-access-tokens-and-connecting-a-device.md), on the shell of [ADR 0426](0426-the-web-shell-grows-in-app-shell-opt-in.md).

## Context

The account hub is the one app that does not use `@lorenzo/app-shell`: it has its own head, header, footer and navigation, with links that appear only when the person may have them. The account menu of ADR 0416 points at the hub's pages (Profile, Notifications, Libraries and people, Access tokens and devices), so the hub is the first app to move over.

## Decision

- **The hub's frame is the web shell** (`AppPage shell="web"`). Its own header, footer and head are removed; its pages keep their content and move to the new designs one slice at a time.
- **Gated links are the shell's.** A `NavItem` may say `requires: "signed-in"` (or `library-admin`, `repository-work`, `discover`, `create-tenant`, `beings`); the link stays hidden until the app calls `shell.allow(requires)`. The hub keeps the rules that decide which pages a person has (`GET /me`, `GET /tenants`, the discover facets) in `lib/shell.ts`, unchanged. An answer that does not come leaves its links hidden.
- **`welcome` is optional on `AppPage`.** The hub's pages say their own loading, so the frame shows the page at once; the other apps keep their welcome.
- **The bell is the hub's unread count** (`shell.notifications`), asked again every 30 seconds, when the tab returns and when a notification is marked read, as before.
- **The slices** after the frame: Profile (ADR 0418, PT2, PT3, PT6), Access tokens and Connect a device (PT4, PT5), Home with first run and "caught up" (AH1), then Libraries, campaigns and notifications, and Repositories as one area (AH2 to AH9) once each is agreed.

## Consequences

- The hub depends on `@lorenzo/app-shell`; the web shell's account menu links to the hub's current paths until the pages move.
- The frame changes what every hub page looks like around its content. The end-to-end checks that name the header (`banner`, the navigation's name "Pages") follow it.
