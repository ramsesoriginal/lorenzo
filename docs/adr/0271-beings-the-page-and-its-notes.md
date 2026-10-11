# 0271 - Beings: the list, a page for each being, and notes

Status: accepted, decided with the maintainer on 2026-10-11. Slice of [ADR 0270](0270-beings-app.md).

## Context

The API can already answer everything a being's page needs, in pieces: the entry with its effective stats and information ([ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md)), the character row with its players ([ADR 0031](0031-character-table-and-read-api.md), [ADR 0036](0036-user-player-character-crud-api.md)), the list of beings ([ADR 0078](0078-being-listing-and-search-endpoint.md), amended by [ADR 0173](0173-a-gm-lists-the-beings-they-can-see.md)), what a character owns ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)), information with readers ([ADR 0038](0038-information-payload-knowledge-crud-api.md), [ADR 0109](0109-player-knowers-knower-listing-and-information-list.md)) and its order ([ADR 0237](0237-api-pictures-and-information-order.md)). inventory-web has players' notes on items ([ADR 0113](0113-inventory-web-slugs-and-player-notes.md)) with an "Everyone can read this" box; [ADR 0194](0194-user-facing-terminology.md) since named four audiences for any text.

## Decision

### The list

- **What is listed is what the API lists.** An Owner or Organizer of the library, or a GM, gets `GET .../beings` (ADR 0173); anyone else gets the library's characters, which any participant may list (inventory-web's give search does the same, ADR 0078). A refusal (404 or 403) is the fall back; any other error is shown.
- **A search and three filters, in the browser over the whole list:** the name, **Kind** (characters, which a player plays, or NPCs: every other being, a bare one included), **Campaign** (the characters on the roster of one of the library's campaigns, from `GET .../campaigns/{id}/players`) and **Mine** (`GET .../characters?mine=true`, [ADR 0049](0049-list-characters-mine-filter.md)). The filters are in the address (`?q=&kind=&campaign=&mine=1`), so a filtered list can be shared and survives Back. Each row says its kind and marks the viewer's own.
- Without a campaign list the campaign filter is hidden; the list needs no more of the viewer than a participant is.

### The page

One page per being, `/being/?tenant=&slug=` (or `&id=`). After it loads, the address names the being by its link name if it has one, whichever way it was reached. It shows, top to bottom and in one column:

1. its **name**, its **kind** (Character or NPC) and its **link name**;
2. its **picture** (the entry's main picture, fetched with the viewer's token, [ADR 0108](0108-lorenzoscript-in-inventory-web.md)), its **description** rendered as LorenzoScript with the shared package (links to beings open their pages here; links to items open inventory-web's item page if it is configured, else are plain text), its **tags** and the **stats** it has, its own or inherited;
3. **Played by:** the owner first, then the others who share it, each with the campaign and "You" where it is the viewer. Names come from the campaign rosters ([ADR 0176](0176-a-campaigns-people-come-with-their-names.md)) where the viewer may read them, else "A player". A being no one plays says so;
4. **Inventory:** how many things it owns, the first few by name and a link to its board in inventory-web (`PUBLIC_INVENTORY_WEB_BASE_URL`; left out without it). It uses the existing `owned-by` read, and says so when the viewer may not read it;
5. **Notes**;
6. for those who may, the editing sections ([ADR 0272](0272-beings-editing-stats-and-handing-over.md)).

A being that cannot be found, is not a being, or is not visible to the viewer gets one sentence ("There's no such being here, or it isn't one you can see.") and not a half-drawn page. Not signed in, an incomplete link and an unknown library each have their sentence too.

### Notes

A note is information of type `note`, whose text is LorenzoScript. The page lists every note the viewer can see, in the order the information has, with a label (default "Note"; a note may carry one, [ADR 0194](0194-user-facing-terminology.md)) and its audience.

- **Four audiences**, as the radio buttons of the note's form, each with one line saying what it means:
  - **GM only** (`is_public` false, no one told): the campaign's GMs and the library's Owners and Organizers.
  - **Everyone** (`is_public` true): anyone with access to the library.
  - **Some characters** (`is_public` false and the characters chosen are told, `PUT .../knowers/{character}`): the GMs and the characters chosen.
  - **Player note** (`is_public` false and the being itself is told): the GMs and the being's players. This is the rule of ADR 0113 for a private note on an item the viewer's character owns, and what loot-bot's `/note` makes.
- **How an audience is stored and read back.** Public is `is_public`. Otherwise it is read from the note's knowers, which only those who may grant it may list ([ADR 0109](0109-player-knowers-knower-listing-and-information-list.md)): none is GM only; the being alone is a Player note; anything else is Some characters. A reader who cannot list them sees "Shared with you" and cannot change the audience, though they may still edit the text if the API lets them. A change of audience is a plan (set `is_public`, add the knowers missing, remove the ones not wanted), applied after the note is saved; if the second step fails, the page says the text was saved but the audience was not. A new note whose knowers cannot be set is deleted again, as in ADR 0113, so no one writes something they cannot read.
- **Who is offered what.** Someone who runs the table (a GM of a campaign in the library, or a member of it) is offered all four, GM only first. A player of the being is offered Player note (first) and Everyone. Private is the default in both cases. This is a convenience: the API decides every write, and its refusal is shown.
- **Add, edit, delete** use ADR 0101's writes with `If-Match` (a stale edit says so). Edit and Delete show wherever Add does.
- **Reorder** with up and down buttons. The order route wants every row the viewer can see, not only notes, so the page reads them all and puts the notes into the places notes held; the descriptions and pictures keep their slots. A concurrent change shows up as the API's 409.
- A player of another being sees the notes shared with them and no controls.

## Consequences

- The four audiences of identity §14.3 exist in a screen for the first time, as a mapping over `is_public` and knowers that needs no API change. If the API gains an authorship field on information, "Player note" can mean "written by a player" instead of "told to the being"; until then it names the way ADR 0113 and loot-bot already shared a player's note.
- A GM sees every note, as everywhere; the page does not hide any from them.
- The list is only as long as one request per page of 100; a library with thousands of beings would want a server-side search, which `?q=` already allows. Not needed yet.
- The "Campaign" filter costs one request for the first campaign chosen, and is kept.
