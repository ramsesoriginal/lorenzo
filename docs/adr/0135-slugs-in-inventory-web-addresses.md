# 0135 - inventory-web: slugs wherever an address takes an id

Status: accepted

## Context

inventory-web's addresses name things by id:

- **Every page** has `?tenant=`, the library.
- **The item page** has `?id=`, a catalog item or an instance.
- **The board** has `?character=` or `?group=`, whose board it opens ([ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md), [ADR 0134](0134-board-refinements.md)).

Ids are UUIDs: fine for a link the app makes, hard to type, and meaningless to read. Most of these things have a slug too:

- **A tenant** always has one, unique across Lorenzo ([ADR 0030](0030-tenant-campaign-read-api.md), [ADR 0033](0033-tenant-creation-and-update-api.md)).
- **An entity** can have one, unique within its tenant ([ADR 0107](0107-entity-slugs-and-batch-resolve.md)). That covers items, instances, characters and groups.

Only the item page takes one so far, as `?slug=` ([ADR 0113](0113-inventory-web-slugs-and-player-notes.md)).

## Decision

### Where

Each of those parameters takes a slug as well as an id:

- `?tenant=` on every page.
- `?id=` on the item page. `?slug=` stays, so links already out there keep working.
- `?character=` and `?group=` on the board.

So `/board/?tenant=sunken-vale&character=ashfang` and `/item/?tenant=sunken-vale&id=belt-pouch` work.

The GM's "browse a being" box on the board takes a slug too. It's the one other place where an id is typed in.

### Telling a slug from an id

A value shaped like a UUID is an id. Anything else is a slug. Both slug grammars could, in theory, produce something shaped like a UUID. That slug is read as an id. On the item page, `?slug=` still reaches it.

### Resolving

- **A tenant slug** is looked up among the viewer's own libraries, every page of `GET /tenants`, which is the list the header's switcher shows. No endpoint looks a tenant up by slug, and none is needed: a library the viewer isn't in is a 404 by id as well.
- **An entity slug** is resolved with `GET .../entities/resolve` (ADR 0107), as the item page's `?slug=` already is. What the slug names then goes where its id would have:
  - On the item page, its `kinds` decide between the catalog item and the instance, as for `?slug=`.
  - On the board, it has to be one of your characters or groups, as an id has to be.

A slug is matched exactly, as ADR 0107 matches it. An id costs no extra request.

What doesn't resolve fails the way an unknown id does:

- **A tenant**: "There's no library “…” you can see."
- **An item**: "There's no such item here, or it isn't one you can see."
- **A character or group**: no board opens.

### The address keeps what it was given

A page doesn't rewrite a slug into an id. A link shared by slug stays one, and the item page's Copy link copies it as it is.

What the app writes itself stays ids, because a slug can change and an id can't. That covers links, the switcher, and the board's address after you pick a character. So after picking another character, `?tenant=sunken-vale` stays, next to the new character's id.

### What's remembered is an id

The last library and the last character or group (ADR 0134) are remembered as ids, never as slugs:

- The header's inline script remembers `?tenant=` only when it's an id.
- A slug is remembered as the id it resolves to.

A renamed slug then doesn't strand what was remembered.

## Not in scope

- Links that the app itself builds with slugs.
- Slugs for campaigns, which inventory-web's addresses don't name.
- Forbidding slugs shaped like a UUID, in the API.

## Consequences

- Hand-written and shared addresses can be readable: `?tenant=sunken-vale&character=ashfang`.
- A slug costs one request before the page loads. For a tenant, that's the viewer's library list.
- A bookmark by slug breaks when the slug changes. A bookmark by id doesn't.
- No API change.
