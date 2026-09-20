# 0097 - loot-bot: `/changes`, a bot-recorded view of what happened to your stuff

Status: accepted

Numbered 0096 originally; renumbered to 0097 on merge into `main`, which had independently claimed 0096 for the tenant-OWNER/ORGA information-visibility ADR in the meantime. Same renumbering precedent as ADR 0050/0054's own history (see [docs/adr/README.md](README.md)).

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 7. A player wants a private answer to "what happened to my characters' belongings since I last looked" — a gift from another player, an award, a confiscation, a loot drop they missed. It is distinct from a GM's view: [ADR 0063](0063-tenant-activity-log.md)'s activity log is tenant-admin-only and deliberately covers only seven membership and campaign mutations, none of which are item moves.

The API has nothing to build this from. There is no per-player change feed, and `updated_at` can't stand in for one: owner and container writes deliberately never bump it ([ADR 0051](0051-loot-bot-give-command.md)'s addendum). The complete answer is [RFC 0022](0022-player-facing-change-feed-api.md), an `apps/api` change; it was agreed, when this slice was scoped, that `/changes` would meanwhile be **bot-recorded only** and would say so, building nothing RFC 0022 would have to unpick.

The bot also keeps no history today: `pending_undo` is one overwritten row per user, and a drop's claims are deleted once applied. So this slice needs an event log of its own, and a call in every command that moves belongings between characters.

## Decision

### What gets recorded

An event is written **after the underlying write succeeded** — never before, so the log can't describe something that didn't happen — for:

| Command | Recorded as | Filed under |
| --- | --- | --- |
| `/give` | "Frodo gave Torch ×5 to Sam." | giver and receiver |
| `/give-bulk` | "Sam was given 3 items: Sword, Torch ×5, Rope." | receiver only |
| `/reassign` (GM) | "Torch was reassigned from Frodo to Sam." | both characters |
| `/award` (GM) | "Frodo was awarded Sword." | the character |
| `/confiscate` (GM) | "Sword was taken from Frodo." | the character |
| `/drop` take | "Frodo took Torch from a loot drop." | the character |
| `/drop` apply-claims | "Frodo received Sword from a loot drop claim." | each honored claimant |

- **Bulk gives record the receiver only**: a `bulk-assign` result doesn't say who each item came from.
- **GMs are never named.** `/changes` shows what happened to your stuff, not who decided it; whether an actor should ever be shown is an open question in RFC 0022, and leaving it out now can't leak something later.
- **Left out on purpose:** the player's own housekeeping — `/move`, `/move-bulk`, `/rename`, `/merge`, `/undo`, `/container-new`. RFC 0021 named moves and undo, but "since I last looked" is about things that happened *to* you, and those are the noise: a log dominated by your own tidying would bury the gift you were looking for. Each is one more `recordCharacterEvents` call if it turns out to be missed.

### Storage: keyed by character, not by Discord user

`loot_bot.character_event(id, event_id, character_entity_id, kind, summary, created_at)` and `changes_seen(discord_user_id, seen_at)` (migration `0004`), no RLS, like the bot's other tables.

- **One row per affected character**, because the bot has no reverse lookup from a character to whoever plays it — but a player can always list the characters *they* control. So "events for my characters" is answerable; "events for that Discord user" wouldn't be, and a *received* gift would be invisible to its receiver.
- **`event_id` is shared by an event's rows**, so a player who controls both sides of a transfer sees it once.
- **The summary is rendered when recorded**, from names the acting user was allowed to read at that moment. The viewer may not be allowed to look up the other character's name later. It names characters rather than saying "you" so it reads correctly for a player with several characters, and it is truncated at 500 characters.
- **A failed name lookup degrades, never drops** — the id decides *who sees* an event, so a missing name only weakens the wording ("another character").
- Rows older than **90 days** are pruned (opportunistically, on `/changes` — the log is a convenience view, not a ledger).

### `/changes [history]`

Private. Reads the events for **the caller's own characters** (`getControlledCharacters`, as the caller) newer than the caller's **last-looked marker**, newest first, up to 25, with a relative timestamp (`<t:…:R>`) on each and a count of how many older ones a full list left out. `history:true` shows the recent past regardless and doesn't move the marker; a first look, with no marker, shows the recent past rather than an empty list. The marker is set to the moment the command *started reading*, after the reply is sent, so a change recorded mid-command shows up next time instead of being skipped.

**Every reply — including an empty one — carries a note that only changes made through this bot are shown.** Without it, "Nothing new" would read as "nothing happened" when the truth may be "nothing happened *through the bot*". That is the honest limit of a bot-recorded view, and it goes away when RFC 0022 lands.

### Recording is best-effort

`recordCharacterEvents` swallows and logs failures: it runs after a write that already succeeded, and a missing log line must never turn a completed give into an error message. The trade-off — an occasionally missing entry — is the right way round for a convenience view.

### Options: `getBoolean`

`/changes history` is this bot's first boolean option; `OptionsReader` and the interaction adapter gain `getBoolean` (null when Discord omits an unset option, and for a non-boolean value).

## Consequences

- **Partial by construction.** Anything done through `apps/inventory-web`, `apps/account-hub`, or the API directly never appears, and neither do actions taken before this shipped (nothing is backfilled).
- **Extra API reads.** Recording a give or reassign costs up to two `getCharacterName` lookups, best-effort and after the write.
- **Migration `0004`.** Other open branches ([ADR 0094](0094-loot-bot-container-new.md), [ADR 0095](0095-loot-bot-notification-dms.md)) also add a `0004`; drizzle numbers them sequentially, so whichever lands after the first must regenerate its migration (`mise run //apps/loot-bot:db-generate`).
- **Migrating to the API feed.** When RFC 0022 lands, `/changes` switches its source and drops the note; the recording calls and both tables can then be deleted. Nothing here is shaped to survive that, deliberately.
- Not built: recording the player's own housekeeping, backfill, per-character filtering (`/changes character:…`), and showing GM identity.
