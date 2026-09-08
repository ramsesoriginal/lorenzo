# ER diagram: entity (sub-slice 1)

```mermaid
erDiagram
    TENANT ||--o{ ENTITY : scopes
    TENANT {
        uuid id PK
    }
    ENTITY {
        uuid id PK
        uuid tenant_id FK
        string name "internal/reference name, not in-fiction text"
        timestamptz created_at
        timestamptz updated_at
    }
```

`tenant` is [ADR 0013](../../adr/0013-tenant-table-bootstrap.md)'s minimal bootstrap, shown here only for the FK. Otherwise deliberately just one table — concrete types (`item`, `being`, `place`), prototypes, stats, information/knowledge, and containment each get their own sub-slice and their own diagram update, per [ADR 0012](../../adr/0012-entity-table.md).
