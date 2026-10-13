# 0243 - Bench: the main picture

Status: accepted

## Context

Slice B8 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md). The API gained one main picture per entry in [ADR 0237](0237-api-pictures-and-information-order.md), and Bench already shows an entry's picture where a text asks for it ([ADR 0239](0239-bench-pictures-in-text.md)). Nothing in Bench could yet set one.

## Decision

- **Each entry shows its main picture** in the entry pane, with "Choose picture…" (or "Replace picture…") and "Remove picture". The picture is read once per entry, through the same `pictureOf` the links in text use.
- **It is not a command.** The RFC makes pictures online-only, and the outbox's promises cannot be kept for a file: it is not stored to send later, and a removed picture cannot be undone, since the bytes are gone. A write shows "Saving…", then the picture as the server now has it; a failure shows the server's words, or "Pictures need a connection." The picture on screen is only ever what the server confirmed.
- **Only what the API takes is sent.** PNG, JPEG, WebP and GIF are checked in the browser (the size limit is the server's setting, so its refusal is shown as it comes). The upload is the API's multipart `PUT /entities/{id}/picture`; Remove is its `DELETE`.
- **An entry made here and not sent yet** says a picture can be added once it has been sent, since the server does not have it to put a picture on.
- **Links in text are told** when a picture changes, so a preview showing `![alt](slug)` fetches the new one.
- **A failed read is not drawn again for.** It is retried after ten seconds, so a redraw after each failure cannot loop.
- **`![[` picks a picture.** The entry picker of [ADR 0235](0235-bench-the-entry-picker.md) opens on `![[` too and writes `![Name](link-name)` in full, since a picture has no `[[ ]]` form. It lists every entry: whether one has a picture is not in the list, and one without shows its alt text in the preview.
- **New pictures are not public**, like every new piece of information ([ADR 0237](0237-api-pictures-and-information-order.md)). Changing that is a decision for the repository as a whole, not for this slice.

## Consequences

- Taking a picture away is final. There is no undo for it, and the pane says nothing before doing it; a confirmation can be added if that proves too easy to do by accident.
- Pictures stay out of the offline work (B4) by design.
