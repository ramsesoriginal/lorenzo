# Client views

The backend is meant to hold the full complexity described in the rest of `docs/domain/`. Nothing that uses the API is meant to expose all of it at once — every client is a **narrower, audience-specific slice**.

## The clients

Each kind of client shows one slice for one audience; [apps/README.md](../../apps/README.md) lists every app.

- **Players** see what they have and where they have it — stats and notes, but only the ones the GM chose to make visible to them (see [visibility](entities-knowledge-and-visibility.md)). They do so in a Discord bot, in Android and iOS apps that keep an offline copy of an inventory, and on the web.
- **The GM** gets web views across every player and their possessions, including secret notes and stats players never see. "GM" is the game master, whatever a table calls them: a campaign may name its own ([ADR 0294](../adr/0294-the-gms-title-per-campaign.md), "Storyteller", "DM", "Narrator"), and the apps say that name wherever one campaign is in play.
- **Everyone in a library** has an account hub for their own profile, libraries, campaigns and notifications, and one app each for the kinds of thing they work on: beings, calendars and clocks, Sessions and Scenes, Locations and Maps, and manuscripts (see [kinds](kinds.md)).
- **Authors** of a repository work in a workbench, Bench, that edits its entries, texts and stats; a command line does the same for scripts and for importing item data.

## Why this matters for app boundaries

This is part of why [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md) allows many apps of the same "kind" rather than one do-everything web app: a GM-facing console and a player-facing companion app are legitimately different tools with different audiences, even though they're both "web frontends" for the same underlying data.

## Future direction (not being built yet)

The inventory-manager idea was described as a possible first step toward something bigger: connecting inventory to **events** (past, present, predicted future), and a **ledger of ownership** — tracking ownership provenance over time, not just current possession. Events now exist as their own kind, but nothing ties them to inventory, and ownership is still only the current holder. This is deliberately not scoped yet; it's recorded here so it doesn't get lost, not as a commitment to build it next.
