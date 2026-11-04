# Account hub: design

A fresh design of the account hub, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. This page holds the brief, the questions and the decision log for this app.

Status: the prototype is built and ready for review. Questions 1 to 5 and the first round of open questions are decided (AH1 to AH9).

## What the app is for

The account hub is where a person is, and where they look after the places they run. It has two sides that one person meets in one day:

- **Mine.** Who I am, what I belong to, what needs me, how I connect a device.
- **What I run.** The libraries, campaigns and repositories I look after: their people, their links, what they copy, what they publish.

It is the one app that spans libraries ([RFC 0013](../../../rfcs/0013-account-hub-app.md)): the same person is a GM in one campaign and a player in another. Sources: [the app's README](../../../../apps/account-hub/README.md), [v1.0.md](../../../../v1.0.md), RFC 0013, RFC 0036 sections 3 and 4, and ADRs 0170 to 0180, 0194, 0212, 0220, 0265, 0267 to 0269.

## The jobs

Ordered by who arrives and what they need in the first minute.

| Who | The job | Needs from the data |
| --- | --- | --- |
| A new account | Start: run a game, or join one with an invite link | `capabilities.create_tenant`; the link's preview |
| A player | See where I play and as whom; join, leave, pick a character | the campaigns where I hold a seat, my characters there |
| A GM | Run a campaign: its players and who each plays, its GMs, invite links, who can see what | `GET /me`, `GET /me/managed`, the campaign's players and GMs by name |
| A library Owner or Organizer | Look after the library: name, description, People and their roles, invite links, repositories it draws on, delete | members, roles, links with their status, counts |
| A library admin | **Shelf:** see what the library may copy, copy it (check first, name clashes, review, done), work through updates (new, changed, removed upstream, conflict; was, now, yours) | invitations, the copy plan, the update rows |
| A repository Owner or Author | **Studio:** create, describe, staff, publish; releases; the libraries using it; built on; view it as a subscriber; make it public | state, releases, People, libraries using it, blockers |
| Anyone | Notifications; profile; personal access tokens and approving a device; appearance; delete my account | the inbox, tokens with last use, device codes |
| Anyone, when public repositories are on | **Discover:** look at public repositories and their storefront | the public listing and a release's permitted preview |

Roles in play: Owner, Organizer, Author (of a library or a repository); GM and player (of a campaign). A repository has no campaigns and no roster. Every person sees only what the API lets them; the screen shows the reason where a control is not offered.

## What stays true, whatever it looks like

These are rules about behaviour and honesty, not about pictures. They hold in any direction.

- **A secret is shown once.** An invite link or a token is shown when it is made, with Copy, and never again; the list shows status, uses and expiry, never the secret.
- **A dead link says one thing.** Unknown, expired, revoked and used up all read "This link doesn't work any more." (D27).
- **A GM link is single use and lasts at most a week;** a player link has a lifetime chosen from presets.
- **A copy cannot be undone as a whole,** and the wizard says so before it starts. An update never applies by itself; "apply all clean" never includes a breaking row, an edit made since the last release, or an attachment.
- **Players see nothing of the update inbox,** and the inbox says that applying changes what players see.
- **Nothing hidden is counted** (D24), and an unknown id is shown as a word ("a removed entry"), never as an identifier.
- **The API decides every permission.** The screen explains a refusal in plain words; it does not guess.
- **Deleting a library or a repository** names what is lost, with counts the person may know, and asks for the name (D26).
- **Words** follow identity §14.3 and ADR 0194: library, repository, campaign, People, Owner, Organizer, Author, GM, player, invite link, entry, built on, copy, update, name clash, check first.

## Visual or structural decisions in the old documents

Named here so each can be kept or dropped on purpose. None carries over by default.

| From | What it decided | The question |
| --- | --- | --- |
| ADR 0170 | Confirmations are the browser's own `window.confirm` | Replaced by the dialogs of D26 (decided). Listed so it is not forgotten. |
| ADR 0178, 0179, 0180 | The app is a set of pages: libraries, campaigns, beings, setup, join, profile | Does the page set stay, or does the app have another shape? |
| RFC 0036 sections 3 and 4 | Shelf and Studio are areas with the nav labels "Repositories" and "My repositories", and Studio has the tabs Overview, Profile, People, Built on, Releases, Libraries using it | Do the two areas and the tab list carry over? |
| ADR 0178 | The hub also lists beings, with a "Repository" badge | Beings now has its own app; does the hub still list them? |
| ADR 0179 | One page, "Your campaigns", across libraries: where you play, where you run | Does a cross-library campaigns view stay? |
| ADR 0292, 0293 | Discover lists public repositories with filters and a storefront | Where does Discover live? |

## Questions

1. **Where does the app begin?** Three directions I would draw, so you can choose by looking:
   - **A. Home first.** A person-centered Home (what needs me, where I play, what I run), with Libraries, Repositories and Account as places you step into.
   - **B. A console.** Choose a library or a repository, and everything about it is in one workspace (Overview, People, Campaigns, Repositories, Danger); Home is a short list.
   - **C. Two workspaces.** "Play" (my campaigns, characters, notifications) and "Run" (libraries and repositories), side by side, each its own area.
2. **Repositories.** Keep Shelf ("Repositories", what a library draws on) and Studio ("My repositories", what a person publishes) as two areas with the same tab structure, or one "Repositories" area where your role decides what you see?
3. **Pages to drop or merge.** Drop the hub's beings listing (Beings has it)? Merge campaigns into their library plus a short "where I play" on Home?
4. **Old decisions.** From the table above: which carry over? "All except …" is a good answer.
5. **Discover.** Inside the hub, its own place in the shell, or hidden unless public repositories are on?

## Decision log

Decided with the maintainer, 2026-11-04, from the brief above. Each answer is the maintainer's; none carries an old visual decision over.

### AH1. The app begins at Home, in layout B

Direction A (a person-centred Home), in the two-column layout B: "Needs you" and "Where you play" on the left, "What you run" on the right, then Continue and the apps. Layouts A (everything stacked) and C (Needs you with filters) are turned down, and the prototype has one layout.

### AH2. One Repositories area

One area, "Repositories", where the person's role and relationship decide what they see: the ones their libraries draw on, and the ones they publish. The tabs follow the role (Owner and Author see Profile, People and Releases; a consumer sees Overview, Use in a library and Libraries using it). Turned down: Shelf and Studio as two areas.

### AH3. Beings dropped; campaigns live in their library

The hub no longer lists beings (Beings has its own app). Campaigns are a tab of their library, with its players and links. Where I play is a block on Home. There is no cross-library campaigns page.

### AH4. No old visual decision carries over

The table of old decisions above is answered "none". The rules under "What stays true" still hold; they are behaviour, not pictures.

### AH5. Discover has its own place

Discover is a tab of its own in the app, shown only when public repositories are on. It is not hidden inside Repositories.

### AH6. "Needs you" holds tasks only

Computed tasks (updates waiting, a link about to end, a new player, a draft). Notifications stay in the bell and the notifications page and do not appear there.

### AH7. Libraries is the entry for libraries and for creating one

### AH8. Campaign detail is inline in the library, as drawn

### AH9. The tab name "Use in a library" and the role-driven tab set stay

## The prototype

In `account-hub/prototype/`. It links `apps/brand` in place and unchanged, loads the shell prototype (`../../prototype/`) and extends it through its hook points (`ROUTES_EXT`, `PROTO_EXT`, `PROTO_CLICK`, `PROTO_SYNC`, `START_ROUTE`, `TAB_HIDE`, `LOCKUP`, `ICONS_PATH`). Plain HTML, CSS and JS.

### Run it

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/account-hub/prototype/index.html
```

A private single-page copy is built with `node build-review-copy.mjs` (`--fragment` for the Artifact host).

### Pages

Tabs: Home, Libraries, Repositories, Discover (only when public repositories are on). Notifications, Profile, and Tokens with device approval sit behind the account button.

- **Home.** Needs you and Where you play beside What you run, then Continue and What do you want to do. A new account sees the first-run choice instead; a quiet account sees a "caught up" state.
- **Libraries, and a library.** Overview, Campaigns (players, GMs, links shown once, revoke), People (by role), Settings (a save bar and type-the-name delete).
- **Repositories, and a repository.** The update inbox with was, now and yours, "apply all clean" with a confirm, a four-step copy wizard with name clashes, releases with a guarded publish, a visibility switch with a blocker, libraries using it, and create.
- **Discover and a storefront.**
- **Account.** Notifications, profile with colours and delete account, tokens shown once, approving a device with a code.

The controls bar switches account state (busy, quiet, new), role (Owner, Organizer, Author, none) and "may create".

### What it fakes

All data is made up and held in memory (`hub-data.js`). Nothing calls the API; permissions are the role switch. Copy, publish, revoke and delete change only the page state.

### What was checked

- 37 scripted interactions in Playwright, all passing.
- axe-core: no violations on 18 routes at 430 and 1440 wide, in light and dark.
- Touch targets of at least 44px at 430 wide on five routes.
- No console errors.

### What was not checked

A screen reader, a real touch device, colour-blindness simulation, Safari and Firefox, and every route at 834 and 2200 wide.

### Findings

- Ctrl L and Ctrl Shift T are reserved by browsers, so the prototype uses the chords G then L and G then T.
- The rules under "What stays true" are all shown by a screen: secret once, one-word dead link, uncounted hidden things, the reason beside a control that is not offered.

### Screens

In `account-hub/screens/`, 36 images: Home, quiet and first run (01 to 03); libraries and a library by tab and by role (04 to 13); repositories, the copy wizard, the update inbox, releases and publish (14 to 22); Discover and storefront (23, 24); notifications, profile and device (25 to 27); dark (28, 29); 834 wide (30, 31); 430 wide (32 to 36).

## Open questions

None for the account hub. The checks are re-run once on the final layout before the write-up.
