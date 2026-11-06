# Lorenzo web interfaces: design

The design guidelines for Lorenzo's web interfaces and a fresh design of each web app, worked out with the maintainer on clickable prototypes. This page holds the brief and the decision log. Nothing is decided until it is in the log.

Status: decided. The shell, the page templates and the design of every web app (Account hub, profile and tokens, Writing, Calendars and Sessions, Maps, Beings, Inventory, Social) are agreed with the maintainer. The write-up is [RFC 0050](../../rfcs/0050-the-web-interface.md) with [ADR 0409 to 0424](../../adr/README.md), the guideline text is in [identity](../../brand/identity.md), and the follow-ups for `apps/brand` are in [follow-ups.md](follow-ups.md).

## Layout of this directory

- `web/` (this directory): the system. Brief, decision log, [`prototype/`](prototype/index.html) (the shell and the templates), [`screens/`](screens/) (rendered from it) and [`mascot-images.md`](mascot-images.md) (the images the illustrators are asked for).
- `web/<app>/`: one directory per app design, in the order of the log below.
- [`../bench`](../bench/README.md) and [`../beings`](../beings/README.md) are earlier designs and are not changed by this work.

## Scope of the work

| App | Treatment |
| --- | --- |
| account-hub | New design |
| writing | New design |
| calendars and sessions | New design, together |
| maps | New design |
| beings | New design |
| inventory-web | Minimal redesign only |
| bench | No redesign. It stays its own thing; the system takes nothing from it unless the maintainer says so |

## The brief

Ultra-modern, responsive, pragmatic, with very good UX. Minimal chroma. Simple for a beginner in the first minute, powerful for a power user in the tenth hour.

### Principles

Each has a test that a screen can fail.

1. **The first minute needs no manual.** Every screen says what it is for and offers one clear next step. *Test: a visitor with no context can say what the screen is for and what to do first.*
2. **Honest state, in words and an icon.** Saved, waiting, out of date, and who can see it. *Test: for any value you can say where it is saved and who sees it without a tooltip, and every state has an icon as well as words.*
3. **Neutral first. Colour is state, never the only signal.** One action colour. Several colours may mark state, and each state also carries an icon, a word and a pattern or shape that survives greyscale and colour blindness (hatching and similar patterns). Gold only where identity §1.4 allows. *Test: in greyscale and in a colour-blindness simulation every state is still told apart.*
4. **A keyboard path for everything; hover is decoration only.** Hover may animate but never carries a function or information. *Test: finish the main task without a mouse; remove every hover style and nothing is lost.*
5. **A phone is a first-class width.** Designed and checked at 430 wide. *Test: the main task works at 430 with a thumb, with targets of at least 44px and no sideways scroll.*
6. **Power is added, never required.** The palette, bulk actions, density options and saved layouts sit on top of a complete simple app. *Test: remove them all and a complete simple app remains; adding them removes nothing a beginner uses.*
7. **The same job looks the same in every app.** One shell, and one grammar for direct, derived and restricted (identity §18). *Test: two apps side by side use the same control for the same job.*
8. **The words are the product's, and setting-free.** *Test: swap fantasy for sci-fi or an office and the copy and examples still hold.*
9. **Every screen draws its bad days.** Empty, loading, error, conflict, partial permission, offline. *Test: each screen has all six drawn.*
10. **Modern CSS, and motion that orients.** Use the newest CSS where it helps: everything in the motion and scroll preview of `apps/brand` (typewriter reveal, staggered entrance, scroll indicators, count-up, squircle corners, loaders, spinners, glows, scroll fades) and scroll-driven effects such as parallax where they make sense. Everything that opens, closes, moves or switches has a transition, short enough to feel snappy and slow enough to feel smooth. Each technique sits behind `@supports` with a static fallback, and reduced motion removes movement (identity §15.4). *Test: every opening, closing, moving or switching thing has a transition duration; with the new CSS unsupported and with reduced motion on, everything still works and reads the same.*

### What is fixed from the brand and what is open

Fixed: token roles and names, the three typefaces, Archive Blue for action, gold as punctuation, neutral visibility, the icon atlas, the voice and terminology of identity §14, and accessibility (§15).

