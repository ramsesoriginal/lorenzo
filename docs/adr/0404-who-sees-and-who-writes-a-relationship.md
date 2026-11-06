# 0404 - Who sees and who writes a relationship

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slices 2 and 14. Builds on [ADR 0305](0305-facts-and-entry-audiences.md),
[ADR 0304](0304-atomic-information-audiences.md) and [ADR 0399](0399-relationships-the-kind-and-its-two-ends.md).

## Context

Some ties are secret: a hidden loyalty, a romance, a debt. A stat has no audience of its own (a value is as visible as
its entry), and a relationship is shown only with both ends visible. The audience has to be the relationship's.

## Decision

- **Restricted by default.** A relationship made through the route is restricted unless `is_public`, whatever its type.
  The starter repository sets no audience.
- **Named recipients.** The entry audience of ADR 0305 (`entity_audience` and `entity_knowledge`) is enabled for the
  `relationship` kind: a restricted relationship can be granted to characters, groups and players, with the atomic,
  versioned `GET` and `PUT .../entities/{id}/audience` that facts have (`If-Match`, 428 and 412). Group grants follow
  current membership. A grant does not reveal an end the reader cannot see: the rule of ADR 0399 still needs both ends.
- **Different readers, different entries.** What one reader may know and another may not is two relationships, each
  with its own audience, never a redaction of one (authored truths, ADR 0028). A public friendship and a restricted
  romance between one pair are two entries.
- **Notes** on a relationship are information with their own audiences ([ADR 0304](0304-atomic-information-audiences.md));
  sharing a note never reveals the relationship.
- **Who reads**: any participant, only what is visible. A restricted relationship is read through explicit grants, by
  its applicable GMs and by library Owners and Organizers who have not opted out, as ADR 0305 says for facts. Authors
  read authored world content.
- **Who writes, first**: those who write Locations and Maps: Authors, GMs and full-visibility Owners and Organizers.
  They make, replace the ends of, restrict, share and delete.
- **Who writes later (slice 14, its own ADR)**: a player may make a relationship with a being they control, with a
  default audience of that being and the GMs, and may not widen it beyond. Nothing here lets a player change another
  entry's relationships.
- **No relationship feeds access** (RFC 0049 S3).

## Validation and delivery

Tests: restricted by default for the route and the bulk write; a grant to a character, a group and a player; an
audience change under `If-Match`; a granted reader with a hidden end seeing nothing; two relationships for one pair
with different audiences reading differently; group membership changing a reader's view; the opted-out Owner; the
Author reach; every read applying the same predicate as ADR 0399.

## Excluded

Players writing (slice 14), a redacted or merged view of two relationships, a per-stat audience, and any grant that
widens the entry gate silently.
