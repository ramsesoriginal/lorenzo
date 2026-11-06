# Lorenzo Social

What [Lorenzo Social](../../apps/social/README.md) does, from a person's side. It keeps the relationships between the
entries of a library: who is tied to whom, which way, how much it counts, since when, and who may see it
([RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)).

## Relationships

A **relationship** is an entry of its own kind that ties two other entries, its ends: a being, a group, a Location, an
Event, anything but another relationship. It goes one way (from the first end to the second) or both. Its **type** is a
prototype entry (parent of, ally of, at war with), so what a type carries is inherited. Two relationships may tie one
pair, even of one type: refusing a second would tell a writer that a hidden one exists.

A relationship is shown only to someone who may see it and **both of its ends**. One with a hidden end is not read as a
smaller list or a gap: it is not there. It is **restricted** when made, and opened on purpose. A restricted one can be
granted to named characters, groups and players. Authors, GMs, and Owners and Organizers write relationships; **a player
may make one with a being they control**, which is for that being and the GMs, can be changed or deleted by the player
who made it, and can never be opened to everyone ([ADR 0409](../adr/0409-players-write-their-own-relationships.md)).

## Standings

A **standing** is an ordinary stat on a relationship: honor, reputation, a Concordance. It is inherited through the
type, so a type can carry a starting value, and a number can have a **scale** (a minimum and a maximum) that an input
is held to. A library says which three stats of its own mark a type as one-way and give the words it reads as from each
end ("is the parent of", "is a child of"), and a relationship then reads as a sentence.

## Time

A relationship may name an Event where it **starts** and one where it **ends**. Read **as of** an Event, each one holds,
has not begun, has ended, or is not known, from the Events and assertions the reader can see; a limit the reader cannot
see makes it "not known" and is never named. The matrix and the graph can be read through that lens, and as what a
being **may read** (not what it believes).

## Through

A relationship can be stated to hold **through** others, in order ("a grandfather through a father and a father"). It
is authored, never inferred, and acyclic.

## Webs and the matrix

A **web** is a saved view of relationships: the entries it shows, the types it is limited to, a layout and a seed, and
hand placements. It says what it shows, not what is true, and gives access to nothing it names. A reader sees the
members and relationships they may see, and a hidden member moves no one. The layouts are circle, radial, stress,
ForceAtlas2, manual and layered (for a family tree), drawn by [`@lorenzo/graph-renderer`](../../packages/graph-renderer).

The **matrix** puts a web's entries on both sides and a standing, or whether a relationship is there, in every cell.
It holds only the cells in view, is keyboard first (arrows, Enter or F2, typing a number, Delete, undo and redo), and
saves in batches. An empty cell given a value makes a restricted relationship; a cell that two relationships fill is a
conflict. On a phone one entry's standings are a list.

## The starter

An empty library is offered a **starter** set of types and standings on the types screen: five standings with their
scales, and the usual family, bond, office, realm and intimacy types with how each reads. It is ordinary content added
on purpose, sets no audience, and can be changed or deleted.