Open to change, one decision at a time: the chrome (decided, D5); the edge of a control (decided, D6); the blue tint of selection; whether the warmth of Paper and Parchment counts as chroma; breakpoints and widths; a type scale; density; the steps of the dark surfaces; the shape of the header and footer; motion durations.

## The shell prototype

A clickable composition of the shell and the templates, in [`prototype/`](prototype/index.html): plain HTML, CSS and JavaScript, no framework. **It is a reference for layout and behaviour, not code to ship.** It runs on made-up data in several settings and changes only what is in memory.

### How to run it

Serve the repository root (the page links `apps/brand` in place, and the brand fonts and icon sprite are fetched):

```bash
python3 -m http.server 8731    # from the repository root
# open http://localhost:8731/docs/design/web/prototype/index.html
```

The bar at the top ("Prototype controls") switches the width of the design (430, 834, 1440, 2200 or the window), the theme, the number of libraries, who is looking (a GM or a player), online or offline, how loading behaves (slow, fails once, keeps failing), and jumps to first run, the join link and the states. It is not part of the design. The width is simulated with container queries, so every layout rule follows the frame, not the window.

To open it without serving anything, [`prototype/build-review-copy.mjs`](prototype/build-review-copy.mjs) builds one page with the brand CSS, the icon sprite and the scripts inlined, and the brand fonts beside it: `node docs/design/web/prototype/build-review-copy.mjs OUT_DIR` (add `--fragment` for a host that supplies its own html, head and body).

### What it contains

The header, one row for one library and two tiers with the wordmark for several, and the bottom tab bar (D12, D29), the state strip (D13), the library switcher shown only for more than one library (D14), the slim status bar and the "Apps and about" drawer (D18), Home with the shared blocks (D16), the palette with its preview and the shortcut model (D25), toasts with the 10-second timer (D26), dialogs and menus that become sheets (D26), density and Appearance (D22), and the first run, the account menu, signing out with unsent changes and joining with an invite link (D27). Templates: list and detail (with the tablet side sheet and the third pane on a large screen), reading, settings and forms with the save bar, the editor with autosave, the board, a full-width map workspace, Home, and the states gallery. Other apps open a plain "not drawn in the prototype" page.

Keyboard: `Ctrl K` (`Cmd K`) opens the palette, `Ctrl Shift K` in an editor; `?` lists the shortcuts; G then H, S, B, I, C, M, W, O, R, A goes to an app; J, K, Enter, X, N, E and `/` work in the beings list; `Ctrl Z` undoes the last action.

### Brand pieces and new pieces

Linked from `apps/brand` in place and unchanged: `normalize.css`, `tokens.css`, `fonts.css`, `base.css`, `motion.css` (spinner, skeleton, progress bar, the spark loader, stagger, count-up, typewriter), the icon sprite. **Not used: `components.css` and `layout.css`.** The shell's controls follow decisions the brand components do not yet (a control edge at 3:1, container-driven sizes), so the prototype has its own in `prototype/shell.css`. That file defines no colour, radius or font of its own.

New, and not in the brand: [`prototype/proposed-tokens.css`](prototype/proposed-tokens.css) (D6 `--border-control`, D23 type roles and the 12px step, D26 transition durations). `apps/brand` is not changed by this work.

### What it fakes

The API, sign-in and sign-out, real offline storage and synchronisation, real conflicts, search (a match on names), pictures (labelled boxes), the mascots (labelled slots with the image id from [mascot-images.md](mascot-images.md)), the legal pages, the in-world date, saving a person's preferences in the account (the prototype keeps them on the device), and everything in apps it does not draw.

### What was checked, and what was not

Checked in a real browser (Chromium, Playwright), on 2026-11-04:

- **axe-core** on the twelve routes at 430 and 1440, in light and dark: no violations after fixes.
- **Pressed controls** are at least 44px at 430 on eleven routes.
- **Thirty-one scripted behaviours** pass: the palette (open, search, narrow, close), the G chords, selection and the bulk bar, row menus, delete with Undo, the toast timer pausing and resetting under the pointer, filters, the offline strip, the sign-out, shortcuts and drawer dialogs, the save bar, the type-the-name delete, editor autosave, linking an entry with `Ctrl K`, moving a board item, the setup flow, the More sheet and the detail sheet on a phone, the palette as a full screen on a phone, the detail as a side sheet and the dialog as a sheet at 834, and the third pane at 2200.

