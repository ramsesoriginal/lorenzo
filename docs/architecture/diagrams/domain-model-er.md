# ER diagram: domain model

A snapshot of the stored API tables, checked against [`models/`](../../../apps/api/src/lorenzo_api/models) on 2026-10-15. The diagrams are grouped to keep the entry/component core, stat vocabulary, information, accounts and repository machinery readable. A table referenced from another group appears there by name only; its columns are defined in its own group.

Columns show primary and foreign keys and nullable values. Routine `created_at`/`updated_at` and `created_by`/`updated_by` columns and their attribution edges are omitted; timestamps and attribution differ by table, so consult the model and [ADR 0029](../../adr/0029-attribution-created-by-updated-by.md) for their exact shape. Views (`v_item`, `v_item_instance`, `v_character`, `v_effective_stat`) are reads over these tables, not stored tables.

Relationship lines are foreign-key references: dotted lines do not claim a cascade or ownership rule. A same-tenant composite foreign key is drawn once by its non-tenant column; every tenant table still carries `tenant_id` and enforced RLS. Unique constraints, checks, trigger rules and delete actions are defined in the migrations and the [ADR index](../../adr/README.md), not reproduced here.

## Entries, inheritance, containment and ownership

```mermaid
erDiagram
    ENTITY ||..o{ BEING : "entity_id"
    BEING ||..o{ CHARACTER : "entity_id"
    PLAYER |o..o{ CHARACTER : "owner_player_id"
    ENTITY ||..o{ CONTAINMENT : "child_entity_id"
    ENTITY ||..o{ CONTAINMENT : "parent_entity_id"
    ENTITY ||..o{ ENTITY_PROTOTYPE : "entity_id"
    ENTITY ||..o{ ENTITY_PROTOTYPE : "prototype_id"
    ENTITY ||..o{ ENTITY_SLUG : "entity_id"
    ENTITY ||..o{ ENTITY_STAT_GROUP : "entity_id"
    STAT_GROUP ||..o{ ENTITY_STAT_GROUP : "stat_group_id"
    CHARACTER ||..o{ GROUP_MEMBER : "character_entity_id"
    ENTITY ||..o{ GROUP_MEMBER : "group_entity_id"
    ENTITY ||..o{ ITEM : "entity_id"
    ENTITY ||..o{ ITEM_INSTANCE : "entity_id"
    ENTITY ||..o{ OWNERSHIP : "owned_entity_id"
    ENTITY ||..o{ OWNERSHIP : "owner_character_id"
    BEING {
        uuid entity_id PK,FK
        uuid tenant_id FK
    }
    CHARACTER {
        uuid entity_id PK,FK
        uuid tenant_id FK
        uuid owner_player_id FK "nullable"
    }
    CONTAINMENT {
        uuid child_entity_id PK,FK
        uuid parent_entity_id FK
        uuid tenant_id FK
        int quantity
    }
    ENTITY {
        uuid id PK
        uuid tenant_id FK
        string name
    }
    ENTITY_PROTOTYPE {
        uuid entity_id PK,FK
        uuid prototype_id PK,FK
        uuid tenant_id FK
        int position
    }
    ENTITY_SLUG {
        uuid entity_id PK,FK
        uuid tenant_id FK
        string slug
    }
    ENTITY_STAT_GROUP {
        uuid entity_id PK,FK
        uuid stat_group_id PK,FK
        uuid tenant_id FK
    }
    GROUP_MEMBER {
        uuid group_entity_id PK,FK
        uuid character_entity_id PK,FK
        uuid tenant_id FK
    }
    ITEM {
        uuid entity_id PK,FK
        uuid tenant_id FK
        boolean in_public_catalog
    }
    ITEM_INSTANCE {
        uuid entity_id PK,FK
        uuid tenant_id FK
    }
    OWNERSHIP {
        uuid owned_entity_id PK,FK
        uuid owner_character_id FK
        uuid tenant_id FK
    }
```

## Stat vocabulary and formulas

