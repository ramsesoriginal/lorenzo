# 0237 - API: pictures on information, a main picture, and reordering information

Status: accepted

## Context

Accepts section 8 ("K8") of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md). The API stored pictures (`payload_picture`, bytes in Postgres, read through [`GET /payloads/{id}/content`](0020-rest-api-tenant-scoping-and-schemas.md)) but offered no way to put one there, take one away, or change the order of an entity's information. [ADR 0101](0101-editable-information-and-description-payloads.md) made `order` editable one row at a time, which cannot express "swap these two" under the unique `(entity_id, order)` index. Bench needs all three: it shows a being's picture and lets the author arrange notes.

## Decision

- **`POST /tenants/{t}/information/{information_id}/payloads`** takes a multipart `file` and appends a picture payload (the trigger gives it the next `order`). Same gate as every information edit (`authorize_information_edit`: sight of the row, then standing over the entity). Content type must be png, jpeg, webp or gif; size is capped by the new setting `picture_max_bytes` (default 2 MB). Either failure is a 422. The same allow-list as profile pictures ([ADR 0056](0056-profile-pictures.md)) is used, not a copy of it.
- **The main picture is one picture.** `POST` to a `main_picture` information is a 409; `PUT /tenants/{t}/entities/{id}/picture` creates the singleton `main_picture` information (201, titled "Main picture", public unless `is_public=false` is sent) or replaces its bytes in place (200). `DELETE .../picture` removes it and is idempotent (204).
- **`DELETE /tenants/{t}/payloads/{payload_id}`** removes a payload, but only a picture: any other kind is a 409, because a description or number payload is edited, not deleted. Removing the only picture of a `main_picture` information removes the information with it, since an empty singleton is meaningless.
- **`PUT /tenants/{t}/entities/{id}/information/order`** takes `information_ids`, the complete list of the information the caller can see, in the new order. A list that omits, repeats or invents a row is a 409. Information the caller cannot see keeps its slot: the visible rows are laid into the slots the visible rows occupied. The update runs in two phases under the existing entity information lock so the unique index never trips. No `If-Match`: the list itself is the precondition, and a concurrent add or remove shows up as the 409.
- Activity logs ids only ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)): `payload.picture_added`, `payload.deleted`, `information.picture_set`, `information.picture_removed`.

## Consequences

- Uploads are a single multipart request; there is no JSON/base64 variant.
- Bytes live in Postgres ([ADR 0017](0017-information-and-payloads.md)); the 2 MB cap keeps rows and backups modest and is a setting if it needs to move.
- Generated clients (TypeScript schema, CLI models) change.
