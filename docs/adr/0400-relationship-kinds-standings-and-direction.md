# 0400 - Relationship types, standings and direction

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slices 4 and 13. Builds on [ADR 0399](0399-relationships-the-kind-and-its-two-ends.md),
[ADR 0037](0037-effective-stat-resolution.md) and [ADR 0104](0104-computed-stats.md).

## Context

A relationship says that two entries are tied. What the tie is (parent of, ally of), how much it counts (a
reputation, a Concordance) and which way it points need a home that is not a column, because the setting decides the
words. Stats, prototypes and formulas already exist and are the same for every entry.

## Decision

**A type is a prototype.** A relationship names its type through `prototypes` when it is made. Types are entries and
form a tree (Family, then Parent of and Sibling of); nothing is seeded.

**A standing is a stat on the relationship entry.** Its value inherits through prototypes by ADR 0037: a relationship
from a character to a group can be the prototype of a more specific one from that character to one member of it. The
nearest value wins; an adjustment is a sum formula over an inherited base and an own part, which reads the resolved
stats of the entry read (ADR 0104). Nothing checks that the member belongs to the group, and the app says "inherited
from" where a value is. A server total over a being's relationships is not built (the value would differ per reader);
the app may add up what the reader sees and says so.

**Direction is the type's.** A type may carry three optional stats, found in the library by name (RFC 0049, open
question 1):

- *directed*, a tag: a relationship of this type is one-way;
- *reads as*: the sentence verb from the first end ("is the parent of");
- *reads as, from the other end*: the verb from the second ("is a child of").

A **directed** standing is two one-way relationships, one each way, each with its own value and its own audience ("A
honors B" may be secret from B). A **symmetric** one is one two-way relationship, shown in both cells of the matrix and
edited from either. A one-way relationship fills its own cell; a two-way one fills both; two visible relationships for
one cell are a conflict the matrix shows. A library without these stats works: a relationship reads with its type's
name and its own `one_way`.

**Pairwise only.** A relationship has two ends. A marriage of three is three symmetric relationships, each with its
own audience and Events. "The marriage" as one thing with dates and stats is an entry (a group or any entry) that each
partner relates to, by the convention of [ADR 0401](0401-groups-and-relationships.md). A relationship with a set of
members is parked, as ADR 0363 parked it for connections.

**The bulk write.** `POST /tenants/{t}/relationships/bulk` takes at most 100 operations in one transaction:
`create` (as the single `POST`, plus `stats`), `set` and `clear` (a stat of an existing relationship, with its ETag)
and `delete`. Each end and each relationship is resolved under the writer's own visibility, a refusal of any operation
refuses the request and writes nothing, and the answer is the rows as written. It is the writer of the matrix.

**The words, as content.** Reputation, honor, Concordance, faith and familiarity are standings. Romantic and sexual are
types. Family (parent of and child of, sibling, co-parent, married, partner), summoner of and summoned by, patron of
and patroned by, diplomat for and diplomat in, at war with and in alliance with are types. They live in an opt-in
**starter repository**, which a library copies like any repository; it is authored with the maintainer in its own
slice, holds no default audience (every new relationship is restricted, ADR 0404), and is not code. Derived kinship
(grandparent, cousin) is never inferred; [ADR 0402](0402-relationship-through.md) lets an author state it.

## Validation and delivery

Tests: a standing inherited through a prototype chain and overridden; a sum formula over an inherited base; two
one-way relationships and one two-way one for the matrix cells; a library without the type stats; the bulk write with
each refusal writing nothing and ends hidden from the writer; the starter repository copied into an empty library.

## Excluded

A server total, a derived kinship, a relationship with a set of members, a default audience in the starter, and any
type or standing in the schema or the code.