```mermaid
erDiagram
    ENTITY ||..o{ COMPUTED_STAT : "entity_id"
    STAT_DEFINITION ||..o{ COMPUTED_STAT : "stat_definition_id"
    STAT_DEFINITION ||..o{ COMPUTED_STAT_COMPARISON : "left_stat_definition_id"
    STAT_DEFINITION |o..o{ COMPUTED_STAT_COMPARISON : "right_stat_definition_id"
    STAT_DEFINITION ||..o{ COMPUTED_STAT_CONTENTS : "source_stat_definition_id"
    STAT_DEFINITION ||..o{ COMPUTED_STAT_LINEAR : "source_stat_definition_id"
    COMPUTED_STAT_SUM ||..o{ COMPUTED_STAT_SUM_TERM : "entity_id"
    STAT_DEFINITION ||..o{ COMPUTED_STAT_SUM_TERM : "source_stat_definition_id"
    COMPUTED_STAT_SUM ||..o{ COMPUTED_STAT_SUM_TERM : "stat_definition_id"
    ENTITY ||..o{ ENTITY_STAT : "entity_id"
    STAT_DEFINITION ||..o{ ENTITY_STAT : "stat_definition_id"
    STAT_DEFINITION |o..o{ STAT_DEFINITION : "max_hint_id"
    STAT_DEFINITION |o..o{ STAT_DEFINITION : "min_hint_id"
    STAT_DEFINITION |o..o{ STAT_DEFINITION : "resolved_hint_id"
    STAT_GROUP ||..o{ STAT_DEFINITION : "stat_group_id"
    STAT_DEFINITION ||..o{ STAT_DEFINITION_ENUM_VALUE : "stat_definition_id"
    COMPUTED_STAT {
        uuid entity_id PK,FK
        uuid stat_definition_id PK,FK
        uuid tenant_id FK
    }
    COMPUTED_STAT_COMPARISON {
        uuid entity_id PK
        uuid stat_definition_id PK
        uuid tenant_id FK
        uuid left_stat_definition_id FK
        string comparator
        uuid right_stat_definition_id FK "nullable"
        string right_constant "nullable"
        string true_value "nullable"
        string false_value "nullable"
    }
    COMPUTED_STAT_CONTENTS {
        uuid entity_id PK
        uuid stat_definition_id PK
        uuid tenant_id FK
        uuid source_stat_definition_id FK
    }
    COMPUTED_STAT_LINEAR {
        uuid entity_id PK
        uuid stat_definition_id PK
        uuid tenant_id FK
        uuid source_stat_definition_id FK
        string multiplier
        string offset
        string round_mode
    }
    COMPUTED_STAT_SUM {
        uuid entity_id PK
        uuid stat_definition_id PK
        uuid tenant_id FK
        string offset
        string round_mode
    }
    COMPUTED_STAT_SUM_TERM {
        uuid entity_id PK,FK
        uuid stat_definition_id PK,FK
        uuid source_stat_definition_id PK,FK
        uuid tenant_id FK
        string coefficient
        int position
    }
    ENTITY_STAT {
        uuid entity_id PK,FK
        uuid stat_definition_id PK,FK
        uuid tenant_id FK
        int value_int "nullable"
        string value_text "nullable"
        float value_float "nullable"
        boolean value_bool "nullable"
    }
    STAT_DEFINITION {
        uuid id PK
        uuid tenant_id FK
        uuid stat_group_id FK
        string name
        string value_type
        string unit "nullable"
        boolean adjustable_in_play
        boolean pin
        boolean signed
        int position
        uuid max_hint_id FK "nullable"
        uuid min_hint_id FK "nullable"
        uuid resolved_hint_id FK "nullable"
    }
    STAT_DEFINITION_ENUM_VALUE {
        uuid id PK
        uuid tenant_id FK
        uuid stat_definition_id FK
        string value
        int sort_order
    }
    STAT_GROUP {
        uuid id PK
        uuid tenant_id FK
        string name
        int priority
        boolean mandatory
        int position
    }
```

## Information and payloads

