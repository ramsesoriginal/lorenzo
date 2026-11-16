# 0412 - Web page templates, and when a page saves

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D21.

## Context

Pages in the apps are one-offs: a settings page in one app saves on a button, a similar page in another saves as you type, and nothing tells the person which.

## Decision

- **Seven templates:** list and detail, reading, settings and forms, document editor, board, full-width workspace, and home.
- **Reading** has a 680px measure and the **editor** a 720px writing column. **Settings and forms** are capped at 1040px, with the label and help on the left and the fields on the right, and one column on a phone.
- **Saving is chosen per template.** A form with irreversible effects uses an explicit bar at the bottom ("1 change not saved", Discard, Save changes; a border, not a shadow). Writing and entry fields autosave and say "Saved". Every screen says which it is, by its state. Later app designs add: a field that changes something reversible saves as it is changed with an Undo (Beings, Social, Profile); structure that can break links keeps the explicit bar (Inventory's catalog).
- **Home** has the app's own blocks first, then the shared "Continue" and "What do you want to do?".
- **Full width**, exempt from the cap: the board, the full-width workspace and the editor's outline pane.

## Consequences

- The explicit bar rewrites its own buttons only when the number of changes changes; rewriting them on every change lost a click on Save that followed an edit (found while building the prototypes).
- Autosave and the explicit bar both need an honest offline state (a change kept on the device is said to be).
