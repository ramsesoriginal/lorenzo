# 0245 - Bench: the order of the notes

Status: accepted

## Context

[ADR 0237](0237-api-pictures-and-information-order.md) added `PUT /entities/{id}/information/order` to the API, which takes the complete list of the information the caller can see. Bench shows an entry's notes in the order the server gives them but could not change it.

## Decision

- **Each note has "Move note up" and "Move note down"** buttons beside it (the first cannot go up, the last cannot go down). Buttons first, since they work with the keyboard and a screen reader; dragging can come later.
- **It is a command**, `notes.set-order`, so it is shown at once, sent in order with the rest, undone by Undo, and kept waiting without a connection. Its value is the notes' ids joined by commas, one string, because the order itself is what is compared: a list value is compared without regard to order, which would take a move for no change. Three-way compare works as for any field: the order changed elsewhere to another order is a conflict, "Keep mine" or "Use theirs".
- **The whole list is sent, the notes in their places.** The server wants every piece of information the caller can see (the description, notes, the picture, others). The transport reads the entry, lets the notes take the places the notes held in the order asked, and keeps everything else where it was. A note the client has not heard of stays where it is. A 409 (something was added or taken away meanwhile) is shown as needing attention, like any refused write.
- **It waits for notes made here.** A move names notes by id, so it is held until the notes it names have been sent.

## Not in scope

Dragging a note; moving the description among the notes (it is not one); reordering other kinds of information, which Bench does not show.

## Consequences

- A move is one write whatever the distance; a note moved up two places by two clicks is two commands, each undone separately.
