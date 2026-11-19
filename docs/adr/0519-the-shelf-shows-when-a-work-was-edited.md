# 0519 - The shelf shows when a work was edited

Status: accepted, answering Q4 of [ADR 0494](0494-writing-moves-into-the-web-shell.md), which the maintainer first answered "not yet" and then asked for.

## Context

Writing's shelf (W1) lists the work from the entry list, which gave a name and a kind. A writer coming back wants the work they were on, and the browser's "last opened" only knows this browser.

## Decision

- **`GET /tenants/{tenant_id}/entities` rows carry `updated_at`**, the time the entry was last changed (the entry's own version, which every structural and text change of a manuscript touches). It is additive: nothing that reads the list needs to change.
- **The shelf shows it**: each work reads "Edited today", "yesterday", "N days ago" or the date, the list is most recently changed first, and a count line says how many of how many works are shown.
- **Not in this decision:** a count of words per work (the API has no such count; the outline tree counts on the client, one read per row, which a whole shelf must not do).

## Consequences

- The generated clients gain `updated_at` on the list row.
- Continue stays what it was: the work last opened in this browser.
