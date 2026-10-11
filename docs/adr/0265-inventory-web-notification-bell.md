# 0265 - inventory-web: a notification bell

Status: accepted

## Context

A person using inventory-web learns of what happened to them (a character's game event, items a GM sorted, being added to a library) only by opening the account hub. The notifications half of the v1.0 row "Notifications, hover previews" asks for them where the person already is. The API is complete: `GET /me/notifications` with `unread_only` and `since` (([ADR 0058](0058-notifications.md), [ADR 0086](0086-managed-scope-aggregate-and-notifications-since-filter.md)), a read receipt per notification, and the unread count as the pagination envelope's `total` ([ADR 0087](0087-account-hub-pictures-unread-badge-and-access-overview.md)). The hub already shows them ([ADR 0071](0071-account-hub-stack-auth-deploy.md)).

Two facts shaped the design. A notification is written with its `title` and `body` by the server, as a finished sentence ("You were added to X"); there is no raw-type-to-sentence mapping in the hub to share, it prints `title` and `body`. And there is no "mark all read" route.

## Decision

- **A bell with a dropdown in the header**, beside who is signed in, for signed-in people only. The button has `aria-expanded` and `aria-controls`; its accessible name carries the count ("Notifications, 3 unread"; the badge itself is hidden from assistive technology, "99+" past two digits) and a polite live region says when new ones arrive.
- **The dropdown lists the ten newest, newest first.** Each shows its `title` (the sentence), its `body` and how long ago, unread ones marked, with "Mark read" per notification, "Mark all as read" when anything is unread, and "See all" to the account hub's `/notifications/`. The hub's origin is `PUBLIC_ACCOUNT_HUB_URL`, defaulting to the deployed hub.
- **A notification is a link when it names a page here.** A character's message leads to that character's board, "items sorted" to the library's board; the rest (invites, repository news) are text, since the hub is where they are acted on.
- **Mark all as read** reads every unread one, not only the ten listed: it pages the unread list and marks each with the existing route, reporting how many failed. A bulk route would be one request; it is left until the number of unread makes this slow.
- **Polling is light.** On load, when the tab comes back, when the dropdown opens, and every 60 s while the tab is visible; never while hidden, never signed out (the bell is only started once signed in), doubling after each failure up to 5 minutes. Count and list come from one pair of requests (a page of ten, and a one-item unread page for the total).
- **Errors are quiet.** A failed load keeps what was shown; with nothing shown, the dropdown says "Could not load notifications." A failed mark says so in the dropdown.
- **Keyboard:** Escape closes and returns focus to the button; Tab wraps between the button and the end of the dropdown; a click outside closes. On a narrow screen the dropdown spans the width under the header.
- **Wording** follows [the identity guide](../brand/identity.md) §14.3; the sentences are the server's.
- **Copied, not shared:** `relativeTime.ts` from the hub (a dependency-free 30-line file) and the small notification calls. With a third consumer they would become a package; the two apps have different clients and caches, so extracting now would be larger than the code.
- **Not here:** hover previews (another slice), a "since"-based incremental poll (the list is ten items, a plain read is as cheap), phone layout beyond not breaking the header.

## Consequences

- Notifications are visible and clearable from every page of inventory-web without a trip to the hub.
- Each visible tab makes two small requests a minute per signed-in person; hidden tabs make none.
- "Mark all" costs one request per unread notification until a bulk route exists.
- The hub and this bell show the same `title` and `body`; if the API ever stops composing sentences, both apps need the mapping and it becomes a package.
