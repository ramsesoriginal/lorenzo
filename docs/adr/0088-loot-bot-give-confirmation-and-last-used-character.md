# 0088 - loot-bot: `/give` confirmation and last-used-character memory

Status: accepted

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 3, two small changes that share one file and one risk.

**`/give` moves an item out of the caller's inventory the instant the command is submitted.** `/undo` exists ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)) but is best-effort and short-lived, and a mistyped autocomplete pick is easy. One deliberate click before it happens is cheap insurance.

**The bot makes players restate which character they mean.** `/drop` take/claim and `/note visibility:private` need a "current character" and stop with "Set a current character first — run `/set-current`" when none is stored. `/set-current` ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)) is explicit-only, so a player with several characters has to keep re-running it as they switch. Working the RFC's sketch ("a command that succeeds with an explicitly-passed character updates the preference") against the real commands showed it doesn't fit: **no command takes an option naming *your own* character** — `/give to:`, `/award`, `/confiscate`, `/inspect` and `/add-to-group` all name *someone else's* (or a GM's target), and `/set-current` already stores its own. The signal that actually exists is the *item*: when you give, move, rename, or merge something, its owner tells us which of your characters you were acting as.

Two adjacent facts from the code shaped the design:

- The command runs on Cloud Run ([ADR 0053](0053-loot-bot-http-interactions-and-cloud-run-deploy.md)), which can scale out. A button click can land on a different instance than the one that showed it, so an in-memory pending-action map (`pending-bulk-give.ts`'s shape) would sometimes lose the click's state.
- `getPreference` ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)) fell back to the global-default row only when *no channel row existed at all*. A channel row created by `/set-current container:...` alone has no character and so **hid** the global one — which would have silently defeated remembering a character for exactly the players most likely to have used `/set-current`.

## Decision

### `/give` asks first, statelessly

- `/give` no longer transfers anything. It reads the item and the target (only to word the prompt and fail early — unreachable item, unknown target, a quantity on a non-stack), then replies ephemerally with `Give **Torch ×5** to **Sam**?` (or `**2 of Torch** (you have 5)`) and **Give / Cancel** buttons. The transfer happens in `onButton`.
- **The intent lives in the button's `customId`**: `give:ok:<item id>:<target id>:<quantity|all>`. No bot-side state, so any instance can serve the click. It fits Discord's 100-character limit even at the largest quantity an integer option can carry (98); a test pins that, since exceeding it fails at send time.
- **Re-validated at click time**, exactly as the command used to do inline: fresh `GET` with its `ETag`, then `transferItem`'s split-vs-whole decision against the stack *as it is now* ([ADR 0051](0051-loot-bot-give-command.md)). The prompt may sit for a long time, so it decides nothing.
- **A double-click can't give twice.** The click is acknowledged with `update({ content: "Giving…", components: [] })` — the buttons vanish as part of the acknowledgement, before any work — rather than `deferUpdate`. That matters because a partial give is a *split*, which isn't idempotent. This needed `update` added to the button interaction type and adapter (the select-menu and modal adapters already had it).
- The message is ephemeral, so only the invoker can click; the undo recording, "remember" step and result text are otherwise unchanged.
- **No expiry and no skip option.** Stale confirms are safe because of the re-validation; and "one click before it leaves" is the whole feature, so it isn't opt-out. `/give-bulk` already has a multi-step flow, and `/reassign`/`/confiscate` are GM tools where friction is a different trade-off — none changed here.

### Last-used character: remember the owner of what you acted on

- After a **successful** `/give`, `/move`, `/rename`, or `/merge`, if the item's owner is one of the caller's *own* characters (`getControlledCharacters`), it is stored as the caller's default in the **global-default** row ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)), so it applies server-wide (one bot = one guild).
- **Only characters you control.** A GM moving a player's item, or an ownerless item, says nothing about who the GM is playing.
- **A channel `/set-current` still pins.** A channel-specific value always beats the global one, so an explicit choice is never overridden by memory; "override anytime" is `/set-current` (or, as always, changing what you do next).
- **Best-effort.** It runs after the write already succeeded; a failure (API blip, DB error) is logged at `warn` and swallowed, never turning a completed give into an error message.
- **`getPreference` now falls back per field, not per row**: a channel row that sets only a container inherits the global character, and vice versa. One query (`IN (channel, global)`) instead of two. This is a bug fix in its own right — the old behaviour contradicted `setPreference`'s own "only touch the fields given" semantics, where an unset field means *unset*, not *deliberately empty*.
- **`/drop` take names who got the item** (`Took 2 of Torch for Frodo.`), best-effort. With a default that can now move by itself, loot landing on the wrong character has to be visible where it happens, not discovered in an inventory later.

### Where memory does *not* update

`/drop` take/claim and `/note` *consume* the default and don't write it, and `/reassign`/`/confiscate`/`/inspect` are GM tools acting on other people's characters. `/move-bulk` (a container, not an owned item's owner) is left alone rather than guess. Any of these can be added later by the same one-line call if it turns out to matter.

## Consequences

- `/give` is now two interactions instead of one, with one extra API read (the prompt) and one extra API read on the click's `getControlledCharacters` for the remember step. Both are small; the click has no 3-second-ack pressure because it acks first.
- `ButtonInteraction` gains `update`, and `getPreference` changes semantics for anyone with a container-only channel row — strictly toward what `setPreference` already implied.
- `/give`'s tests move their transfer assertions from `execute` to `onButton`; `execute` now tests the prompt.
- Not built: a channel-scoped memory (the global row is enough, and `/set-current` covers channel pinning), auto-defaulting to your *only* character when nothing is stored (`/link` already does this at link time; a player who gains a character later still hits "Set a current character first" until they use any of the four commands above), and a "current character" line in `/whoami`. The last two are the obvious next steps if the wall turns out to bite.
