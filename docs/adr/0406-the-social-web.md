# 0406 - The SocialWeb: a saved view of relationships

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slice 8. In the shape of the Map ([ADR 0336](0336-maps-the-kind-its-system-and-its-placements.md)) and
[ADR 0351](0351-writing-placements-in-bulk.md).

## Context

A drawing of a court or a family is worth keeping and sharing: which entries, which relationship types, how they are
placed, how they look. Per-viewer server storage does not exist, and a view meant for players has to be content that
travels through copy and release. The name leaves room for other views of the social data later.

## Decision

A SocialWeb is an entry of kind `social_web` that may be another kind as well. It says what it shows, not what is true.

```sql
social_web(entity_id PK, tenant_id NOT NULL, layout text NOT NULL, layout_seed integer NOT NULL,
  theme_hint text NULL, view jsonb NULL, standing_stat_id NULL, as_of_event NULL)
social_web_entry(web_entity_id, entry_entity_id, x numeric NULL, y numeric NULL,
  PRIMARY KEY (tenant_id, web_entity_id, entry_entity_id))
social_web_type(web_entity_id, type_entity_id, PRIMARY KEY (tenant_id, web_entity_id, type_entity_id))
```

- **A web shows exactly the entries that have a row**, at most 500 and at most 50 types (*proposed default*). No rule
  is expanded by the server: "add this group's members" and "add everyone within two steps" are editor actions that
  write explicit rows. The ad hoc form of the same selections is the address of the page, unsaved.
- **Edges** are the visible relationships whose two ends are members, limited to the web's types when it names any.
  A relationship that no reader may see is not an edge for them.
- **`layout`** is a name from the closed list in code ([ADR 0407](0407-the-graph-renderer.md)); `x` and `y` are both set or
  both null and are hand placement, used by `manual` and as pins by the others. `theme_hint` is a theme name from code;
  the viewer's choice beats the web's, which beats the default. `view` holds visual-only switches (labels, hulls) and
  never an entry id or a value the server reads. `standing_stat_id` and `as_of_event` are the matrix's standing and
  the date lens when saved.
- **Reader-scoped.** A reader sees a member only if they may see the entry, a row of a hidden entry leaves no mark, gap
  or count, and the layout is computed over what that reader sees, so a hidden member moves no one. Two readers can see
  different drawings of one web.
- **Audience** is the entry's own (restricted unless public, ADR 0404). A web gives no access to anything it names.
- **Writes** are by those who write relationships (ADR 0404); a bulk write of members and positions in one transaction
  takes at most 100 rows. A web is created, renamed and deleted as an entry.
- **Repository**: three content tables, registry lines and the format bump; a copy drops a member whose entry was not
  copied and reports it.

## Validation and delivery

Tests: the round trip and validation (both coordinates or none, the closed layout list, the member cap); a hidden
member absent from a reader's read and moving no byte of another member's position; a relationship edge between a
visible and a hidden member absent; the bulk write; copy and release; the older reader; that no reach code reads a web.

## Excluded

A rule the server expands, a stored per-viewer view, an entry id inside `view`, edges for entries that are not members,
and a web of webs.
