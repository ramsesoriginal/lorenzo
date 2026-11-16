# 0417 - The account hub, redesigned

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/account-hub](../design/web/account-hub/README.md), AH1 to AH9. Narrows [ADR 0178](0178-account-hub-repositories.md) and [0179](0179-account-hub-one-campaigns-page.md) without superseding them.

## Context

The account hub grew page by page: libraries, campaigns, beings, setup, join, profile, and then repositories as two areas (RFC 0036, Shelf and Studio). The maintainer asked for it to be designed afresh from its jobs.

## Decision

- **The app begins at Home** (AH1), in a two-column layout: "Needs you" and "Where you play" on the left, "What you run" on the right, then Continue and the apps. A new account sees the first-run choice instead; a quiet account sees a "caught up" state.
- **One Repositories area** (AH2), where the person's role and relationship decide what they see (the ones their libraries draw on, the ones they publish). The tabs follow the role: an Owner or an Author sees Profile, People and Releases; a consumer sees Overview, "Use in a library" and "Libraries using it" (AH9). Shelf and Studio as two areas is turned down.
- **Beings is dropped from the hub** (AH3); Beings has its own app. Campaigns are a tab of their library, with players and links; "Where I play" is a block on Home; there is no cross-library campaigns page (AH8: campaign detail is inline in the library).
- **Discover has its own tab,** shown only when public repositories are on (AH5).
- **"Needs you" holds tasks only** (AH6): computed tasks (updates waiting, a link about to end, a new player, a draft). Notifications stay in the bell and its page.
- **Libraries is the entry for libraries and for creating one** (AH7).
- **A secret is shown once.** An invite link or a token is shown when it is made, with Copy, and never again; a list shows status, uses and expiry, never the secret. A GM link is single use and lasts at most a week; a player link has a lifetime from presets.
- **A copy cannot be undone as a whole,** and the wizard says so before it starts. An update never applies by itself; "apply all clean" never includes a breaking row, an edit made since the last release, or an attachment.
- **No old visual decision carries over** (AH4).

## Consequences

- The hub's profile and tokens pages are in ADR 0418.
- The hub's page set is a design; the API and the repository tooling are unchanged.
