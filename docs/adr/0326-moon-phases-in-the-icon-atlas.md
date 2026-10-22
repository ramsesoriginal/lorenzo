# 0326 - Moon phases in the icon atlas

Status: accepted, decided with the maintainer on 2026-10-22. Extends [ADR 0274](0274-the-atlas-grows-for-bench-kinds-and-states.md) and [identity §17.4](../brand/identity.md#174-custom-domain-icons).

## Context

Calendars draws a moon's phase with the emoji 🌑 to 🌘. They ignore the theme, differ between platforms, are not part of the atlas, and carry their label by `title` and `aria-label` on a bare `span`. The calendar engine reports a phase as an integer from 0 to 7 (`int(fraction * 8)`, new moon first, [ADR 0308](0308-authored-calendars-and-calculation.md)). Tabler has a `moon` and a `moon-stars` but no set of phases.

## Decision

- **Eight custom symbols**, one per phase band, named by meaning: `icon-moon-new`, `icon-moon-waxing-crescent`, `icon-moon-first-quarter`, `icon-moon-waxing-gibbous`, `icon-moon-full`, `icon-moon-waning-gibbous`, `icon-moon-last-quarter`, `icon-moon-waning-crescent`. Phase *n* is the *n*th in that order.
- **Drawn in Tabler's grammar** (24×24 box, 2px stroke, round caps and joins, outline first, `currentColor`, no baked-in colour): the circle's outline with the lit part as one closed arc path, so the full moon is the circle and the new moon the outline alone. They are listed in `icons.manifest.yaml` as Lorenzo-owned custom icons, separate from upstream originals, and shown on `preview/icons.html`.
- **Words say the phase.** An icon reinforces state ([§17.8](../brand/identity.md#178-state-and-status)): the moon's name and its phase ("Selene: Waxing gibbous") are text in the day's accessible description and in the selected day's panel, and the icon itself is decorative.
- **The existing check applies**: the test that reads the sprite and the manifest fails when they list different icons.

## Not in scope

A different moon model, more than eight bands, or colour for a phase.

## Consequences

- The sprite gains eight symbols; a day cell with several moons uses `.icon` like any other.
- The phases follow the theme and render the same everywhere.
