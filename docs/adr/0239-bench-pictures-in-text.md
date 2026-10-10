# 0239 - Bench: pictures in text

Status: accepted

## Context

[ADR 0233](0233-bench-links-to-entries-in-text.md) and [ADR 0236](0236-bench-link-names.md) made `[[Name]]` and `[text](slug)` links work in Bench's previews. LorenzoScript has the matching image form, `![alt](slug)`, which names an entry's picture; Bench rendered it as its alt text. The API already serves an entry's main picture ([ADR 0237](0237-api-pictures-and-information-order.md) adds writing it).

## Decision

- `![alt](slug)` shows the **main picture** of the entry the link name stands for: the picture payload of its `main_picture` information. An entry without one, or a name nothing holds, shows the alt text as before.
- `Transport.pictureOf(entryId)` reads the entry and fetches the payload through the authenticated client (`GET .../payloads/{id}/content`, as a blob), answering a `blob:` URL; `null` when there is no picture. A plain `<img src>` could not carry the bearer token, which is why it is a blob.
- `LinkResolver` fetches pictures only for entries an *image* link names, once per entry (a link does not cause a fetch), after the slug lookup of `render`. A failed fetch is not remembered and is tried again at the next render. `renderNow` shows only pictures already fetched, so the preview that follows the typing never waits; the full render then fills in.
- The blob URLs live as long as the page does; they are small and bounded by the entries linked to.

## Consequences

- No new API route is needed. Reading the entry for its picture is one extra request per linked picture.
- Pictures show in Bench's previews only; other places that render text (hover card) are unchanged.
- Changing an entry's picture while Bench is open is not noticed until reload.