```mermaid
erDiagram
    PAYLOAD ||..o{ CONTENT_REFERENCE : "payload_id"
    ENTITY ||..o{ INFORMATION : "entity_id"
    INFORMATION ||..o{ KNOWLEDGE : "information_id"
    ENTITY |o..o{ KNOWLEDGE : "knower_entity_id"
    PLAYER |o..o{ KNOWLEDGE : "knower_player_id"
    INFORMATION ||..o{ PAYLOAD : "information_id"
    PAYLOAD ||..o{ PAYLOAD_DESCRIPTION : "payload_id"
    PAYLOAD ||..o{ PAYLOAD_DOCUMENT : "payload_id"
    PAYLOAD ||..o{ PAYLOAD_NUMBER : "payload_id"
    PAYLOAD ||..o{ PAYLOAD_PICTURE : "payload_id"
    CONTENT_REFERENCE {
        uuid payload_id PK,FK
        int position PK
        uuid tenant_id FK
        string kind
        string hint
        string target
    }
    INFORMATION {
        uuid id PK
        uuid tenant_id FK
        uuid entity_id FK
        string title
        string type
        boolean is_public
        int order
    }
    INFORMATION_TYPE {
        string name PK
        boolean is_singleton
        string category
    }
    KNOWLEDGE {
        uuid id PK
        uuid tenant_id FK
        uuid knower_entity_id FK "nullable"
        uuid knower_player_id FK "nullable"
        uuid information_id FK
    }
    PAYLOAD {
        uuid id PK
        uuid tenant_id FK
        uuid information_id FK
        int order
    }
    PAYLOAD_DESCRIPTION {
        uuid payload_id PK,FK
        uuid tenant_id FK
        string locale
        string content
    }
    PAYLOAD_DOCUMENT {
        uuid payload_id PK,FK
        uuid tenant_id FK
        bytes data
        string filename
        string file_type
    }
    PAYLOAD_NUMBER {
        uuid payload_id PK,FK
        uuid tenant_id FK
        string value
    }
    PAYLOAD_PICTURE {
        uuid payload_id PK,FK
        uuid tenant_id FK
        bytes data
        string file_type
    }
```

## People, campaigns, credentials and activity

