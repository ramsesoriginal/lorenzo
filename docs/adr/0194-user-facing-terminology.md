# 0194 - User-facing terminology

Status: accepted, decided with the maintainer on 2026-10-07. Extends [ADR 0178](0178-account-hub-repositories.md), which corrected [identity §14.3](../brand/identity.md#143-terminology) for repositories, and [ADR 0170](0170-account-hub-readable-errors-self-service-exits-and-admin-basics.md), which put "library" into the account hub's buttons. The vocabulary was settled before the RFCs for repository tooling (RFC 0036 to RFC 0041) were written, so that the new screens use it from their first line.

## Context

Identity §14.3 defined three words: library, tenant and repository. Everything else people read in Lorenzo grew with the code, and an audit of the account hub, inventory-web, loot-bot, the command line, the API's own messages and the docs found the same ideas under several names, and the code's names reaching people:

- **"Tenant" in front of users.** API notifications ("copy it into your tenant"), error titles ("Tenant not found"), the command line (`lorenzo tenant ...`, "You don't belong to any tenant yet") and one field of loot-bot's `/whoami` all say tenant, where §14.3 says library. "Play tenant" is a third name for a library.
- **Role names.** `owner` and `orga` appear as dropdown values, a column in `lorenzo tenant list` and in a notification; the same people are called admins, administrators, owners and organizers on different screens.
- **Competing words for one idea.** Table, campaign and library; prototype, parent, ancestry and inherit; information, note and description; "Public", "Private", "GM-private", "Players can read this" and "Everyone can read this" for who can see a text; give, hand over, reassign, award, move, drop and take for moving things; container and sack; catalog, base item and item instance.
- **Data-model words.** Entity, slug, being, stat definition and "item instance" appear in screens and messages without a definition, and some API messages quote request flags (`split=true`) to a player in Discord.
- **Raw values.** Notifications show `scope/type`, and the activity log shows raw actions and ids where a name was not known.
- **Words nobody defined.** Pack, stack, bound, equipped, not carried, catalog; and none of the ideas the repository tooling adds (release, public repository, offline).

## Decision

### The vocabulary

The vocabulary is the one now written into [identity §14.3](../brand/identity.md#143-terminology), which is the reference for anything a person reads. In short:

- **People:** library, repository, campaign, People, Owner, Organizer, Author, Admin (an Owner or an Organizer, never a role name), GM (with a title a campaign may set for itself), player, invite link (also usable as a pasted code).
- **Things:** entry (for an entity), kind (for what it is), item, catalog item and inventory item, being, character, group, stat, tag, formula, link name (slug accepted beside it), picture.
- **Text:** description and notes (a note may carry a label); four audiences named GM only, Everyone, Some characters and Player note; "public" only for a public repository and the public catalog.
- **Inheritance:** inherits from, parent and ancestry for an entry; built on for a repository.
- **Carrying and moving:** inventory, equipped, not carried, container, pack, stack, bound, give, hand over, move, set down, assign, take (for loot only), award, confiscate.
- **Repositories:** draft, published, release, public repository, invite a library, libraries using it, copy, update, name clash, check first.
- **Offline:** sync (Bench only), saved on this device, waiting to sync, synced, out of date, conflict.
- **Where things live:** Shelf and Studio (areas of the account hub), Bench ("Lorenzo Bench"), Discover, Log in and Log out, Lorenzo account. "Workshop" is not used. The navigation labels stay descriptive: "Repositories" and "My repositories".

### Rules

- **Product words are not code words.** The user-facing word is used in screens, buttons, errors, notifications, bot messages, command-line output and help, and user-facing documentation. The technical word stays in code, schemas, addresses, flags and developer documentation, and when a technical document crosses over it says so once, as §14.3 already requires.
- **Raw values are never shown.** One mapping turns role values, notification scopes and types, and action names into the words above, and an unknown id is shown as a word ("a removed entry"), never as a UUID.
- **Messages written by the API are product copy.** Notification bodies and problem titles and details reach people through the hub and loot-bot, so they use the vocabulary and do not quote request fields.
- **New screens use these words from the start.** The existing screens, bot, command line and API messages are brought into line by a sweep, one slice for each surface (account-hub, inventory-web, loot-bot, the command line, the API's messages), each its own change; the order is the maintainer's.
- **Names of places.** Shelf, Studio and Bench are written into §3.3 as names of places, not products.

### Not in scope

- **Renaming code, addresses and flags.** Field names, enum values, routes, `?tenant=` in addresses and the command line's command and flag names (`lorenzo tenant ...`, `--tenant`) stay. Their help text and output change; whether the commands themselves get new names (or aliases) is a separate decision.
- **The GM title.** The per-campaign title is a feature of its own, recorded in its own ADR (see RFC 0040); this ADR only reserves the words.
- **Translation.** The words are English; translation is not decided here.

## Consequences

- One word per idea, defined once, in the brand document the other documents already cite.
- The sweep touches every surface that people read, and it removes a few things people may have learned ("Orga", "Admins", "Set up a table", "Hand it over" for a hub hand-off, "item instance"). Each sweep slice names what it changes.
- A new word goes into §14.3 before it goes into a screen. Words for features not built yet are reserved there so that they arrive with one name.