Not checked: a screen reader, a real touch device, a colour-blindness simulation, Safari or Firefox (scroll-driven animations, view transitions and `corner-shape` are enhancements and degrade to static), a visual review of every route at 834 and 2200, and reduced motion beyond the setting being wired.

### Findings for the brand and the design

- **`--text-tertiary` on `--surface-selected` is 4.4:1** in the light theme, below 4.5 for small text. The prototype uses the secondary colour on selected rows. A brand change to consider.
- **The spacing tokens change at 720px by the window, not the container.** The prototype redefines the same values by container so the simulated width works; the real change is container queries in the brand CSS.
- **`Ctrl L` and `Ctrl Shift T` are reserved by browsers** and cannot be used for "switch library" and "change theme". They are `G` then `L` and `G` then `T` in the prototype, and the shortcuts list shows them so.
- **Atlas:** no icon for an empty state (the prototype uses the dashed entity mark as a stand-in), and none for an app as a destination (the prototype uses the kind icons). Not added; listed for the maintainer.
- **Components the shell needs that the brand lacks** (candidates for promotion, listed in Phase 4): a button and field with the control edge, a segmented control, a switch, a menu, a sheet and dialog that follow the container, a toast with a timer, the palette, the state strip, the status bar, the tab bar, the state chip with its patterns, the save bar, skeleton rows.

### Screens

Rendered from the prototype with Playwright; if a screen and the prototype disagree, the prototype wins. Phone and tablet screens are at 2x, the others at 1x.

| | Wide screens | Phone and tablet |
| --- | --- | --- |
| Home | [light](screens/01-home-1440.png), [dark](screens/02-home-1440-dark.png) | |
| List and detail | [1440](screens/03-beings-1440.png), [selected and bulk bar](screens/04-beings-bulk-1440.png), [2200, third pane](screens/06-beings-2200.png) | [834, detail as a sheet](screens/05-beings-834-detail-sheet.png), [430](screens/07-beings-430.png) |
| Palette | [1440, with preview](screens/08-palette-1440.png) | [430, full screen](screens/09-palette-430.png) |
| Menus, toasts | [row menu](screens/10-row-menu-1440.png), [toasts](screens/11-toasts-1440.png) | [More sheet](screens/31-more-sheet-430.png), [account menu](screens/35-account-menu-430.png) |
| Board | [1440](screens/12-board-1440.png) | [430](screens/13-board-430.png) |
| Reading | [1440](screens/14-read-1440.png) | [430](screens/15-read-430.png) |
| Editor | [1440](screens/16-write-1440.png) | [430](screens/17-write-430.png) |
| Settings and forms | [unsaved changes](screens/18-settings-unsaved-1440.png), [delete a library](screens/19-delete-library-1440.png) | |
| Map | [1440](screens/20-map-1440.png) | [430](screens/21-map-430.png) |
| First run, joining | [first run](screens/22-first-run-1440.png), [setting up](screens/24-setup-progress-1440.png) | [first run](screens/23-first-run-430.png), [join](screens/25-join-430.png) |
| States | [light](screens/26-states-1440.png), [dark](screens/27-states-1440-dark.png) | |
| State strip, footer | [offline](screens/28-offline-strip-1440.png), [conflict](screens/29-conflict-strip-1440.png), [apps and about](screens/30-apps-and-about-1440.png) | |
| Dialogs | [shortcuts](screens/32-shortcuts-1440.png), [appearance](screens/33-appearance-1440.png), [sign out](screens/34-sign-out-1440.png) | |

## Decision log

Each entry: what was decided, the options turned down, and the date.

### D1. Where the deliverables live (decided with the maintainer, 2026-11-04)

A `docs/design/web/` directory for the system and `docs/design/web/<app>/` per app. Turned down: `docs/design/<app>-v2/` per app.

### D2. Output form (decided with the maintainer, 2026-11-04)

Both: a design canvas for exploring alternatives and plain HTML and CSS linking `apps/brand` in place for the clickable shell and the chosen app prototypes. Turned down: canvas only; HTML only.

