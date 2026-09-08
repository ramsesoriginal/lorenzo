# ER diagram: stats (sub-slice 3)

```mermaid
erDiagram
    TENANT ||--o{ ENTITY : scopes
    TENANT ||--o{ STAT_GROUP : scopes
    TENANT ||--o{ STAT_DEFINITION : scopes
    STAT_GROUP ||--o{ STAT_DEFINITION : clusters
    ENTITY }o--o{ STAT_GROUP : acquires
    ENTITY ||--o{ ENTITY_STAT : has
    STAT_DEFINITION ||--o{ ENTITY_STAT : "valued by"

    TENANT {
        uuid id PK
    }
    ENTITY {
        uuid id PK
        uuid tenant_id FK
    }
    STAT_GROUP {
        uuid id PK
        uuid tenant_id FK
        string name
        int priority "inheritance tie-break, unused until entity_prototype exists"
    }
    STAT_DEFINITION {
        uuid id PK
        uuid tenant_id FK
        uuid stat_group_id FK
        string name
        enum value_type "int | text | float | bool"
    }
    ENTITY_STAT {
        uuid entity_id PK_FK
        uuid stat_definition_id PK_FK
        uuid tenant_id FK
        int value_int "exactly one of these four set"
        string value_text
        float value_float
        boolean value_bool
    }
```

`ENTITY }o--o{ STAT_GROUP` is the n:m relation — realized as `entity_stat_group(entity_id, stat_group_id)`, a pure join table with no attributes of its own, not shown as its own box here. See [ADR 0014](../../adr/0014-stats.md) — no resolution/inheritance walk yet, this is direct group membership and direct values only.
