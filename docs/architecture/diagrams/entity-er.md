# ER diagram: entity (sub-slice 1)

```mermaid
erDiagram
    ENTITY {
        uuid id PK
        uuid tenant_id "no FK yet - tenant lives on feat/auth-users"
        string name "internal/reference name, not in-fiction text"
        timestamptz created_at
        timestamptz updated_at
    }
```

Deliberately just one table — concrete types (`item`, `being`, `place`), prototypes, stats, information/knowledge, and containment each get their own sub-slice and their own diagram update, per [ADR 0012](../../adr/0012-entity-table.md).