### D3. Order of the apps (decided with the maintainer, 2026-11-04)

account-hub, writing, calendars with sessions, maps, beings. inventory-web gets a minimal redesign only; bench none. Turned down: the order of `apps/README.md`.

### D4. Branch (decided with the maintainer, 2026-11-04)

Work on `docs/web-design`, off current main, merge commits only. Turned down: the session's default branch.

### D5. Chrome of the system (decided with the maintainer, 2026-11-04)

A hybrid. Page structure and the shell are quiet: no boxes, a hairline and space between sections. A bordered card is used only for a thing that is an object (a person, a note, an entry). Controls keep a visible edge (D6). Turned down: bordered cards for every section; quiet chrome throughout, with soft-fill controls and no edge.

### D6. The edge of a control (decided with the maintainer, 2026-11-04)

A new token, `--border-control`, for the edge of fields and secondary buttons, at a contrast of at least 3:1 against the surfaces they sit on (WCAG 2.1, 1.4.11). Today `--border-strong` is about 1.7:1 on Paper and `--border-subtle` about 1.4:1, calculated from the token values. Proposed values: Ink 50% on Paper in light (about 3.5:1), Paper 42% on Ink in dark (about 3.6:1). The change to `apps/brand` is a follow-up, not made here. Turned down: keeping today's borders and relying on labels; the token for fields only.

### D7. Principles (decided with the maintainer, 2026-11-04)

The ten above. Changes from the first proposal: principle 2 gained an icon beside the words; principle 3 allows several colours for state provided a pattern or shape also carries it; principle 4 makes hover decoration only; principle 5 uses 430 as the phone width; principle 10 was added.

### D8. Phone design width (decided with the maintainer, 2026-11-04)

430 wide is the width phone screens are designed and checked at. Which width the layout changes at is a Phase 2 decision.

### D9. How much effect an app page carries (decided with the maintainer, 2026-11-04)

Effects serve orientation: reveals, scroll indicators, count-up, transitions on everything that opens, closes, moves or switches. Parallax and the canonical glow appear on home and empty-state pages; the maintainer allows a little more where it helps, case by case in the design. Turned down: effects anywhere by default.

### D10. Visibility in a table (decided with the maintainer, 2026-11-04)

Everyone is plain text in a table cell, with no badge (identity §6.6). Every other audience is the neutral badge with an icon and a label.

### D11. Selection tint (decided with the maintainer, 2026-11-04)

`--surface-selected` stays as it is (12% Archive Blue). Revisit only if the shell shows it as too much chroma.

### D12. The header (decided with the maintainer, 2026-11-04)

