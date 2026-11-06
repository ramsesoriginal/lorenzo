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

## UI-A: what is in `apps/brand` and how it was checked

Slice UI-A (#1012) of [RFC 0050](../../rfcs/0050-the-web-interface.md) is built in `apps/brand`, in six stacked pull requests, and checked against the prototype.

| Item | Where |
| --- | --- |
| `--border-control`, type roles, `--dur-*`/`--ease`, `--space-2h`, the `--text-tertiary` contrast fix | `tokens.css` |
| Container steps, density (48, 36, 28px; 64px and 44px targets on a phone), page widths | `layout.css` (`.shell-container`, `.shell-app`, `.shell-page`) |
| Control edge on fields, buttons and the switch; `.segmented-control`; `.icon-button`; `kbd` | `components.css` |
| Menu, bottom-sheet dialog, toast with Undo | `components.css` (`.menu`, `dialog`, `.toast-card`) |
| Global bar, app bar, state strip, status bar, tab bar, apps drawer, palette, state chip | `components.css` (`.shell-*`, `dialog.palette`, `.state-chip`) |
| Save bar, skeleton rows, sideways fade | `components.css` (`.save-bar`, `.skeleton-row`, `.horizontal-mask`) |
| Graph and matrix grammar: standing, edges and nodes, focus dimming, lens line, legend, matrix, time filter | `components.css` (`.standing`, `.graph-*`, `.lens-line`, `.graph-legend`, `.matrix`, `.time-filter`) |
| Class-clash test; palette command contract | `web-classes.json`, `palette-command.schema.json`, `tests/` |
| Icon atlas additions | `icons.svg` (the Relationship and Social web kind icons; the only two the prototypes lacked) |

**How it was checked.** The Dialogs, Shell, Pages and Graph previews show each part. Browser checks (Chromium, light and dark, 1440 and 430 wide) cover behaviour and contrast, and the brand's computed styles were compared, element by element, with the prototype's for the global bar, library and palette buttons, avatar, app bar and tabs, status bar, tab bar, buttons, input, menu, dialog, toast and palette: spacing, heights, edges, radii, fonts and colours agree. The compare found and fixed these: the overlay and bar surfaces are `--surface-canvas`, an overlay's edge is `--border-subtle` with the prototype's shadows, the scrim has no blur, a button and a field are 36px tall (44px on a phone), the status bar's button is 24px, the palette has its preview pane from 1100px, and an icon in a flex row does not shrink.

**Differences kept on purpose.**

- The previews show the text lockup, not the lockup picture, because `apps/brand` is deployed alone.
- A dialog fades in but does not move and closes at once, because two Account Hub tests reopen a dialog straight after Cancel and measure a sheet as it opens; the closing transition returns when an app's tests can wait for it.
- Menus, dialogs and toasts follow the window; the shell's bars follow their `.shell-container`.
- The palette's preview pane holds whatever the app puts in it; the contract for what an app declares is `palette-command.schema.json`, and how it registers at runtime is settled with the shell package (UI-B).
- The class-clash test found and fixed four real clashes with Beings (`.segmented`, `.toast`, `.state`, `.legend`, and `.icon-btn`, now `.segmented-control`, `.toast-card`, `.state-chip`, `.graph-legend` and `.icon-button`).
