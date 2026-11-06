# 0415 - Toasts, Undo, dialogs and menus

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D26.

## Context

Apps confirm and undo in different ways, and a generic "Are you sure?" appears where Undo would do.

## Decision

- **Toasts** are at the bottom center, directly above the status bar (above the tab bar on a phone), in a live region. Three kinds: a quiet confirmation, a reversible action with **Undo**, and an error that stays until dismissed and offers "Try again". A toast that leaves by itself stays **10 seconds**, shows a progress bar counting down, and the timer pauses and resets while the pointer is over it or focus is in it.
- **Undo or confirm.** A reversible action (delete an entry, move, change who sees it) is done at once and offers Undo. An irreversible or large one asks first, in a dialog that names what is lost, with counts the person may know; the largest asks for the name to be typed, and its button says what it does and stays disabled with a reason. Never a generic "Are you sure?". Reversible bulk actions also use Undo.
- **Dialogs** are centered on desktop (the first field takes focus, Enter submits, Esc cancels); at the tablet step and on a phone a dialog is a bottom sheet with stacked buttons, the safe choice first.
- **Menus** are popovers with shortcut hints and a divider before a destructive item; a row's actions are a visible button, never hover-only; on a phone a menu is a bottom sheet with 44 to 48px rows.
- **A refusal is shown as the API gave it,** next to the field or cell, and the draft is kept; a stale write (412) keeps the draft and offers a reload.

## Consequences

- Undo needs each reversible action to have an inverse; the prototypes use a snapshot, which a real app replaces with the command layer of its own.
- An action that cannot be undone says so before it is done (revoking a token, deleting an account).