Two tiers on desktop and tablet: a global bar (brand, library switcher, palette, notifications, account) over an app bar (product name and the app's links as tabs). On a phone, the global bar on top and the app's links as a bottom tab bar (a border, not a shadow, with room for the safe area). Turned down: one bar with a menu button on a phone; a command-first bar with the links behind a menu on desktop.

### D13. The state strip (decided with the maintainer, 2026-11-04)

A strip under the header, shown only when something needs attention (alerts, notes, decisions, warnings, offline, waiting changes), with an icon, words and a pattern. It takes no space when nothing is wrong. The footer carries a quieter status bar (see the footer input below); the two do not repeat each other.

### D14. The library switcher (decided with the maintainer, 2026-11-04)

Shown only when a person has more than one library. Hide the complexity when it is not needed. Turned down: always visible.

### D15. Toolbar icon buttons (decided with the maintainer, 2026-11-04)

No edge on icon buttons in a toolbar (bell, search icon, account). Controls that look like fields or secondary buttons keep the D6 edge.

### D16. Navigation between apps (decided with the maintainer, 2026-11-04)

No app switcher (RFC 0036 section 2 and ADR 0322 stand). Four mechanisms, each with one job:

1. **Links from the data** cross to the thing itself ("Open Mara Quill in Beings"), built from the `GET /app-links` templates.
2. **Home**: every app has its own home. All homes share one block, "Continue" (what you were doing, across apps) and "What do you want to do?" (the apps by job); the rest of each home is specific to that app. The brand mark goes to the current app's home.
3. **The footer** lists every app by job (desktop); on a phone the same list is the More sheet of the tab bar.
4. **The palette** goes to other apps and to entries across apps, not only within the current app.

An app that is not deployed, or that a person's role cannot use, is not listed. Turned down: a brand menu in the global tier (an app switcher); a single Home in account-hub; the footer list alone.

### D17. Grouping of the apps (decided with the maintainer, 2026-11-04)

By job: Play (Sessions, Beings, Inventory), World (Calendars, Maps, Social), Build (Writing, Bench), You (Account). The names of the groups are working names. Writing moved from World to Build in D31.

### D18. The footer (decided with the maintainer, 2026-11-04)

A slim, sticky status bar, always shown, on every app. It holds the sync state (icon and words), the app's own meta (word count in Writing, carried weight in the inventory, the in-world date where an app has one), and the real-world date and time. One button, "Apps and about", opens a drawer with the apps by job (D16, D17), the legal links, the version, the licence and the date. On a phone the status bar sits above the tab bar and the same content is in the More sheet. Turned down: two bands with a page footer; one sticky bar holding everything.

Idea, not decided: the clock may open to show a calendar, a pomodoro timer or a session timer.

### D19. Legal links (decided with the maintainer, 2026-11-04)

Labelled in the interface language, so in English for now. Working labels: "Legal notice" (the Impressum) and "Privacy policy" (the Datenschutzerklärung). The pages do not exist yet (v1.0 lists the privacy notice as New). The source-code link stays visible because the licence is AGPL-3.0. Turned down: always the German names.

### D20. Widths and breakpoints (decided with the maintainer, 2026-11-04)

Steps, not two modes. Working widths: a phone up to 720px; a tablet from 721px; a desktop from 1100px; a large screen from 1700px. The numbers are settled once the page templates are drawn, because the content decides where a layout breaks. The shell switches at 720px (bottom tab bar against top tabs). Everything below the shell adapts to the space it is given, built with container queries, so a component works in any pane. Phone design width is 430 (D8). At a tablet a list shows the list alone and the detail opens as a side sheet; on a large screen a third pane may appear.

Content is capped in width (the probe caps at 1760). Certain content may use the full width: which kinds is decided with the page templates. Turned down: two modes with one 1120px container; viewport media queries only.

### D21. Page templates (decided with the maintainer, 2026-11-04)

Seven templates: list and detail, reading, settings and forms, document editor, board, full-width workspace, home. Rules:

- **Reading** has a 680px measure; the **editor** a 720px writing column.
- **Settings and forms** are capped at 1040px: label and help on the left, fields on the right, one column on a phone.
- **Saving** is chosen per template. Forms with irreversible effects use an explicit bar at the bottom ("1 change not saved", Discard, Save changes; a border, not a shadow). Writing and entry fields autosave and say "Saved". Every screen says which one it is, by state.
- **Home** has the app's own blocks first, then the shared "Continue" and "What do you want to do?" blocks (D16).
- **Full width** (exempt from the cap, for now): the board, the full-width workspace (a map, a wide table) and the editor's outline pane. Everything else is capped.

Turned down: autosave everywhere; an explicit save everywhere; the shared blocks first on Home.

### D22. Density and saved views (decided with the maintainer, 2026-11-04)

Three levels: Comfortable (the default, 48px rows), Compact (36px) and Dense (28px, fine pointer only). The type size never changes (identity §15.5); only row height and padding do. On a phone or a coarse pointer every level is at least 44px, so the control is not offered there.

- **Appearance** holds a density setting (with theme and motion), the starting point for every list.
- **Saved views** are a named layout per list (columns, sort, filters, density) and are per person. They are not shared with other people in the library.
- **Where it is remembered:** in the account, so it follows the person to another device. This needs an API surface for a person's preferences, which does not exist yet; it is a follow-up slice, not made here.

Turned down: a density control in every list toolbar; Appearance alone; saved views alone; shareable views; remembering on the device only.

### D23. Type scale and spacing in use (decided with the maintainer, 2026-11-04)

**Type** is a set of semantic roles, not a ladder of sizes. Editorial roles are fluid between a phone (430) and a desktop (1440), with a clamp that has a rem part so browser zoom still works; interface roles are fixed at every width.

| Role | Phone | Desktop | Face, weight, line |
| --- | --- | --- | --- |
| Display | 34 | 56 | Newsreader 400, 1.1 |
| Title (page, entry) | 28 | 40 | Newsreader 400, 1.15 |
| Reading | 18 | 20 | Newsreader 400, 1.6 |
| Heading | 18 | 18 | Geist 600, 1.3 |
| Subheading | 16 | 16 | Geist 600, 1.35 |
| Body | 15 | 15 | Geist 400, 1.5 |
| UI | 14 | 14 | Geist 400 or 500, 1.4 |
| Meta | 13 | 13 | Geist 400, 1.4 |
| Micro | 12 | 12 | Geist 500, 1.3 |
| Code | 13 | 13 | Geist Mono 400, 1.5 |

Nothing is below 12px. Weights are 400, 500 and 600. Sizes are in rem. Numbers in tables, counts and the status bar use tabular figures. Sentence case; the serif is for titles, names and reading text.

**Spacing** is the brand's 4px grid plus one new step, `--space-2h` (12px on desktop), for gaps in dense groups and the label of a field. On a phone the spacing tokens stay halved at 720px and below, as the brand does today (so `--space-2h` is 6px there).

Turned down: a ladder of ten sizes; fixed roles with a jump at the phone step; the same spacing rhythm on a phone as on desktop (the repository's rule is kept).

### D24. States, and the mascots (decided with the maintainer, 2026-11-04)

- **Retry:** a failed read retries by itself with a short backoff and says so ("Trying again in a moment"); after it gives up a "Try again" button stays. A write is never retried automatically.
- **Loading:** a spinner only for a one-line wait (a single field); a skeleton for everything else; a progress bar wherever the progress is known. The branded spark is for the rare branded waits only (identity §17.9).
- **Mascots** appear in states where a whole page has nothing to show or cannot be shown (first run, a page with nothing in it, not found, no access, offline, a page-level error), never in a working page's region states and never in app chrome. The images are listed in [mascot-images.md](mascot-images.md) for the illustrators.
- **Copy** follows the brand guide (identity §14): clear, concise, precise, quietly playful, no over-cute speech, no apology boilerplate.
- **A hidden thing is never counted.** "No access" does not say whether the page exists; no state says how many entries a person cannot see.

Turned down: retrying a write automatically; a spinner for every wait; no mascots in functional states beyond the rare page-level ones; warmer apologetic copy.

### D25. The palette and the keyboard model (decided with the maintainer, 2026-11-04)

- **One palette** for entries across apps, apps ("Go to") and actions. Tab narrows it (Everything, Entries, Apps, Actions). `Ctrl K` opens it (`Cmd K` on a Mac). On large and desktop screens it is centered with a preview of the selected entry (from the existing entry preview); at the tablet step it is centered without the preview; on a phone it is a full screen.
- **Shortcuts:** `?` lists them. Go to: G then H (home), S (Sessions), B (Beings), I (Inventory), C (Calendars), M (Maps), W (Writing), O (Social), R (Bench, the repository), A (Account). In a list: `J` and `K` move, `Enter` opens, `X` selects, `Shift J` selects a range, `N` new, `E` edit, `/` filters.
- **A switch for single-key shortcuts** (WCAG 2.1.4); shortcuts with Ctrl always work. The keys may become remappable in a later slice.
- **In a rich-text editor** `Ctrl K` inserts a link to an entry, and the palette opens with `Ctrl Shift K`.

Turned down: the palette centered without a preview everywhere; anchored to the header field.

### D26. Toasts, dialogs and menus (decided with the maintainer, 2026-11-04)

- **Toasts** sit at the bottom center, directly above the status bar (above the tab bar on a phone), in a live region. Three kinds: a quiet confirmation ("Saved"), a reversible action with **Undo**, and an error that stays until dismissed and offers "Try again". A toast that leaves by itself stays for **10 seconds**, shows a progress bar counting down, and the timer pauses and resets while the pointer is over it or focus is in it. Turned down: bottom left; top right.
- **Undo or confirm.** A reversible action (delete an entry, move, change who sees it) is done at once and offers Undo. An irreversible or large action asks first in a dialog that names what is lost, with counts the person may know; the largest asks the person to type the name, and its button says what it does and stays disabled with a reason. Never a generic "Are you sure?". Bulk actions that are reversible also use Undo.
- **Dialogs** are centered on desktop; the first field takes focus, `Enter` submits, `Esc` cancels. At the tablet step and on a phone a dialog is a bottom sheet with stacked buttons, the safe choice first.
- **Menus** are popovers with shortcut hints at the right and a divider before a destructive item. A row's actions are a visible button, never hover-only. On a phone a menu is a bottom sheet with 44 to 48px rows.

Turned down: a centered dialog at the tablet step.

### D27. First run, the account and joining (decided with the maintainer, 2026-11-04)

- **First run** for an account with no library: two doors on one screen, "I run a game" (set up a library) and "I'm joining a game" (an invite link field), with the mascot image `first-run-welcome`. Turned down: a single start with a quiet invite field; a sample library to try first.
- **The word is "library"**: "Set up a library", not "Set up a table".
- **"Just looking around"** (browse public repositories) is hidden entirely when public repositories are off in the deployment.
- **An account with no library but an invite pending** sees the joining page; the first-run page appears only when there is neither a library nor an invite.
- **The account menu** holds Profile, Notifications, Libraries and people, Access tokens and devices, Appearance, Keyboard shortcuts and Sign out. Signing out with unsent changes says plainly what is only on the device and what happens to it.
- **Joining** has four moments: preview signed out, preview signed in, done, and one message for every link that does not work.

### D28. The shell prototype (decided with the maintainer, 2026-11-04)

Built in `docs/design/web/prototype/`, linking `apps/brand` in place and unchanged, with the new tokens in `proposed-tokens.css`. Everything drawn in Phase 2 in one go, then reviewed once and iterated, with a private copy for clicking through. The motion may be bolder than the first proposal. Turned down: changing `apps/brand` now; a new page in `apps/brand/preview`.

### D29. The header with one library and with several (decided with the maintainer, 2026-11-04, from the prototype)

Refines D12 and D14. With **one library** the library switcher is hidden and the header is **one row** on a tablet and on desktop: the mark, the app name, the app's links, then the palette, the bell and the account. Below the desktop width the palette shrinks to its icon so the row still fits. With **more than one library** it is the two tiers of D12, and **the wordmark sits between the mark and the library switcher** (the horizontal lockup, the real artwork, in its light and dark versions; never typeset). On a phone the mark stays alone (identity §12.2) and the app name sits beside it when there is one library.

### D30. Lorenzo Social joins the shell (decided with the maintainer, 2026-11-05)

A new app, from [RFC 0049](../../rfcs/0049-lorenzo-social-relationships-and-social-webs.md). It joins the **World** group, beside Calendars and Maps (D17). Its go-to chord is **G then O**. Its tabs are Webs (its Home), Relationships, Types and standings (for authors) and Problems (for staff); a person who may not write sees only Webs and Relationships. Its icon is the atlas's `icon-social`. The app list, the "Apps and about" drawer, the shortcuts list and the shell prototype carry it; its screens are in [social](social/README.md).

### D31. Writing is in Build (decided with the maintainer, 2026-11-05)

Writing moves from World to Build, beside Bench: it is where a person makes things, not where they look at the world. The groups are now Play (Sessions, Beings, Inventory), World (Calendars, Maps, Social), Build (Writing, Bench) and You (Account). Nothing else about Writing changes; the go-to chord stays G then W.

### D32. Profile and tokens are reachable from every app (decided with the maintainer, 2026-11-05)

Profile and Access tokens were drawn only in the account hub's prototype; the account menu of every other app's prototype opened a page that said it was not drawn. The two pages are now in the shell, so the menu opens them from any app. The account hub now uses the same pages, and its earlier copies are gone. They were redesigned from a brief in [account-hub/profile-and-tokens](account-hub/profile-and-tokens/README.md). A save bar rewrote its own buttons on every change, so a click on Save that followed an edit was lost; the shell's, the hub's and the profile's save bars now rewrite only when the count changes.

## Open questions

- Where parallax belongs beyond home and empty-state pages (D9).
- The set of patterns that carries state in greyscale, and the transition durations (the brand's §11.2 gives 150 to 220ms for small, 220 to 320ms for larger).
