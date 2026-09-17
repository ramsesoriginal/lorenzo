# 0061 - Notification sender read-receipts

Status: accepted

## Context

ADR 0058/0059 gave every notification's *recipient* a `read_at` they can query via `GET /me/notifications`, but the *sender* has no way to find out whether anyone's actually read what they sent - a GM posting "session Saturday 3pm" to a campaign or group has no way to check who's seen it.

## Decision

`notification` gains `batch_id: uuid.UUID` (not null) - one value shared by every row a single `POST .../notifications` call fans out. Each of `lorenzo_api/notifications.py`'s five `create_*_notification` functions generates one `uuid.uuid4()` per call and stamps it onto every row it creates, so "did the group I messaged see it" is a single `WHERE batch_id = ...` query instead of fragile correlation by matching title/type/timestamp (which two same-titled broadcasts could collide on).

`NotificationOut` gains `batch_id` and `user_id` (the recipient) - both harmless on a recipient's own inbox read (it's already their own id), and exactly what a sender needs reading the same shape from the other side.

`GET /me/notifications/sent` (`routers/users.py`) - `Page[NotificationOut]`, `WHERE created_by = caller.id`, optional `?batch_id=` to pull just one broadcast's full recipient list, newest-first. No RLS change needed: the `created_by = app.user_id` clause ADR 0058 already added (for the `INSERT ... RETURNING` fix) already permits exactly this read.

## Not in scope

- Push/email delivery confirmation of any kind - still just in-app `read_at`, same as ADR 0058.
- A read-count summary endpoint (e.g. "3 of 5 have read this") - a client can compute this itself from the `?batch_id=` list; not worth a second endpoint for a small, already-fetched set.
- Editing or retracting a sent notification.

## Consequences

- New migration (`notification.batch_id`); `lorenzo_api/notifications.py` (all five creation functions); `schemas/notifications.py` (`NotificationOut`); `routers/users.py` (`GET /me/notifications/sent`).
