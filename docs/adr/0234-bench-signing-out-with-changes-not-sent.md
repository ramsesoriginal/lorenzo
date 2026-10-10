# 0234 - Bench: signing out with changes not sent

Status: accepted, decided with the maintainer on 2026-10-09. The part of slice W-H of [RFC 0042](../rfcs/0042-bench-workbench-interface.md) that "can come earlier" than B4: the sign-out dialog. Builds on [ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md) (the outbox).

## Context

Bench holds what has been changed and not yet sent in the page ([ADR 0221](0221-bench-the-command-layer-and-the-first-editor.md): the outbox does not survive a closed tab until B4). Signing out, switching repository or closing the tab loses it, and said nothing.

## Decision

- **Signing out asks only when there is something to lose.** With nothing unsent, it signs out at once, as before: nothing is kept on this device yet that a person would care about.
- **With changes not sent, a dialog** (the prototype's words): "Sign out with 3 changes not sent?", that these changes are only on this device and signing out loses them, the entries they are on with a count each, and three ways out:
  - **Send them, then sign out**: sends what is waiting; when nothing is left it signs out. When there is no connection the button is off and the dialog says so. When a change could not be sent (a conflict, a refusal) it stays, and says how many need a look, so they can be opened or given up: Bench never signs out over a change it could not send without being told to.
  - **Give them up and sign out**: drops every change not sent, after what is being sent has finished, and signs out.
  - **Cancel** (and Escape): nothing happens.
- **The dialog never starts on the button that loses changes**: it is opened after the key press that asked for it has ended (an Enter would otherwise press whatever button had the focus), and focuses Send, or Cancel when Send is off.
- **The same guard is on the palette's "Sign out"** and on the title bar's button; both go through one function.
- **Closing or reloading the page with changes not sent asks first**, with the browser's own words (`beforeunload`), which also covers switching repository, which reloads. This is all the page can do about a closed tab until B4 stores the outbox.
- **A connection is known again as soon as the server answers**, even with a conflict as the answer; a conflict used to leave Bench believing it was offline.

## Not here

- The honest dialog of the prototype that talks about copies of repositories on the device and how big they are: there are none until B4.
- The start screen and the first run (W-H); the rest of W-H waits on B4.
- Per-repository counts: one repository is open at a time.

## Consequences

- Nothing a person typed is lost without being told, except by a crash.
- B4 changes the dialog's words (the changes are then kept on the device and only a sign-out loses them), not its shape.
