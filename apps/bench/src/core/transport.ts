// What the command layer needs from a server, as a small interface. The real one is built on the
// typed client (lib/transport.ts); the sample one keeps everything in memory (core/sample.ts).

export interface EntrySummary {
  id: string;
  name: string;
  kinds: string[];
  /** Its direct parents: where it shows in the tree. */
  parentIds: string[];
}

/** The kinds an author can give or take away so far; the others are made by their own routes. */
export type EditableKind = 'item' | 'being';
export const EDITABLE_KINDS: readonly EditableKind[] = ['item', 'being'];

/** A piece of text on an entry: its description, or a note. LorenzoScript, kept as written. */
export interface TextDoc {
  /** The information's id (made by the client for a new one, ADR 0222). */
  id: string;
  /** The payload that holds the text, which is what an edit writes to. */
  payloadId: string;
  title: string;
  text: string;
  /** What `If-Match` wants on an edit of the text. */
  version: string | null;
}

/** An entry a link name stands for (`GET .../entities/resolve`). */
export interface ResolvedEntry {
  slug: string;
  id: string;
  name: string;
  kinds: string[];
}

/** How a stat's value is typed (the API's `value_type`). */
export type StatType = 'int' | 'float' | 'text' | 'bool' | 'enum';
export type StatScalar = string | number | boolean;

/** A stat the repository defines: what an entry can have a value for. */
export interface StatDef {
  id: string;
  name: string;
  type: StatType;
  /** The allowed values of an enum stat, in order. */
  enumValues: string[];
}

/** One stat on an entry, as the server resolved it. `own` false means it is inherited. */
export interface StatValue {
  statId: string;
  name: string;
  /** The effective value; null for an own value just cleared, whose inherited one is not known here. */
  value: StatScalar | null;
  own: boolean;
}

/**
 * A float is not edited yet: the API wants `3.0` for a float stat, and JSON written by the browser
 * says `3` (ADR 0227).
 */
export const canEditStat = (type: StatType): boolean => type !== 'float';

/** An entry as the server last said it was. `etag` is what `If-Match` wants on a write. */
export interface EntryState {
  id: string;
  name: string;
  kinds: string[];
  parentIds: string[];
  childIds: string[];
  /** The one description, if it has one the caller may read. */
  description: TextDoc | null;
  notes: TextDoc[];
  stats: StatValue[];
  etag: string | null;
}

/** What a create of a piece of text sends: a description (one per entry) or a note. */
export interface NewText {
  id: string;
  type: 'description' | 'note';
  title: string;
  text: string;
}

/** What a create sends. The id is the client's own (ADR 0222): sent twice, it is made once. */
export interface NewEntry {
  id: string;
  name: string;
  kinds: string[];
  parents: string[];
}

/** Only an item has a name that can be changed so far. */
export const canRename = (kinds: readonly string[]): boolean => kinds.includes('item');

/** An inventory item's one parent changes through its own route, not here. */
export const canSetParents = (kinds: readonly string[]): boolean =>
  !kinds.includes('item_instance');

export interface Transport {
  listEntries(): Promise<EntrySummary[]>;
  listStatDefinitions(): Promise<StatDef[]>;
  /** The entries these link names stand for; a name nothing holds is left out. */
  resolveSlugs(slugs: string[]): Promise<ResolvedEntry[]>;
  getEntry(id: string): Promise<EntryState>;
  /** Makes the entry (or, if it is already there under this id, returns it) and answers with it. */
  createEntry(entry: NewEntry): Promise<EntryState>;
  /** Writes, and answers with the entry as it is after (a fresh `etag` included). */
  setName(id: string, name: string, etag: string | null): Promise<EntryState>;
  setParents(id: string, parentIds: string[], etag: string | null): Promise<EntryState>;
  /**
   * Sets the entry's own value for a stat, or with `null` removes it so the entry inherits again.
   * Answers with the entry as it is after (a fresh `etag` included).
   */
  setStat(
    id: string,
    stat: { id: string; type: StatType },
    value: StatScalar | null,
    etag: string | null,
  ): Promise<EntryState>;
  /** Gives the entry a kind, or takes it away. Answers with the entry as it is after. */
  setKind(id: string, kind: EditableKind, on: boolean, etag: string | null): Promise<EntryState>;
  /** Makes a description or a note on the entry under its own id, or finds it already there. */
  createText(entryId: string, text: NewText): Promise<void>;
  /** Replaces the text of a payload. `version` is its `If-Match`. */
  setText(payloadId: string, text: string, version: string | null): Promise<void>;
}

/** There is no connection: the command stays waiting and is tried again. */
export class OfflineError extends Error {
  constructor(message = 'No connection.') {
    super(message);
    this.name = 'OfflineError';
  }
}

/** The server said no. `precondition` is a stale `If-Match`: the entry changed since it was read. */
export class RefusedError extends Error {
  readonly precondition: boolean;
  constructor(message: string, precondition = false) {
    super(message);
    this.name = 'RefusedError';
    this.precondition = precondition;
  }
}
