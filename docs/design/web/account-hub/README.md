# Account hub: design

A fresh design of the account hub, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. This page holds the brief, the questions and the decision log for this app.

Status: the brief and its questions. No direction is chosen yet.

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

Nothing is decided here yet.
