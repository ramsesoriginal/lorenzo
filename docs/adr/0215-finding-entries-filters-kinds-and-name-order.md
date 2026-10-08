# 0215 - Finding entries: filters, kinds and name order

Status: accepted, decided with the maintainer on 2026-10-08. Slice K5 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md), tracked in #551. Builds on [ADR 0047](0047-item-catalog-search-and-container-convention.md) and [ADR 0073](0073-item-prototype-graph-inspection-and-bulk-editing.md), whose filters it gives to every entry; needed by K7 (the bulk effective-stat read) and by the editors that list entries ([RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md)).

## Context

`GET /tenants/{id}/entities` lists every entry of a library, ordered by name, with nothing to narrow it by and nothing to say what each row is: a client that wants "the beings" or "what is under Weapon" fetches everything, then asks `GET /entities/resolve` or the entry itself once for each. `GET /items` and `GET /beings` have `q`, and `GET /items` has `prototype_id` and `recursive`, but both are ordered by id, which is stable and means nothing to a person; a catalog of three hundred items in id order cannot be browsed. [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §5 proposes the shape; this slice builds it and settles the names and the ordering rule.

## Decision

### `GET /tenants/{id}/entities`

Four optional query parameters, all of which combine (an entry must pass every one given):

| Parameter | Meaning |
| --- | --- |
| `q` | A substring of the entry's name, case-insensitive. `%` and `_` in it are letters, not wildcards. |
| `kind` | Repeatable: `item`, `item_instance`, `being`, `character`. An entry matches if it has **any** of the kinds given, and is listed once. Another value is a `422`. |
| `parent_id` | Only entries that have this entry as a parent: the `prototype` edge, direct. An id that is not an entry of the library, or is another library's, is a `404`, as `prototype_id` is on `GET /items`. |
| `recursive` | With `parent_id`, every descendant, not just the direct children. Without `parent_id` it changes nothing. |

The names are the ones the neighbouring lists already use (`q`, `recursive`), and `parent_id` is RFC 0041's word for the API's `prototype`, so a client filtering `GET /items` by `prototype_id` and `GET /entities` by `parent_id` means one thing by both. `kind` takes the four values `GET /entities/resolve` already reports; the RFC's `kinds` field on a *new* entry is `item` and `being` only, but a list may be asked for the others, and "the characters" is a question a hub asks.

The rows are `EntityListOut`: the `EntitySummary` fields (`id`, `name`, `quantity`, which is null here) and **`kinds`**, a list in the order `item`, `item_instance`, `being`, `character`, empty for an entry with no kind (a group, a category node). It is read for the whole page in one query over the four marker tables, not one query for each entry. The order stays by name, then id, and the gate is unchanged: every participant of the library lists every entry name ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) Open questions keeps whether it should be narrower).

**`q` is escaped here and not on the two older lists.** `GET /items` and `GET /beings` pass `q` to `ILIKE` as it is, so a `%` in it matches anything. That is old and harmless for a person typing a word, and is left alone: it is not what this slice is about. A new filter that took the same shortcut would be a second place to fix.

### `GET /items` and `GET /beings`: by name, then id

Both are ordered by the entry's `name`, then `entity_id`, as `GET /entities` is. The id breaks ties, so two entries with the same name keep a fixed order and a page never repeats or skips a row. The comparison is the database's, the same as the one `GET /entities` already uses, so the three lists agree. Their filters, their gates (the public catalog for a player; a GM's reach for beings) and their pages are unchanged; only the order is.

### Reused, not copied

The walk that finds every descendant of a prototype moved from `routers/items.py` to `entity_access.py` as `prototype_descendants_cte`, next to the containment walks it resembles, because two routers now use it. Its behaviour is the same.

## Not in scope

- A filter for an entry with no kind, and an "all of" form of `kind`: RFC 0041 adds one only if a client asks.
- `kinds` on `GET /items` and `GET /beings`: their rows are what an item or a being is, not a mixed list.
- Effective stat values in a list, and the filters on a bulk read: K7.
- Who sees which entries ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) Open questions).
- Escaping `q` on `GET /items` and `GET /beings`.

## Consequences

- A client lists a library's beings, or everything under a category, or the items whose name contains a word, in one request, and knows what each row is without asking again.
- **A visible change to two lists:** `GET /items` and `GET /beings` come back in name order instead of id order. A client that relied on the id order gets another one; nothing in this repository did.
- `GET /entities` answers with a new schema, `EntityListOut`, a superset of the old rows; the response of an unfiltered call has the same rows in the same order plus `kinds`. The generated clients take it; the check for breaking changes finds none.
- A request for `parent_id` loads one entry first, so an unknown parent is a `404` and not an empty page, which is how a client learns its id is wrong.
