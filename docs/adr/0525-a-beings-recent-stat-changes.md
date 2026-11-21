# 0525 - A being's recent stat changes

Status: accepted, the first slice (BA) of [ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md), chosen by the maintainer so that the History of a being's sheet ([BN9](../design/web/beings/README.md): "Hit points 16 to 14, by Ana, 17:12") is complete from the start. An exception to the coverage rule of [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md).

## Context

The History of a being's sheet says who made each step. The sheet's own undo is a client-side list of the person's own steps, and the API cannot say who changed a stat: a stat row (`entity_stat`) knows when it changed, not by whom, and ADR 0084 leaves stat-value writes out of the activity log on purpose ("high volume, low accountability value"), which is also admin-only.

## Decision

- **A table, `entity_stat_change`** (tenant data: `tenant_id`, row level security forced, same-tenant keys to the entry and the stat definition, deleted with either): the entry, the stat, the value before (`old_value`, null when the entry had no own value) and after (`new_value`, null when the value was removed), the actor and the time. A bool, a number or a text is stored as the JSON of itself. It is a table no repository holds and no copy carries (`copy: none`).
- **It is written in the one place a stat's own value is written** (`_write_own_value`, which the stat PUT and the tag PUT and PATCH share) and where one is removed (the two DELETE routes). A value that is already the value is not a step. Only the latest 100 steps of an entry are kept, dropped in the same transaction; the History shows the latest 30 by default.
- **`GET /tenants/{tenant_id}/entities/{entity_id}/stat-changes?limit=`** lists them newest first, each with the stat's id and name, the old and new value, and the actor's id and name (the person's nickname, else display name, else null). The gate is the entry's own read (`GET /{entity_id}`): whoever may read a being's stats may read how they changed, and an entry the caller cannot see is a 404. Stats are not hidden from a reader one by one, so there is no further filter.
- **It is not the activity log.** The admin timeline of ADR 0063 and 0084 stays as it is; this is a bounded list for the sheet, readable by the table.
- **Not in this slice:** the sheet's History itself (B5), the other writes that move a number (a computed stat has no own value to change), and a way to undo from the server's list (undo stays the client's, through the same writes).

## Consequences

- The generated clients gain the read.
- A stat write now also writes one small row, and a delete of a being or a stat takes its history with it.
- Every step is attributed: the actor is the user who made the request, as `updated_by` already says for the entry.
