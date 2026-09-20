# 0089 - loot-bot: `/help` grouped by task, with a first-run intro

Status: accepted

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 4. [ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)'s addendum added `/help` when the bot reached 25 commands: a hand-maintained `CATEGORIES` list (Account, Inventory, Groups, GM tools, Loot drops, Utility) rendered as one embed field per category, each line `/name — description`. It's accurate, but it answers "what commands exist" rather than "how do I do the thing I came to do":

- The categories are by *kind of object*, not by *goal*. "Inventory" holds ten commands with no order — `/move-bulk` sits between `/item` and `/merge`, and nothing says `/inventory` is where a newcomer starts.
- Nothing tells a first-time user what to do first, although the answer (`/link`, then `/inventory`) is the same for everyone.
- `/help`'s own registered description, "List every command, or show one command's full options", describes the mechanism, not why you'd run it.

The fix has to stay a discoverability fix. Renaming or restructuring the commands themselves (a 26-command reshuffle into subcommands, say) would break muscle memory for a problem that doesn't need it — RFC 0021 ruled that out explicitly, and it also collides with ADR 0053's note that this bot deliberately uses no subcommands.

## Decision

### Regroup by task; move nothing

`HELP_GROUPS` (renamed from `CATEGORIES`, and exported so tests can check it) is re-cut around what someone is trying to do, in the order a newcomer needs them:

| Group | Commands |
| --- | --- |
| Getting started | `/link` `/whoami` `/set-current` `/introduce` |
| See what you have | `/inventory` `/item` `/my-groups` |
| Give, move, and tidy | `/give` `/give-bulk` `/move` `/move-bulk` `/merge` `/rename` `/undo` |
| Notes and groups | `/note` `/add-to-group` |
| Loot drops | `/drop` `/pending-claims` |
| GM tools | `/award` `/inspect` `/confiscate` `/reassign` `/add-channel-to-group` |
| Housekeeping | `/unlink` `/ping` `/help` |

No command is renamed, removed, or has its options changed. Every command still appears exactly once.

### A short intro, the same for everyone

The overview gains a description: *"Lorenzo keeps track of what your characters carry. New here? Run `/link` to connect your Lorenzo account, then `/inventory` to see what you've got. The rest are grouped by what you're trying to do."* The title becomes "Lorenzo — what would you like to do?".

It is deliberately **not** tailored to whether the caller has linked. That would need a `linked_account` lookup, and `/help` is the one command with no dependency on anything being up (the `/ping` precedent ADR 0068 cited); a help command that fails when the database is down is worse than one that offers "run `/link`" to someone already linked. The cost of the static version is one sentence a linked user skims past.

### Say who a group is for

A group may carry a one-line `note`, shown in italics above its commands: *Loot drops* — "Only a GM can start a drop; anyone can check what's outstanding"; *GM tools* — "For a campaign's GM - these won't work for other players." Those are today's real authorization rules, previously discoverable only by trying the command and being told no.

### A command's detail view says where it lives

`/help command:give` gains a footer, "Part of: Give, move, and tidy — run /help for the rest", so someone who arrived by name (or from a link in chat) can find its neighbours. A command in no group gets no footer.

### `/help`'s own description is rewritten

"New here? Start with this: every command, grouped by what you want to do." Descriptions are registered with Discord, so this needs `mise run register-commands` after deploy, like any command change (`apps/loot-bot/README.md`). Every other command's description is untouched — the GM-only ones already say so or are covered by the group note, and changing 25 registered strings to prefix them would be churn for no gain.

### The safety net becomes a test

`ctx.commands`-driven rendering plus an `Other` fallback (ADR 0068) already kept a forgotten command from vanishing, but it kept it visible *under the wrong heading*. `help-command.test.ts` now checks, against the real registered command list rather than fixtures, that every command has a group, that `HELP_GROUPS` names no command that isn't registered (a typo would otherwise quietly render nothing), that none appears twice, that the full overview stays inside Discord's embed limits (1024 per field, 6000 total, no `Other` bucket), and that every command description is within Discord's 100-character limit. Adding a command now fails CI until it's grouped.

## Consequences

- Grouping is still hand-maintained, by name — nothing on a `Command` says what it's for — but a missed entry now fails a test instead of shipping under "Other".
- The overview is one embed with seven fields, comfortably inside Discord's limits with the real descriptions; if the command count doubles, the same test says so before Discord does.
- `dispatch-commands.test.ts` referenced the old "Utility" group by name and was updated — that end-to-end test (it proves `dispatchInteraction` really injects the command list) remains the only thing tying `/help` to the real dispatcher.
- Not built: a linked-vs-not-linked tailored intro (see above), per-command usage examples, a `/help` that pages or uses buttons per group, and a "GM only" marker on individual lines. Any is a small follow-up if the flat overview turns out not to be enough.
