# 0282 - The being sheet's shell: modes, sections and the sticky bar

Status: accepted, decided with the maintainer on 2026-10-12. Slice U1 of [RFC 0043](../rfcs/0043-the-being-sheet.md); builds on [ADR 0270](0270-beings-app.md) to [0272](0272-beings-editing-stats-and-handing-over.md). The design is [docs/design/beings](../design/beings/README.md); where this and the prototype disagree, the prototype wins.

## Context

A being's page was one column of separate sections, with editing as a second stack of forms below. The design asks for a page that a GM, a player at the table, an author and a skirmish player can all use, by letting the person pick how they look at the being.

## Decision

- **Three modes, Read, Play and Edit**, in a segmented switch in the header and again in a sticky bar, so changing mode never means scrolling back. A mode says what you are doing, not what you may do: the API still decides every write. **Edit is offered only** to those who may write (a GM of a campaign the being is in, a tenant administrator, the player of the being); for anyone else the control is disabled with its reason, and a mode that cannot be drawn falls back to Read (`lib/sheetMode.ts`).
- **The mode is not remembered.** A page opens in Read. (Open question 5 of the design brief: remembering it per library or per being can be added without changing anything else; nobody asked for it.)
- **The sections keep one DOM order and take their visual order from the mode:** Read puts About, Notes, Stats, Inventory; Play puts Stats, Inventory, Notes, About; Edit follows Read, so the page does not jump when you start building. Order is set with CSS `order`, so focus order and the document stay the same for assistive technology.
- **Edit-only parts** (the name, link name, picture and tag forms, the stat forms, handing over) sit where they are drawn and are shown only in Edit (`data-only-in`). The existing forms and their behaviour are kept; U2 replaces the stat forms with fields in the stat tiles.
- **Notes can be added in every mode.** Moving, editing and deleting a note are shown in Edit only.
- **The sticky bar** appears when the header scrolls out of view (`IntersectionObserver`): the name, a few numbers, links to the sections and the mode switch. Until the library says which stats to keep in view (U2), it shows the first three numbers of the first group.
- **One live region** says what changed ("Play mode"), so a screen reader hears the change and not the page.
- **The stat area** is drawn as groups of tiles on a surface of its own, with the provenance in words ("From Dwarf", "Calculated"); U2 adds what Play does with them.
- **No token is defined and no brand file is changed.** `styles/sheet.css` is the prototype's stylesheet over the brand's tokens; each addition is a candidate for `apps/brand` once a second app needs it ([ADR 0098](0098-branding-css-app-and-package.md)).

## Not in scope

Changing numbers in Play, the undo, provenance panels (U2); the datasheet layout (U3); entity templates; remembering the mode.

## Consequences

The e2e tests enter Edit before using a form. A page for someone who may not edit has no way into a form at all, as before, now stated by the disabled switch.