```mermaid
erDiagram
    APP_USER |o..o{ APP_USER : "suspended_by"
    APP_USER |o..o{ AUDIT_LOG : "actor_id"
    ENTITY ||..o{ CAMPAIGN : "entity_id"
    CAMPAIGN ||..o{ CAMPAIGN_GM : "campaign_id"
    APP_USER ||..o{ CAMPAIGN_GM : "user_id"
    CAMPAIGN ||..o{ CAMPAIGN_PROFILE_PICTURE : "campaign_id"
    PROFILE_PICTURE ||..o{ CAMPAIGN_PROFILE_PICTURE : "profile_picture_id"
    CHARACTER ||..o{ CHARACTER_PLAYER : "character_entity_id"
    PLAYER ||..o{ CHARACTER_PLAYER : "player_id"
    APP_USER |o..o{ DEVICE_AUTHORIZATION : "user_id"
    APP_USER |o..o{ ENTITY_CHANGE : "actor_user_id"
    APP_USER ||..o{ ENTITY_CHANGE : "user_id"
    CAMPAIGN |o..o{ INVITE : "campaign_id"
    APP_USER ||..o{ MEMBERSHIP : "user_id"
    APP_USER ||..o{ NOTIFICATION : "user_id"
    APP_USER ||..o{ PERSONAL_ACCESS_TOKEN : "user_id"
    CAMPAIGN ||..o{ PLAYER : "campaign_id"
    APP_USER ||..o{ PLAYER : "user_id"
    REPOSITORY_RELEASE |o..o{ TENANT : "current_release_id"
    REPOSITORY_RELEASE ||..o{ TENANT : "id"
    STAT_GROUP ||..o{ TENANT : "id"
    STAT_GROUP |o..o{ TENANT : "weapon_stat_group_id"
    CAMPAIGN ||..o{ TENANT_ADMIN_CAMPAIGN_OPT_OUT : "campaign_id"
    APP_USER ||..o{ TENANT_ADMIN_CAMPAIGN_OPT_OUT : "user_id"
    PROFILE_PICTURE ||..o{ TENANT_PROFILE_PICTURE : "profile_picture_id"
    PROFILE_PICTURE ||..o{ USER_PROFILE_PICTURE : "profile_picture_id"
    APP_USER ||..o{ USER_PROFILE_PICTURE : "user_id"
    APP_USER {
        uuid id PK
        string authgear_subject_id
        string email "nullable"
        string nickname "nullable"
        datetime suspended_at "nullable"
        uuid suspended_by FK "nullable"
        string suspension_reason "nullable"
        string display_name "nullable"
        string pronouns "nullable"
        string bio "nullable"
        array locales
        string user_color "nullable"
        array last_seen_roles
    }
    AUDIT_LOG {
        uuid id PK
        uuid tenant_id FK
        uuid actor_id FK "nullable"
        string action
        string target_type
        uuid target_id "nullable"
        string detail "nullable"
    }
    CAMPAIGN {
        uuid id PK
        uuid tenant_id FK
        string name
        string game_system
        string slug
        string description
        boolean secret
        boolean player_self_service
        uuid entity_id FK
    }
    CAMPAIGN_GM {
        uuid tenant_id PK,FK
        uuid user_id PK,FK
        uuid campaign_id PK,FK
    }
    CAMPAIGN_PROFILE_PICTURE {
        uuid campaign_id PK,FK
        uuid tenant_id FK
        uuid profile_picture_id FK
    }
    CHARACTER_PLAYER {
        uuid character_entity_id PK,FK
        uuid player_id PK,FK
        uuid tenant_id FK
    }
    DEVICE_AUTHORIZATION {
        uuid id PK
        string device_code_hash
        string user_code
        string client_name "nullable"
        string status
        uuid user_id FK "nullable"
        string token_name "nullable"
        datetime token_expires_at "nullable"
        datetime expires_at
        datetime last_polled_at "nullable"
    }
    ENTITY_CHANGE {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        uuid character_entity_id
        uuid entity_id
        string kind
        string entity_name
        string detail "nullable"
        uuid actor_user_id FK "nullable"
        boolean actor_visible
        datetime occurred_at
    }
    INVITE {
        uuid id PK
        uuid tenant_id FK
        string kind
        uuid campaign_id FK "nullable"
        string token_hash
        string role "nullable"
        datetime expires_at
        int max_uses "nullable"
        int use_count
        datetime revoked_at "nullable"
    }
    MEMBERSHIP {
        uuid tenant_id PK,FK
        uuid user_id PK,FK
        string role
    }
    NOTIFICATION {
        uuid id PK
        uuid batch_id
        uuid user_id FK
        uuid tenant_id FK "nullable"
        string scope
        uuid source_id "nullable"
        string type
        string title
        string body
        datetime read_at "nullable"
    }
    PERSONAL_ACCESS_TOKEN {
        uuid id PK
        uuid user_id FK
        string name
        string token_hash
        string token_hint
        datetime last_used_at "nullable"
        datetime expires_at "nullable"
        datetime revoked_at "nullable"
    }
    PLAYER {
        uuid id PK
        uuid user_id FK
        uuid campaign_id FK
        uuid tenant_id FK
        boolean self_service "nullable"
    }
    PROFILE_PICTURE {
        uuid id PK
        bytes data
        string file_type
    }
    TENANT {
        uuid id PK,FK
        string name
        string slug
        string description
        string kind
        datetime published_at "nullable"
        uuid current_release_id FK "nullable"
        boolean npcs_shared_with_gms
        int export_revision
        uuid weapon_stat_group_id FK "nullable"
        string ability_information_type "nullable"
    }
    TENANT_ADMIN_CAMPAIGN_OPT_OUT {
        uuid tenant_id PK,FK
        uuid user_id PK,FK
        uuid campaign_id PK,FK
    }
    TENANT_PROFILE_PICTURE {
        uuid tenant_id PK,FK
        uuid profile_picture_id FK
    }
    USER_PROFILE_PICTURE {
        uuid user_id PK,FK
        uuid profile_picture_id FK
    }
```

## Repositories, copies, profiles and releases

