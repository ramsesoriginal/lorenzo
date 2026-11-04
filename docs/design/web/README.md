# Lorenzo web interfaces: design

The design guidelines for Lorenzo's web interfaces and a fresh design of each web app, worked out with the maintainer on clickable prototypes. This page holds the brief and the decision log. Nothing is decided until it is in the log.

Status: Phase 2 (the shell). Header, navigation between apps and footer decided; type and spacing decided; states next. No prototype is committed yet.

## Layout of this directory

- `web/` (this directory): the system. Brief, decision log, shell prototype, screens.
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

By job: Play (Sessions, Beings, Inventory), World (Calendars, Maps, Writing), Build (Bench), You (Account). The names of the groups are working names.

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

## Open questions

- Where parallax belongs beyond home and empty-state pages (D9).
- The set of patterns that carries state in greyscale, and the transition durations (the brand's §11.2 gives 150 to 220ms for small, 220 to 320ms for larger).
