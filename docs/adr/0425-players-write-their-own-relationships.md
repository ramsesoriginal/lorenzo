# 0425 - Players write their own relationships

Status: accepted, decided with the maintainer on 2026-11-05 as the "who writes, later" of
[ADR 0404](0404-who-sees-and-who-writes-a-relationship.md), recorded here as its own ADR;
[RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md) slice 14.

## Context

ADR 0404 let Authors, GMs and full-visibility Owners and Organizers write relationships and said a player may later
make one with a being they control, with a default audience of that being and the GMs, and may not widen it. A player
knows their own character's loyalties and grudges better than a GM does, and has nowhere to put them.

## Decision

- **Making.** `POST /tenants/{t}/relationships` also takes a player (a participant who is not a writer) when at least
  one end is a being they control (their own characters, ADR 0124's reach). Both ends must be entries the player can
  see, and the other rules of ADR 0399 hold (two different entries, an end is never itself a relationship, the library
  limit).
- **The audience is the being and the GMs, and no wider.** What a player makes is restricted, whatever the body says:
  `is_public: true` from a player is a `403`. The controlled being (each, when both ends are theirs) is granted it, so
  the player reads it back, and the GMs read it through their reach as they read every relationship (ADR 0404). A player
  never changes an audience: the audience routes stay with those who write relationships.
- **Changing and deleting their own.** `PUT /relationships/{id}` and `DELETE /relationships/{id}` (new, under
  `If-Match`) also take the player who made it, while they still control an end of it; a replacement keeps a
  controlled end. A player never touches a relationship someone else made.
- **Standings** of a player's relationship are written by those who write relationships (the bulk write and the stat
  routes); a player's standings arrive with the standing rule of their own, if wanted. Nothing here lets a player change
  another entry's relationships, or any type, stat, web or audience.
- **Reads** are unchanged: a relationship is read only with both ends and its own audience (ADR 0399), so a player who
  made one with a being they control and a hidden end could not make it (the end must be visible to them).
- A relationship carries `can_edit` on its own read: true for a writer, and for the player who made it while they
  control an end. The interface offers the changes by it; the API decides each.
- A player's relationship feeds no access (RFC 0049 S3): a grant to a being is a grant to read one entry.

## Validation and delivery

Tests: a player making one with their being (restricted, granted to the being, read back by the player and a GM, not by
another player); `is_public` refused; no controlled end refused; an end the player cannot see refused; changing and
deleting their own, and not another's; a replacement that drops the controlled end refused; `can_edit`; a writer's
behaviour unchanged.

## Excluded

A player widening an audience, writing a type or a standing, making a web, changing a relationship someone else made,
and a group's members writing for the group.
