# 0192 - The placeholder item: the API and the seed

Status: accepted, decided with the maintainer on 2026-10-05.

Slice 2 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md). The "Unsorted item" a library holds for what the catalog does not know, and what a GM needs to sort one: a way to change what an instance is, to list the unsorted ones, and to tell the player. Nothing reads it from a client yet; the importer and the screens are slices 3 to 5.

## Context

A player can make an instance only of a public item ([ADR 0186](0186-player-self-service-enforcement.md)), so something the catalog lacks has nowhere to go ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) Context). Reading the code for this slice showed what was missing: an instance's prototype is written at creation and never again (`PATCH` takes a `name` only); the instance list has no filter by item; the seed has no public item. A fourth thing looked missing and is not: a note a player writes on their own item is invisible to them, since a new non-public note has no knowers, but its author can grant their own character knowledge of it ([ADR 0101](0101-editable-information-and-description-payloads.md)'s edit gate lets an author), so no API change is needed.

## Decision

### The placeholder, in the seed

A node of the `core` layer, **slug `unsorted`, name "Unsorted item"**, with a short public description, and **public**. A node gains an optional `public` (default false) which `lorenzo seed` passes as `in_public_catalog`; every existing node stays as it was. The seed's `version` goes from 2 to 3. A tenant already seeded gets it by running `lorenzo seed` again, which is idempotent, or by taking its repository's update. A tenant whose `unsorted` slug is held by something else is the seed's existing "belongs to something that isn't an item" refusal.

### Changing what an instance is

`PATCH /tenants/{t}/item-instances/{id}` takes a **`prototype_id`**, which replaces the instance's prototype link with that one base item (any item of the tenant, public or not). The name, notes, owner, container and count are untouched.

- **A manager's alone**: a GM of the owner's campaigns, or for an ownerless instance any GM in the tenant; `403` for anyone else, including the player who holds it. A `null`, an unknown id and a non-item are `422 invalid-item-prototype`. The same prototype again is `200` and changes nothing.
- **The activity log** records `item_instance.prototype_changed`, with the new prototype and the one it replaces. (A rename still is not, [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md).)
- **Everything in one transaction**, with the ETag and `If-Match` rules the route already has.

### Listing them

`GET .../item-instances?prototype_id=` lists the instances whose direct prototype is that item, under the list's existing visibility ([ADR 0040](0040-item-instance-read-visibility.md)). "Every unsorted item" is one call.

### Telling the player, twice

A prototype change is told to the instance's holders, as [ADR 0099](0099-player-facing-change-feed.md) tells them any change to it:

- **The change feed** gets one row per instance, of a new kind **`sorted`**, `detail` = `prototype=<the new item's name>`, so a client can say "Your *Hydra Zahn* is now a *Hydra Tooth*". The feed's usual rules apply: the actor is left out, and hidden when a GM.
- **A notification** (scope `tenant`, type `items_sorted`) says "3 of your items have been sorted", one per person. **Sortings that follow one another within ten minutes of the first collapse into it** while it is unread: a GM working down the list, or a bulk action, is one notification per player, with its count raised. The count lives in the title, since a feed row can be read only by its recipient and so not by the GM writing the next one.

`record_change` now returns the rows it wrote, so a caller can act on who was told.

### A writer reads what they wrote by telling their character

Nothing changes in visibility. A note a player writes on their own item is visible to the GM's reach and to nobody else until its author tells their own character, `PUT .../information/{id}/knowers/{character}`, which the author may do. A client that writes a placeholder's description and details does both calls (the importer and "Not in the list", slices 3 and 4). A first attempt made the author always able to read what they wrote; it broke the rule that someone who loses their standing (a demoted GM) stops seeing what they wrote as a GM, and was dropped.

## Not in scope

- The importer, "Not in the list", the badge and the GM's view: slices 3 to 5.
- A bulk prototype change. A GM's view loops over `PATCH`, and a bulk route is added if that proves slow.
- Changing the prototype of an *item*, which `PUT /items/{id}/prototypes` already does.
- Making the placeholder for a tenant that never runs the seed. Import says what to run ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) §4).

## Consequences

- An **API contract extension**, nothing tightened: two new things `PATCH` and the list accept, one new feed kind, one new notification type. A client that does not know `sorted` shows a generic "changed" (loot-bot's `describeChange` already does).
- No migration and no new table, so [ADR 0002](0002-multi-tenancy-shared-schema-rls.md) and [ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md) are untouched.
- The seed's `core` layer now holds two items, and a published `core` repository carries the placeholder to the tenants that copy it.
