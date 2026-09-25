# 0116 - Players read catalog items, and browse a public catalog

Status: accepted

## Context

[ADR 0032](0032-item-and-item-instance-crud-api.md) opened item-instance reads to every tenant participant but left the catalog at `get_tenant_context`. Only members, meaning owners and orgas, can read a catalog item. Players hold a seat in a campaign, not a membership, so they can't open one.

That line no longer holds together:

- Since [ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md), a player's instance shows its prototypes' descriptions, labelled "From Spellbook".
- `GET .../entities/{id}` already gives any participant a prototype's name.
- The catalog item's own page is the missing piece. inventory-web had to show "From Spellbook" to players as plain text rather than a link that fails ([ADR 0114](0114-inventory-web-end-to-end-tests.md)).

Browsing is a different question. A catalog holds things nobody has found yet, and a list would name them. Some items are just common things, though, such as a plain robe or a generic backpack. A GM would happily let players look those up.

## Decision

The maintainer chose single items for every participant, plus a public catalog that the GM curates.

### Any participant reads a catalog item

`GET .../items/{id}` and `GET .../items/{id}/prototypes/ancestry` move from `get_tenant_context` to `get_tenant_or_404` plus `require_tenant_participant`. That is the shape ADR 0032 already gave instance reads.

What a reader sees of an item's information stays filtered per reader, as everywhere. The catalog's writes keep needing a membership.

### A public catalog

- **The flag.** `item` gains `in_public_catalog`, a boolean that is `NOT NULL DEFAULT false`. `ItemOut` shows it, and `ItemCreate` and `ItemUpdate` accept it. `ItemInstanceOut` doesn't carry it: it's a catalog item's own property.
- **Listing.** `GET .../items`, with its search and prototype filters, lists every item to a member, as now. Any other participant sees only the items in the public catalog.
- **No inheritance.** An item built on a public one isn't public itself. The GM decides item by item.

### inventory-web

- **Catalog pages for players.** Players open catalog item pages, so "From Spellbook" is a link for them again. "Used as a prototype by" lists what the viewer may list.
- **Browsing.** `/items` for someone who isn't a GM here is the catalog they may browse: the public catalog, searchable, read-only, each row linking to its page. The board links it as "Catalog"; GMs keep "Manage items (GM)".
- **Curating.** GMs tick **In the public catalog** in Manage items' create form and edit panel.

## Consequences

- A player can open any catalog item whose id they come across. What its page shows is only what its information's visibility allows them.
- A GM chooses what players can browse, item by item.
- One migration adds a column to `item` and nothing else. The item views are untouched; the API reads the flag from the item row.
