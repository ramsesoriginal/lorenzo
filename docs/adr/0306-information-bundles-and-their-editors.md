# 0306 - Information bundles and their editors

Status: accepted, decided with the maintainer on 2026-10-16. Slice of RFC 0044.

## Context

Information already holds ordered heterogeneous payloads (ADR 0017). Most editing surfaces
expose one text only; pictures have an API and specialized Bench panes (ADR 0237/0243/0255).
A map sketch and its explanation should be one piece of information with one audience. The
annotated GM version is another piece of information, not a secret payload inside the same one.

## Decision

An information editor reads and preserves every payload in its order. Text is LorenzoScript;
pictures are uploaded bytes. Numbers and documents already in a bundle remain visible and are
preserved; this slice does not add authoring for further kinds. Permissions and visibility remain
on Information. `main_picture` keeps its existing singleton path and meaning.

### Writes and concurrency

Keep the existing one-text create and text PATCH contracts. Add text append and complete payload
order replacement on Information; allow removal of text as well as pictures. Structural changes
lock the containing entry then Information and advance its version. Append and order replacement
honor the information ETag; text append and order replacement require it. Payload edits and
removal use that payload's own ETag, so a stale removal cannot discard a newer text edit.
Existing picture callers may omit their precondition for compatibility. New bundle controls
always send the applicable precondition.

A client may choose a stable payload id for text and picture append. A retry returns the existing
payload only when it belongs to the same information and its kind/content match. Authorization
precedes replay handling; an id collision elsewhere is the same generic 409 as ADR 0222. Replay
of an already accepted append precedes the version check, so a lost response does not make a
second attachment or strand a durable mobile draft. A mismatched replay is a conflict.
An edit-gated `GET /information/{id}/editor` returns the whole bundle to an authorized editor,
including an author who has not added a reader grant yet. Ordinary reads and protected bytes
continue to enforce the audiences; the editing snapshot does not grant reader access.

The new APIs preserve the payload list rather than treating a save as replacement of its first
text. Reordering requires each existing payload exactly once and leaves no partial order.

Uploads keep the configured byte cap and PNG/JPEG/WebP/GIF allow-list. New image acquisition
validates/decodes the image and bounds dimensions before staging; authenticated content reads
continue to authorize before returning bytes or 304. Content reads admit tenant participants
and then check the containing information, replacing the old author-membership-only gate so a
player can see a picture they have been told. No OCR, object store or new media service.

### Beings and inventory-web

Use the small shared information-editor package in the existing descriptions and notes. An
ordinary note starts with one LorenzoScript field. Add picture / Add text and move/remove
controls appear within editing, and the audience control remains collapsed. Read mode shows all
payloads in order. Keep existing forms, typography, icon atlas and authenticated image loading.
Unknown future kinds remain explicit rather than disappearing on save.

### Bench

Fit the existing in-place editor and command layer (ADR 0221/0224/0251/0254). Text operations name
the payload they edit; structural and audience operations retain base/current/mine conflict checks.
Dropping an image targets the information under the pointer. Pasting an image, or using the quiet
keyboard-accessible caret `+`, targets the information containing the caret. Flush pending text
and create its information first, then append the picture last. No target means no attachment;
never silently pick a different note. Preserve focus and use the existing pending/error status.
Bytes remain online-only as ADR 0243/0255 decide. Do not promise durable offline uploads or undo
of deleted image bytes. Explorer dragging and LorenzoScript link syntax keep their own meaning.

### Inventory mobile

Extend the existing native note flow, encrypted drafts and durable worker (ADR 0291). Offer the
system photo picker and camera contracts. Copy selected/captured media into encrypted app-private
storage before considering it part of a draft; never rely on a temporary gallery permission.
Preserve staged capture across process recreation, handle cancellation, apply orientation and
legibility-preserving size limits, and keep originals untouched. Render downloaded pictures through
authenticated requests and account-scoped protected storage.

Persist note id, payload ids, upload progress and desired audience. Retry each append safely;
mark a note sent only after its full bundle and audience are read back. A permanent failure stays
visible and retains its draft. Account cancellation/logout/revocation follows the existing cleanup
boundary, including staged bytes and races with workers. Offline recipient selections retain their
explicit ids; validation failure never broadens the audience. Native controls follow the same
intent as the web component without introducing a web editor inside Compose.

## Consequences

One shared content model gains editors appropriate to each app. A simple note stays simple,
while a mixed map-and-text bundle uses the same audience, links and repository behavior as text.
Persistent offline Bench authoring, OCR, new payload kinds and broader physical existence gates
remain separate work. Integration tests cover payload ordering/concurrent edits, lost-response
replay, visibility, and native draft recovery; browser flows use the real API.
