# RFC 0050: The web interface: one shell, one grammar, and the order to build it in

- **Status:** accepted, decided with the maintainer (2026-11-06), from clickable prototypes agreed with them one decision at a time. The open questions below stay open; each is settled in the ADR of the slice that needs it. Built so far: UI-A to UI-D and Calendars and Sessions of UI-E (ADR 0426 to 0428, 0433, 0440 to 0442); the rest is tracked in #1020.
- **Builds on:** [RFC 0049](0049-lorenzo-social-relationships-and-social-webs.md) (Lorenzo Social), [RFC 0047](0047-lorenzo-writing.md) (Writing), [RFC 0048](0048-locations-maps-connections-and-optional-dates.md) (Maps), [RFC 0046](0046-sessions-scenes-and-lived-order.md) (Sessions), [ADR 0273](../adr/0273-app-links-registry.md) (app links), [identity](../brand/identity.md).
- **Picture:** [docs/design/web](../design/web/README.md) and its clickable prototypes, one per app.

## Summary

The web apps were built at different times and look different for the same jobs. This RFC records a design for all of them at once: one shell (header, navigation, status bar), one set of page templates and states, one keyboard model, and a redesign of each app inside it. Each decision of substance is an ADR (0409 to 0424). The guideline text is in [identity](../brand/identity.md); the changes to `apps/brand` are a list of follow-ups, not part of this change. No application code is written by this RFC.

## 1. Decisions

1. **Principles** ([ADR 0409](../adr/0409-the-web-interface-principles.md)): ten tests a screen can fail; a control has a visible edge; neutral first.
2. **A shell** ([ADR 0410](../adr/0410-the-web-shell-header-navigation-and-status-bar.md)): two header tiers (one with a single library), a bottom tab bar on a phone, a state strip, a status bar, apps grouped by job, no app switcher.
3. **Widths, containers, density and type** ([ADR 0411](../adr/0411-web-widths-containers-density-and-type.md)).
4. **Page templates and saving** ([ADR 0412](../adr/0412-web-page-templates-and-saving.md)).
5. **States and the mascots** ([ADR 0413](../adr/0413-web-states-and-the-mascots.md)).
6. **The palette and the keyboard model** ([ADR 0414](../adr/0414-the-palette-and-the-keyboard-model.md)).
7. **Toasts, Undo, dialogs and menus** ([ADR 0415](../adr/0415-toasts-undo-dialogs-and-menus.md)).
8. **First run, the account menu and joining** ([ADR 0416](../adr/0416-first-run-the-account-menu-and-joining.md)).
9. **Per app:** Account hub ([0417](../adr/0417-account-hub-redesign.md)), profile, access tokens and connecting a device ([0418](../adr/0418-profile-access-tokens-and-connecting-a-device.md)), Writing ([0419](../adr/0419-writing-redesign.md)), Calendars and Sessions ([0420](../adr/0420-calendars-and-sessions-redesign.md)), Maps ([0421](../adr/0421-maps-redesign.md)), Beings ([0422](../adr/0422-beings-redesign.md)), Inventory ([0423](../adr/0423-inventory-redesign.md)), Social ([0424](../adr/0424-social-redesign.md)).
10. **The prototypes are a reference, not a starting point.** Their logic is ported where it was written as pure functions and re-tested; their markup and styles are not copied. Bench and the authoring app are not covered here (see section 3).

## 2. From the design to slices

| Id | What | Depends on |
| --- | --- | --- |
| UI-A | Tokens and components in `apps/brand`: the follow-ups in [follow-ups](../design/web/follow-ups.md), each with a test | none |
| UI-B | The shell as a shared package: header, tab bar, state strip, status bar, apps drawer, palette, toasts, dialogs | UI-A |
| UI-C | Page templates, save bar, states and mascots, skeletons, the class-clash test | UI-B |
| UI-D | Account hub, profile, tokens and connecting a device in the shell | UI-C |
| UI-E | Writing, Calendars and Sessions, Maps | UI-C |
| UI-F | Beings and Inventory | UI-C |
| UI-G | Social (the app itself is RFC 0049's) with the two kind icons | UI-C, RFC 0049 slices |
| UI-H | Retire each app's own header, footer and button styles once its slice lands | UI-D to UI-G |

**First step: UI-A.** It touches no app and nothing else can start without it.

## 3. Not in scope

Bench and the authoring app (their designs are under [docs/design/bench](../design/bench/README.md)); the mobile and Discord apps; changes to any API; the renderer package and layout engines of RFC 0049; real-time collaboration.

## 4. Open questions

- **Tool registry contract.** The palette lists commands from each app; whether apps register them at runtime or declare them is settled with UI-B.
- **A shared time filter** for Sessions, Calendars and Social: one component or three, settled with UI-E.
- **Windowing** of very large matrices and lists in the real apps, settled with UI-G.
- **Tertiary text on selected surfaces** has a contrast finding listed in the follow-ups; the fix is a token change in UI-A.
