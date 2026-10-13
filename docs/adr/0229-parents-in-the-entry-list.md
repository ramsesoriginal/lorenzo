# 0229 - Parents in the entry list

Status: accepted, decided with the maintainer on 2026-10-09. A small addition to [ADR 0215](0215-finding-entries-filters-kinds-and-name-order.md) (the entry list), asked for by slice W-D of [RFC 0042](../rfcs/0042-bench-workbench-interface.md) (the explorer as a tree). The Bench side, the explorer as a tree, is its own ADR (0230).

## Context

`GET /tenants/{t}/entities` lists every entry by name with what it is (`kinds`), and can be narrowed to the children of one entry (`parent_id`). It does not say where an entry comes from. Bench draws the explorer as a tree, one row per place an entry has, and for that it needs every entry's parents. With only the list, that is one read of every entry (the detail has `prototypes`), which for a repository of hundreds of entries is hundreds of requests on every open. The bulk export of RFC 0039 (W3) will answer it for the offline mirror, but it is a larger piece with its own questions, and the explorer should not wait for it.

## Decision

- **Each row of the list carries `parent_ids`**: the entry's direct parents, in id order, empty for an entry with none. They are the same edges as `prototypes` on the detail and as `parent_ids` of `PUT .../parents` ([ADR 0216](0216-parents-for-any-entry.md)).
- **One extra query for the page**, as `kinds` is: the parents of the page's entries are read together (`entity_id = ANY(...)`, as ADR 0215 does), not one query per row. A filtered list names them too, and a parent that is not on the page is still named.
- Nothing else about the list changes: its order, its filters and its paging stay as they were. A caller that ignored the new field is unaffected.
- The generated clients (`packages/api-client`, `apps/cli`) are regenerated.

## Consequences

- A client can draw the whole tree from the paged list, `size` rows per request, without reading any entry.
- The list is somewhat larger on the wire (one array per row). Names and kinds were already per row, and an entry has few parents.
- W3 stays as RFC 0039 describes it; this does not replace it.
