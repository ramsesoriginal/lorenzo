# 0402 - Relationship through

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slice 5. Builds on [ADR 0399](0399-relationships-the-kind-and-its-two-ends.md).

## Context

Some relationships hold because of others: a grandfather through a father and a father, a co-spouse through the
partner both share, trust through a chain of trusted relationships. Nothing in Lorenzo infers any of it, and none of it
should be inferred (RFC 0049 S5). The author needs to state it.

## Decision

```sql
relationship_through(relationship_entity_id, step smallint, via_entity_id, tenant_id NOT NULL,
  PRIMARY KEY (relationship_entity_id, step), UNIQUE (relationship_entity_id, via_entity_id),
  CHECK (relationship_entity_id <> via_entity_id), both ids -> relationship)
```

- **An ordered chain, authored.** A relationship is *stated* to hold through the relationships in its steps, in order.
  Nothing derives a value, a direction or a type from it, and nothing checks that the steps join the ends. A lint
  (GM and Author only) lists a chain whose ends do not meet, when every step is visible.
- **Acyclic.** A relationship is not through itself, directly or by a longer path. The check is a recursive ancestor
  check inside the write transaction under an advisory lock, with a depth cap; readers keep the cap and a path guard,
  so a cycle that arrives through a repository ends a chain without naming a row. At most 12 steps
  (*proposed default*).
- **Steps may leave gaps** after a delete; readers order by `step`. Deleting a step's relationship removes the row.
- **Visibility.** A reader sees the steps whose relationships they may see, in order, with no gap and no marker; a
  hidden step leaves no trace, as a hidden level in a part-of chain does (RFC 0048). Whether the relationship itself is
  seen is ADR 0399's rule.
- **Writes** need the standing of ADR 0399. `PUT .../relationships/{id}/through` replaces the chain atomically under
  `If-Match`.
- **Drawn dashed**: a relationship with steps is indirect, and §18 gives indirect the dashed edge. Selecting it
  highlights its steps.
- A tenant table with forced RLS, a registry line, the `repository_read` policy and a release-format bump; a copy
  writes a step only when both relationships were copied.

## Validation and delivery

Tests: a chain of three; a cycle refused by a direct and by a two-hop path; a self step; a hidden step leaving no gap
and the same bytes as a chain without it; deleting a step's relationship; the lint; copy and release; the depth cap.

## Excluded

Any derived value, any inference of a type or direction, a required match of ends, and steps that are not
relationships.
