# 0272 - Beings: editing, stats and handing over

Status: accepted, decided with the maintainer on 2026-10-11. Slice of [ADR 0270](0270-beings-app.md); follows [ADR 0271](0271-beings-the-page-and-its-notes.md).

## Context

A being's page only reads until it can change things. The pieces exist: rename ([ADR 0079](0079-account-hub-roster-reuse-and-being-handoff.md)), the description, link name and tags ([ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md), [ADR 0113](0113-inventory-web-slugs-and-player-notes.md)), stat values ([ADR 0263](0263-inventory-web-editing-stat-values.md)), the main picture ([ADR 0237](0237-api-pictures-and-information-order.md)), and creating a character and handing it over, which account-hub's `/beings` page does today (RFC 0014).

## Decision

### Who sees the controls

The editing sections show to someone who runs the table (a GM of a campaign in the library, or an Owner or Organizer) or who plays the being, as in ADR 0271. This is a convenience; every write is the API's to allow, and its message is shown.

### What can be edited, on the being's page

- **Name:** `PATCH .../characters/{id}`. Only a character has this row; a bare being (ADR 0031) has no Name or Hand over section.
- **Description:** the entry's own, in the information form with LorenzoScript and its editor, as on the item page.
- **Picture:** `PUT` or `DELETE .../entities/{id}/picture` (multipart; PNG, JPEG, WebP or GIF, at most 2 MB, checked before it is sent so the person is told before the upload and not after).
- **Link name** (slug): the field with a suggested free one, as ADR 0113 has it; "Another entry already uses the link name" on a 409.
- **Tags** (inherited, on, off) and **stats** (a field per type, "Use inherited" to clear), exactly the behaviour of inventory-web, including the read before a stat write that refuses a value changed since it was seen and the decimal that keeps its point. The stat's source reads "Set on this being".

### Sharing the stat logic

`apps/inventory-web/src/lib/statValues.ts` (reading the definitions, resolving rows, parsing what is typed, writing and clearing a value) is generic over what the entry is. It is extracted into **`packages/stat-values`** (`@lorenzo/stat-values`), a small package that ships TypeScript source like `packages/api-client`: its functions take the app's `LorenzoClient` as their first argument, so each app keeps its own token and address. inventory-web's `lib/statValues.ts` is now a few lines binding the package to its client and re-exporting the rest; its own test file is unchanged and passes, and the package carries the same tests against a stand-in client. `sourceIn(noun, row)` says "Set on this item" or "Set on this being"; `sourceOf(row)` stays what inventory-web called.

The form itself (`StatEditor`, about 190 lines) is **copied, not extracted**: it is bound to the app's template helpers, status line and element hooks, and making it generic would mean a UI package with a template contract, which is more than the second consumer justifies ([ADR 0098](0098-branding-css-app-and-package.md)). The same goes for the tag, link name and information editors, which are near-copies with this app's wording. If a third app wants them, that is the time to extract.

### Creating and handing over

- **New being:** a form at the foot of the list, for those who run the table (a GM of a campaign in the library, or a member). It makes a character with no owner (`POST .../characters` with no `owner_player_id`), which is an NPC, and opens its page. A being is not given a player at creation: that is what the next step is for.
- **Hand over to a player**, on the being's page, for a GM of one or more campaigns in the library: pick one of those campaigns, then one of its players (named as ADR 0176 allows), and **Hand over**. It is the order account-hub uses ([ADR 0079](0079-account-hub-roster-reuse-and-being-handoff.md)): first the being joins the player's roster (`PUT .../characters/{id}/players/{player}`), then the player becomes its owner (`PATCH` with `owner_player_id`). A being linked but not yet owned is recoverable; the reverse is not. Anyone who already plays it keeps playing it. The page then shows the being as a Character with its new owner.
- **Not here:** inviting a new player to a campaign by email (account-hub's user picker does it), handing a being back to nobody, deleting a being, promoting a bare being to a character.
- **account-hub keeps its page.** Where `PUBLIC_BEINGS_BASE_URL` is set in its build, each library on its Beings page also links to the list in Lorenzo Beings; nothing else of the hub changed.

## Consequences

- A GM can create an NPC, describe it, give it a picture, stats and tags, write notes in the four audiences and hand it to a player without leaving one app.
- One implementation of the stat rules serves two apps, and a fix to them lands in both. The price is a fourth package under `packages/` (`pkg:stat-values`) and a thin binding in inventory-web.
- Two screens can now hand a being over; they use the same routes in the same order, so they agree. If the rules change, both need the change.
- A player of a being can edit its description, picture, stats and tags if the API's self-or-managed gate lets them. The page offers the controls and the API says no where it does.
