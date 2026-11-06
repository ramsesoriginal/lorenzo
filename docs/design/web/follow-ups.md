# Web interfaces: follow-ups for `apps/brand` and the apps

What the design needs that does not exist yet. This list is a plan, not a change: nothing here is done by [RFC 0050](../../rfcs/0050-the-web-interface.md) itself, and `apps/brand` is untouched. Each item is a part of slice UI-A (tokens and components) or of the app's own slice. The prototypes carry working versions in [`prototype/proposed-tokens.css`](prototype/proposed-tokens.css) and `prototype/shell.css`.

## Tokens and base

- `--border-control`: a control edge at 3 to 1 against its surface (WCAG 1.4.11), light and dark.
- Container-driven spacing and the steps 720, 1100 and 1700 as container queries; 430 as the phone design width.
- Type roles and a 12px step; the density levels (comfortable, compact) as tokens.
- Transition durations and easings as tokens, all removed by reduced motion; `.horizontal-mask` for scrolling rows.
- Contrast finding: `--text-tertiary` on `--surface-selected` is below 4.5 to 1; fix the pair or stop using it there.

## Components

- Button and field with the control edge; segmented control; switch; menu; sheet and dialog; toast with a timer and Undo.
- Palette; state strip; status bar; tab bar; header with one or two tiers; apps drawer.
- State chip with patterns (not colour alone); save bar that rewrites only when the count changes; skeleton rows.
- A class-clash test: shell class names against every app stylesheet.
- A shared time filter (Sessions, Calendars, Social); a tool registry contract for the palette.
- Graph and matrix grammar pieces: standing cell (number, quiet bar, mark and word), state marks, lens line, focus dimming (identity §18).

## Icon atlas

- Relationship: two overlapping rings, `icon-kind-relationship`. Social web: `icon-kind-social-web`, drawn from `icon-social`. Both added with the Social scaffolding slice ([ADR 0408](../../adr/0408-lorenzo-social-the-app.md)).
- Empty-state and app-destination icons the prototypes use where the atlas has none.

## Mascot images

- The four added in [mascot-images.md](mascot-images.md): empty social types, empty relationships, empty social web, device connected.

## Maps

- The Maps follow-ups listed in [maps/README.md](maps/README.md).

## Apps

Each app drops its own header, footer, button and field styles when its slice lands (UI-H). No app is changed before its slice.
