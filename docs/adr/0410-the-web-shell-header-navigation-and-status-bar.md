# 0410 - The web shell: the header, moving between apps, and the status bar

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D12 to D19 and D29 to D31. Supersedes nothing; it keeps [ADR 0322](0322-calendars-and-sessions-share-a-header-and-the-brand-base.md) and RFC 0036 section 2 (no app switcher).

## Context

Each app has drawn its own header, its own way to reach the other apps and its own footer. People move between apps all session: from a being to its inventory, from a Session to its map.

## Decision

- **Two tiers on desktop and tablet** (D12): a global bar (brand, library switcher, palette, notifications, account) over an app bar (the app's name and its links as tabs). **With one library** (D29) the switcher is hidden and the header is one row; with several it is two tiers and the wordmark, the real horizontal lockup, sits between the mark and the switcher. **On a phone** the global bar is on top and the app's links are a bottom tab bar, separated by a border and clear of the safe area.
- **A state strip** (D13) under the header, shown only when something needs attention, with an icon, words and a pattern; it takes no space when nothing is wrong.
- **The library switcher** (D14) shows only when a person has more than one library.
- **No app switcher.** Four mechanisms, each with one job (D16): links from the data cross to the thing itself (built from `GET /app-links`); every app has its own Home, and all Homes share the blocks "Continue" and "What do you want to do?"; the footer lists every app by job; the palette goes to other apps and to entries across apps. An app that is not deployed, or that a role cannot use, is not listed.
- **Groups by job** (D17, D30, D31): Play (Sessions, Beings, Inventory), World (Calendars, Maps, Social), Build (Writing, Bench), You (Account).
- **A slim sticky status bar** (D18), always shown, with the sync state, the app's own meta (word count, carried weight, the in-world date where an app has one) and the real-world date and time, and one button, "Apps and about", that opens a drawer with the apps by job, the legal links, the version and the licence. On a phone it sits above the tab bar and the same content is the More sheet.
- **Legal links** (D19) are labelled in the interface language ("Legal notice", "Privacy policy"); the source-code link stays visible because of the licence.

## Consequences

- A new app needs a place in a group, a tab list, a Home, a go-to chord and an entry in the app-link registry, and nothing else of the shell.
- The in-world date appears in the status bar only where an app has a date of its own (the calendar apps), and nowhere else.
- The legal pages do not exist yet; the labels are working labels.
