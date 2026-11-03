# Writing

Lorenzo can also hold the prose written about a world: a book, its editions and its chapters. This page says what those words mean; the app is [Lorenzo Writing](../../apps/writing/README.md).

- **Manuscript.** Any writable entry can carry its own prose and pictures, apart from its description and notes. A scene's prose, a chapter's prose and a being's biography are all manuscripts.
- **Book.** A work. Making one makes its first Edition.
- **Edition.** One shape of a Book, with its own chapters and its own wording. Another Edition starts as an independent copy of one that exists, and then diverges; names, prose and pictures are copied, notes and history are not.
- **Chapter.** A part of an Edition or of another Chapter, so chapters nest. A Chapter can also stand alone, unassigned, until it is placed. Prose may come before, between or after the chapters inside it. Taking a Chapter out of an outline never deletes its text.
- **Scene telling.** One use of a reusable [Scene](world-model.md#sessions-scenes-and-personal-lived-order) in a Book. Telling the same Scene twice makes two tellings. A telling shares the Scene's manuscript until it is made independent, and may name the being whose viewpoint it takes. A telling says nothing about whether an Event happened.
- **Reviewer.** An Author can give a signed-in account read access to chosen Editions. A reviewer reads only that Edition and writes notes that only they and the Authors see; this gives no membership in the library.

An outline is an order and a place for things, never containment, inheritance, Event order or knowledge: nothing in a manuscript is read as "who knew what". Moving a Chapter, extracting a range of text into a new Chapter, and splitting a text at a safe boundary are built; joining two Chapters is decided and not built yet. The worlds the prose refers to stay ordinary entries with their own [audiences](entities-knowledge-and-visibility.md).

Why it is built this way: [RFC 0047](../rfcs/0047-lorenzo-writing.md), [ADR 0327](../adr/0327-lorenzo-writing.md), [ADR 0341](../adr/0341-books-editions-and-chapter-composition.md) (books, editions, chapters), [ADR 0342](../adr/0342-scene-tellings-and-writing-references.md) (tellings), [ADR 0343](../adr/0343-book-scoped-reviewers.md) (reviewers) and [ADR 0344](../adr/0344-atomic-manuscript-moves.md) to [0347](../adr/0347-syntax-aware-manuscript-splits.md) (moves, extraction, splits).
