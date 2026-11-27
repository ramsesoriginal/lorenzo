# 0529 - An outer audience on a being

Status: accepted and built, 2026-11-27, asked for by the maintainer as slice A1 of UI-H's API work ([ADR 0528](0528-ui-h-retiring-the-old-frame-and-auditing-the-apps.md), H3). It gives a being what a Fact, a calendar entry or a Location already have: a say over who sees it, so the Beings page can show and set "Seen by" ([ADR 0422](0422-beings-redesign.md), BN6; left out of [ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md) because the API could not say it).

## Context

The outer audience (`entity_audience`, with named recipients in `entity_knowledge`, [ADR 0305](0305-facts-and-entry-audiences.md)) is read and written by `GET` and `PUT /tenants/{t}/entities/{id}/audience`, for the kinds that have one. A being is not among them: it has no audience row, so every participant who can read the tenant reads every being, and the beings list, the sheet and the characters list know nothing of a gate. The Beings design shows "Seen by", one of Everyone or GM only, on a being's page.

## Decision

- **The audience routes accept a being.** A being with no row reads as open to all (`is_public: true`), as a Location made from an existing entry does ([ADR 0330](0330-locations-the-kind-and-the-part-of-tree.md)): nothing that exists changes. Unlike the Location, a read does not make the row. The row is made by the first write that says otherwise, in the same request that sets the audience, and until then the `ETag` is the entry's own, so the `If-Match` a client read is the one the write checks. A repeated read of an untouched being gives the same `ETag`.
- **Who may change it** is who may write the being (`authorize_entity_write`), as for the other kinds. A reader who may not gets what they got before: nothing.
- **The gate is applied where a being is read by its own routes**, which did not ask before: `GET …/beings` (the list), `GET …/beings/{id}/sheet`, `GET …/characters` and `GET …/characters/{id}`. The generic entry reads (`GET …/entities/{id}`, its stat changes, search) already ask the gate. A being someone has restricted is absent for a reader outside its audience: 404, and not counted in a list.
- **A player's own characters are always theirs to see.** The characters a player owns or pilots are in the reader's own entries, so a GM who restricts a character does not hide it from its player. This is the one change to who sees what outside a being that someone has restricted: the set `own_entry_ids` of the reader's visibility now holds those characters, which the gate reads and nothing else does.
- **Not decided here:** a "GM only" being's items, notes and relationships. They follow their own audiences, as before; hiding a being hides its page and its place in lists, not what other entries say about it.

## Consequences

- No migration and no new route: the `OpenAPI` document is unchanged apart from the message of one refusal (an outer audience is "available for facts, calendar entries and beings").
- The Beings page can read and set "Seen by" with the existing routes (H4), and a being restricted to the GM disappears from a player's lists and links at once.
- A being with no row costs nothing; a restricted one is one `entity_audience` row, and the list queries gain one `NOT EXISTS`.
- Tests: `tests/test_being_audience.py` (an open start with a stable `ETag`; restricting hides the being from a player's list, character, sheet, entry and stat changes; the GM and the owner keep it; naming the player and reopening bring it back).