```mermaid
erDiagram
    APP_USER |o..o{ REPOSITORY_COPY : "copied_by"
    ENTITY |o..o{ REPOSITORY_COPY_LINK_ENTITY : "entity_id"
    STAT_DEFINITION |o..o{ REPOSITORY_COPY_LINK_STAT_DEFINITION : "stat_definition_id"
    STAT_GROUP |o..o{ REPOSITORY_COPY_LINK_STAT_GROUP : "stat_group_id"
    PROFILE_PICTURE |o..o{ REPOSITORY_PROFILE : "cover_picture_id"
    REPOSITORY_RELEASE ||..o{ REPOSITORY_RELEASE_DOCUMENT : "release_id"
    ENTITY ||..o{ REPOSITORY_SHOWCASE : "entity_id"
    TENANT ||..o{ REPOSITORY_SUBSCRIPTION : "repository_tenant_id"
    TENANT ||..o{ REPOSITORY_SUBSCRIPTION : "subscriber_tenant_id"
    REPOSITORY_COPY {
        uuid tenant_id
        uuid repository_tenant_id PK
        string repository_name
        datetime copied_at
        uuid copied_by FK "nullable"
        datetime synced_at
        uuid synced_release_id "nullable"
    }
    REPOSITORY_COPY_LINK_ATTACHMENT {
        uuid tenant_id
        uuid source_tenant_id PK
        uuid child_source_id PK
        uuid parent_source_id PK
        datetime copied_at
    }
    REPOSITORY_COPY_LINK_ENTITY {
        uuid entity_id FK "nullable"
    }
    REPOSITORY_COPY_LINK_STAT_DEFINITION {
        uuid stat_definition_id FK "nullable"
        string mode
    }
    REPOSITORY_COPY_LINK_STAT_GROUP {
        uuid stat_group_id FK "nullable"
        string mode
    }
    REPOSITORY_PROFILE {
        uuid tenant_id PK,FK
        string visibility
        string preview
        string summary
        string licence_label "nullable"
        string licence_url "nullable"
        json credits
        array tags
        string system "nullable"
        array languages
        uuid cover_picture_id FK "nullable"
        string release_label "nullable"
        datetime released_at "nullable"
        int entry_count "nullable"
        int stat_definition_count "nullable"
    }
    REPOSITORY_RELEASE {
        uuid id PK
        uuid tenant_id FK
        int number
        string label
        string notes "nullable"
        boolean breaking
        string digest "nullable"
        json counts "nullable"
        json breaking_rows
        json warning_rows
    }
    REPOSITORY_RELEASE_BLOB {
        uuid tenant_id PK,FK
        string sha256 PK
        bytes data
    }
    REPOSITORY_RELEASE_DOCUMENT {
        uuid release_id PK,FK
        uuid tenant_id FK
        int format
        bytes content
        array blobs
    }
    REPOSITORY_RELEASED_ROW {
        uuid id PK
        uuid tenant_id FK
        string kind
        uuid row_id
        uuid parent_id "nullable"
        string hash
        string name
        json facts
    }
    REPOSITORY_SHOWCASE {
        uuid entity_id PK,FK
        uuid tenant_id FK
        int position
    }
    REPOSITORY_SUBSCRIPTION {
        uuid repository_tenant_id PK,FK
        uuid subscriber_tenant_id PK,FK
        string source
    }
```

## Rules the lines do not show

- **Tenant isolation:** tenant data has `tenant_id` and `FORCE ROW LEVEL SECURITY`, read through a restricted app role (ADR 0002, 0021). Tenant-to-tenant foreign keys include `tenant_id` (ADR 0117). `repository_subscription` is the deliberate cross-tenant grant table, with policies on both ends.
- **Inheritance:** `entity_prototype.position` orders parents and breaks equal-distance, equal-priority stat ties (ADR 0266). Cycles are refused by database triggers.
- **Knowledge and visibility:** public, character, player and group audiences determine which information a caller reads (ADR 0028, 0109); the lines do not imply access. A content reference is keyed by its textual target, not a foreign key to the entity it resolves to (ADR 0110).
- **Repositories:** a repository is a tenant of kind `repository`, with no campaigns. Copies have local rows, plain source identifiers and snapshots; source identifiers deliberately outlive the source repository. Attachments carry parents a bridge adds to copied entries (ADR 0118 to 0121, 0172).
- **Releases:** release documents and blobs preserve public content; `tenant.current_release_id` selects the current release, with retention and rollback (ADR 0214, 0288). Private repository reads remain live. Public reads and previews use the current document and the read/preview gates (ADR 0286, 0287, 0293).
- **Credentials:** personal tokens and device authorizations belong to a user, not a tenant; only hashes of credentials are stored (ADR 0268).
- **Activity:** logs and change-feed records keep identifiers of deleted objects without foreign keys to those objects. A notification can later be marked read; its `read_at` changes even though its authored message stays fixed (ADR 0058, 0099).
