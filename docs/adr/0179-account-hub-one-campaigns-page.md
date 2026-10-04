# 0179 - account-hub: one `/campaigns` page for the GM and character overviews

Status: accepted, decided with the maintainer on 2026-10-04. Builds on [ADR 0176](0176-a-campaigns-people-come-with-their-names.md) (names) and [ADR 0178](0178-account-hub-repositories.md) (libraries only). It is the v1.0 row "GM and character overviews".

## Context

Two pages answer "where am I, and as what?":

- **`/overview`** ("Your access, everywhere", [ADR 0087](0087-account-hub-pictures-unread-badge-and-access-overview.md)): read-only; each library with your role, and the campaigns in it you play or GM.
- **`/characters`**: your seats, by library and campaign, with the actions that belong to a seat: use one of your characters from another campaign, stop using one here, leave the campaign.

Neither is for someone who *runs* a table, and a person who plays in one campaign and GMs another uses both. `GET /me/managed` ([ADR 0086](0086-managed-scope-aggregate-and-notifications-since-filter.md)) was built for a cross-library "what do I run?" screen and has never been used by account-hub.

## Decision

**One page, `/campaigns`, "Your campaigns", replaces `/overview` and `/characters`.** The old addresses stay and send people on to it, so bookmarks do (Astro's `redirects` option, which a static build turns into pages that forward).

### What it shows

Two sections, drawn from `GET /me` and `GET /me/managed`, for libraries only ([ADR 0178](0178-account-hub-repositories.md)):

- **Where you play.** The campaigns where you hold a seat, with your characters there, and **the actions `/characters` has today**, unchanged: use an existing character, stop using one here (never an owner's own link, [ADR 0170](0170-account-hub-readable-errors-self-service-exits-and-admin-basics.md)), leave the campaign.
- **Where you run.** The campaigns you GM, and every campaign of a library you administer (`is_gm` false for those, shown as "Admin"). Each lists **its players, by name, and the characters each plays**, and its GMs, from `GET .../players` and `GET .../gms`, which carry names since [ADR 0176](0176-a-campaigns-people-come-with-their-names.md). Each links to its administration on `/tenants`.

A campaign you both play and run appears in both. A row names the campaign, then its library, then your role as a badge, the library's role being what `/overview` showed.

### The rest

- **Home and the navigation** link "Your campaigns" in place of the two entries.
- **A person with nothing to show** sees a sentence and, if `capabilities.create_tenant` ([ADR 0175](0175-me-says-what-you-may-create.md)), a link to `/setup` ([ADR 0180](0180-account-hub-one-click-setup.md)).
- **No new API call beyond ADR 0176's fields.** The page reads what a GM could already read; the characters list and its gate are unchanged.

## Alternatives considered

- **Keep both pages and add a GM page.** Three pages for one question, and a campaign you play and run would be in two of them.
- **Fold the seat actions into `/tenants`.** `/tenants` is the administration page; "your seat in a campaign" is play, and a player who administers nothing would have to find it there.
- **Redirect nothing.** Notifications, bookmarks and the previous release's home page all link the old addresses.

## Not in scope

- A GM's notes, a knowledge overview, anything about a character's sheet or inventory: the GM-console row of v1.0.
- Players' names for people with no standing in a campaign: they do not see it, as today.

## Consequences

- **Client-only.** `characters.astro` and `overview.astro` become redirects; their code moves into one page and a small module per section, with the pure parts (which campaigns go in which section, the role badge) unit-tested.
- The real-browser specs that cover `/characters` and `/overview` move to `/campaigns`, and gain a GM with only a campaign grant seeing a player by name.
- `GET /me/managed` gets its first client.
