# ER diagram: information and payloads (sub-slice 6)

```mermaid
erDiagram
    TENANT ||--o{ ENTITY : scopes
    ENTITY ||--o{ INFORMATION : "described by"
    INFORMATION ||--o{ PAYLOAD : bundles
    PAYLOAD ||--o| PAYLOAD_DESCRIPTION : "is a"
    PAYLOAD ||--o| PAYLOAD_NUMBER : "is a"
    PAYLOAD ||--o| PAYLOAD_PICTURE : "is a"
    PAYLOAD ||--o| PAYLOAD_DOCUMENT : "is a"

    TENANT {
        uuid id PK
    }
    ENTITY {
        uuid id PK
        uuid tenant_id FK
    }
    INFORMATION {
        uuid id PK
        uuid tenant_id FK
        uuid entity_id FK
        text title
        text type
    }
    PAYLOAD {
        uuid id PK
        uuid tenant_id FK
        uuid information_id FK
    }
    PAYLOAD_DESCRIPTION {
        uuid payload_id PK,FK
        uuid tenant_id FK
        text locale
        text content
    }
    PAYLOAD_NUMBER {
        uuid payload_id PK,FK
        uuid tenant_id FK
        numeric value
    }
    PAYLOAD_PICTURE {
        uuid payload_id PK,FK
        uuid tenant_id FK
        bytea data
        text file_type
    }
    PAYLOAD_DOCUMENT {
        uuid payload_id PK,FK
        uuid tenant_id FK
        bytea data
        text filename
    }
```

`payload` has no `kind` column, matching `entity`'s own class-table-inheritance pattern: which of the four concrete tables has a row with a given `payload_id` tells you what kind it is. Unlike `entity`, a payload should conceptually be exactly one kind - nothing enforces that yet. See [ADR 0017](../../adr/0017-information-and-payloads.md): `UNIQUE(entity_id, type)` on `information` isn't drawn here since mermaid's ER notation has no composite-unique-constraint marker distinct from the relationship lines above.
