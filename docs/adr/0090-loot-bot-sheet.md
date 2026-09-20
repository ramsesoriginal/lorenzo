# 0090 - loot-bot: `/sheet`

Status: accepted

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 5a. A player's character has stats and lore, but the only way to see either from Discord was `/item` with a raw entity id — and `/item` posts publicly, by design ("showing it off is the point"). A player wants to glance at their own sheet privately, by character name.

Checked against the real API before building anything:

- `GET .../entities/{id}` returns `EntityDetailOut` for any entity, characters included ([ADR 0039](0039-generic-effective-stat-view.md): every entity's stats resolve through `v_effective_stat`). `stats` is the *resolved* value after prototype inheritance ([ADR 0037](0037-effective-stat-resolution.md)); `information` is already filtered server-side to what the caller may see (`information_visibility.py`, [ADR 0035](0035-campaign-scoped-gm-visibility.md)/[0028](0028-knowledge-and-group-membership.md)) — GM-only text about your own character is simply absent for you.
- `stat_groups` on that response is a list of group *entities*, with no mapping from each stat to its group, so a sheet can't honestly be laid out "by group" without an API change.

## Decision

`/sheet [character]` — a private (ephemeral) view of one character, rendered with the existing `formatItemEmbed`: a **Stats** field of resolved `name: value` lines, then each visible `Information` entry as its own field.

- **No new rendering, deliberately.** The API returns the same shape for a character as for an item, so a second formatter would only diverge. If a sheet-specific layout is wanted later (stats grouped, inline pairs), it needs the stat-to-group mapping from the API first.
- **Visibility is the API's, not the bot's.** As with every command here ([ADR 0050](0050-loot-bot-stack-linking-and-isolation.md)) the read is made as the person who ran it; the bot filters nothing and has no GM-secret to leak.
- **Which character:** the `character` option if given (autocompleted from the caller's own characters via `getControlledCharacters`); otherwise the stored `/set-current` default ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md), through `resolveCurrentCharacter`); otherwise, **if the caller controls exactly one character, that one** — so a single-character player configures nothing. With several characters and no default it asks them to pick, rather than guessing.
- The option accepts any character id, not only your own (same "autocomplete is a convenience, not a restriction" principle as `/give`, `/item`); whether you may read someone else's sheet is the API's call, and a 403/404 becomes a friendly "couldn't open that sheet".
- **Private by default, with no public option.** `/item` already exists for showing something off; a sheet often carries player-visible notes the player may not want in a channel.

### Not built

- **Updating the remembered character** when `character` is passed explicitly. [ADR 0088](0088-loot-bot-give-confirmation-and-last-used-character.md) established `rememberActingCharacter`, and `/sheet` is in fact the first command with an explicit own-character option — but that helper lives on a different, still-open branch. Once it lands, this is a one-line call and is the obvious follow-up.
- Stat grouping, a public variant, and other players' characters in autocomplete (a GM has `/inspect` for inventories; a GM's view of a sheet is a separate question).

## Consequences

- One more command (27 registered), grouped under "Account" in `/help` until the task-grouped help ([ADR 0089](0089-loot-bot-task-grouped-help.md)) lands — which then needs `sheet` added to its "See what you have" group (its coverage test will fail until it is, by design).
- No API change, no schema change, no new dependency. Requires re-running `mise run register-commands` after deploy like any new command.
