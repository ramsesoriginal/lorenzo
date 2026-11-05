# 0401 - Groups and relationships: membership stays `group_member`

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md).
Builds on [ADR 0028](0028-knowledge-and-group-membership.md) and
[ADR 0316](0316-collaborative-events-facts-and-participant-audiences.md).

## Context

A group is a bare entry with `group_member` rows: beings only, direct, flat, and what knowledge, notifications and
ownership read. A relationship to a group could also say "member of". Two sources for one fact disagree, and only one
of them may grant access.

## Decision

- **Membership is `group_member`.** It stays the one place that says who is in a group, and the app reads and writes
  it through the existing group API.
- **A relationship to a group adds, and grants nothing.** It says a role or a standing: a rank in an order, a
  reputation with a guild, a Concordance with a pantheon. It never implies membership and membership never implies a
  relationship. No relationship row feeds access, knowledge or reach (RFC 0049 S3).
- **A pantheon** is a group of beings, or any entry. Concordance is a standing on a relationship from a being to it. A
  more specific relationship from that being to one member of the group can have the group-level one as its prototype
  ([ADR 0400](0400-relationship-kinds-standings-and-direction.md)).
- **Nesting** (a pantheon within a pantheon, a nation within an empire, a non-being member) is a relationship between
  group entries, since `group_member` cannot nest.
- **The graph draws a group as a hull** around its members from `group_member`; a relationship to the group is an edge.
  The matrix can take a group's members as its rows or columns.

## Validation and delivery

Tests: a relationship to a group changes no knowledge or notification result; a `group_member` row creates no
relationship; the matrix over a group's members; a prototype chain from a group relationship to a member relationship.

## Excluded

Any synchronization between `group_member` and relationships, a lint for their disagreement, and nested membership in
`group_member`.
