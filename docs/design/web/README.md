# Lorenzo web interfaces: design

The design guidelines for Lorenzo's web interfaces and a fresh design of each web app, worked out with the maintainer on clickable prototypes. This page holds the brief and the decision log. Nothing is decided until it is in the log.

Status: Phase 2 (the shell). Header decided; navigation between apps next, then the footer. No prototype is committed yet.

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

## Input for the footer (not decided)

From the maintainer, 2026-11-04. The footer shows information (current version, a date or clock, links to the Impressum and the Datenschutzerklärung) and a status bar with meta information specific to the app (word counts in Writing, carried weight in the inventory, and similar). The navigation between apps may also live there. Decided after the navigation between apps.

## Open questions

- Where parallax belongs beyond home and empty-state pages (D9).
- The set of patterns that carries state in greyscale, and the transition durations (the brand's §11.2 gives 150 to 220ms for small, 220 to 320ms for larger).
