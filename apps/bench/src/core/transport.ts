import type { Information } from '@lorenzo/information-editor';
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
export type EditableKind = 'item' | 'being' | 'fact';
export const EDITABLE_KINDS: readonly EditableKind[] = ['item', 'being', 'fact'];

/** A piece of text on an entry: its description, or a note. LorenzoScript, kept as written. */
export interface TextDoc {
  /** The whole ordered bundle; legacy/sample mirrors may contain only the first text. */
  information?: Information;
  /** The information's id (made by the client for a new one, ADR 0222). */
  id: string;
  /** The payload that holds the text, which is what an edit writes to. */
  payloadId: string;
  title: string;
  text: string;
  /** What `If-Match` wants on an edit of the text. */
  version: string | null;
  /**
   * Whether the text is Everyone's: a library that copies the repository gets it, and a person
   * looking inside it before copying may read it (RFC 0038 section 5). Otherwise it is GM only.
   */
  isPublic: boolean;
}

import type { Formula } from './formulas';

/** An entry a link name stands for (`GET .../entities/resolve`). */
export interface ResolvedEntry {
  href?: string | null;
  slug: string;
  id: string;
  name: string;
  kinds: string[];
}

/** A piece of information, on another entry, whose text links to an entry or shows its picture. */
export interface Backlink {
  /** The entry the information is about. */
  entryId: string;
  name: string;
  kinds: string[];
  informationId: string;
  title: string;
  /** `description`, `note`, … */
  type: string;
}

/** A formula an entry holds itself, with the version to send back when replacing or removing it. */
export interface HeldFormula {
  entryId: string;
  statId: string;
  formula: Formula;
  /** The `If-Match` of a write to it (a weak ETag of its `updated_at`). */
  version: string;
}

/** What a stat works out to on an entry, tried with a formula that is not saved. */
export interface Preview {
  value: StatScalar | null;
  /** `computed`: by the formula; `direct`: a value of its own wins; `unset`: nothing to read. */
  source: 'computed' | 'direct' | 'unset';
  /** What the formula read. */
  inputs: { name: string; value: StatScalar | null }[];
}

/** A group of stats in the repository's vocabulary. */
export interface StatGroup {
  id: string;
  name: string;
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

/** Whether a stat of this type can be written from Bench: every type can. */
export const canEditStat = (_type: StatType): boolean => true;

/** Fields whose base is read only when their editor opens or a command is sent. */
export type EntryFieldTarget =
  | { kind: 'information-audience' | 'entry-audience' | 'payload-order'; id: string }
  | { kind: 'fact-about'; id: string; subjectId: string };
export type FieldSnapshot = { value: string | boolean; version: string | null };
export const fieldKey = (target: EntryFieldTarget): string =>
  `${target.kind}:${target.id}${target.kind === 'fact-about' ? `:${target.subjectId}` : ''}`;

/** An entry as the server last said it was. `etag` is what `If-Match` wants on a write. */
export interface EntryState {
  fieldSnapshots?: Record<string, FieldSnapshot>;
  id: string;
  name: string;
  kinds: string[];
  parentIds: string[];
  childIds: string[];
  /** The one description, if it has one the caller may read. */
  description: TextDoc | null;
  notes: TextDoc[];
  stats: StatValue[];
  /** The name a LorenzoScript link calls it by, if it has one (`[[Name]]` is its slug). */
  slug: string | null;
  etag: string | null;
}

/** What the API accepts as a link name (ADR 0107): a letter or digit first, then letters, digits, `_`, `-`. */
const LINK_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

/** Why this cannot be a link name, in words, or null when it can. */
export function slugProblem(text: string): string | null {
  if (text.length > 100) return 'A link name is at most 100 characters.';
  if (!LINK_NAME.test(text))
    return 'Use letters, digits, - and _ only, starting with a letter or a digit.';
  return null;
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
  /** The link name to give it, which is dropped if another entry already has it. */
  slug?: string | null;
}

/** Only an item has a name that can be changed so far. */
export const canRename = (kinds: readonly string[]): boolean =>
  kinds.includes('item') || kinds.includes('fact');

/** An inventory item's one parent changes through its own route, not here. */
export const canSetParents = (kinds: readonly string[]): boolean =>
  !kinds.includes('item_instance');

export interface Transport {
  readField?(target: EntryFieldTarget): Promise<FieldSnapshot>;
  writeField?(
    entryId: string,
    target: EntryFieldTarget,
    value: string | boolean,
    version: string | null,
  ): Promise<EntryState>;

  listEntries(): Promise<EntrySummary[]>;
  listStatDefinitions(): Promise<StatDef[]>;
  /**
   * The entries these link names stand for; a name nothing holds is left out. A `my/name` stands
   * for the item held by the being the entry `from` belongs to (ADR 0240); it comes back as asked.
   */
  resolveSlugs(slugs: string[], from?: string): Promise<ResolvedEntry[]>;
  resolveCalendars?(expressions: string[]): Promise<Map<string, { text: string; href: string }>>;
  getEntry(id: string): Promise<EntryState>;
  /** What links to the entry: the texts, on other entries, that name its link name. */
  backlinks(entryId: string): Promise<Backlink[]>;
  /** The formulas the entry holds itself. */
  listFormulas(entryId: string): Promise<HeldFormula[]>;
  /** What the stat works out to on the entry with this formula, or (`null`) with what it has. */
  previewFormula(entryId: string, statId: string, formula: Formula | null): Promise<Preview>;
  /** Gives the entry the formula for the stat, replacing its own (`version` is its `If-Match`). */
  setFormula(
    entryId: string,
    statId: string,
    formula: Formula,
    version: string | null,
  ): Promise<HeldFormula>;
  /** Takes the entry's own formula for the stat away. */
  clearFormula(entryId: string, statId: string, version: string): Promise<void>;
  /** The entries that hold a formula that reads the stat. */
  formulaDependents(statId: string): Promise<{ entryId: string; statId: string }[]>;
  listStatGroups(): Promise<StatGroup[]>;
  createStatGroup(name: string): Promise<StatGroup>;
  createStat(def: {
    name: string;
    groupId: string;
    type: StatType;
    enumValues: string[];
  }): Promise<StatDef>;
  deleteStat(statId: string): Promise<void>;
  /**
   * The entry's main picture as a URL an image can show (a `blob:` one, fetched with the sign-in),
   * or `null` when it has none or it cannot be seen.
   */
  pictureOf(id: string): Promise<string | null>;
  /** Sets the entry's main picture, or replaces it. The server refuses a file it does not take. */
  setPicture(id: string, file: File): Promise<void>;
  /** Takes the entry's main picture away; nothing to take away is fine. */
  clearPicture(id: string): Promise<void>;
  /** Makes the entry (or, if it is already there under this id, returns it) and answers with it. */
  createEntry(entry: NewEntry): Promise<EntryState>;
  /** Writes, and answers with the entry as it is after (a fresh `etag` included). */
  setName(id: string, name: string, etag: string | null): Promise<EntryState>;
  setParents(id: string, parentIds: string[], etag: string | null): Promise<EntryState>;
  /**
   * Puts the entry's notes in this order. Information that is not one of them keeps its place, and
   * a note this list does not know of stays where it was. Answers with the entry as it is after.
   */
  setNoteOrder(id: string, noteIds: string[]): Promise<EntryState>;
  /**
   * Makes one of the entry's notes Everyone's (`true`) or GM only (`false`). Answers with the entry as
   * it is after.
   */
  setNotePublic(id: string, noteId: string, isPublic: boolean): Promise<EntryState>;
  /** Gives the entry a link name, or with `null` takes it away. A name another entry has is refused. */
  setSlug(id: string, slug: string | null): Promise<EntryState>;
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
  removePicturePayload?(payloadId: string, version: string): Promise<void>;
  payloadFile?(payloadId: string, version: string): Promise<string>;
  appendPicture?(
    informationId: string,
    payloadId: string,
    file: File,
    version: string,
  ): Promise<void>;
  /** Appends the first text to an information that previously held images only. */
  appendText?(
    informationId: string,
    payloadId: string,
    text: string,
    version: string,
  ): Promise<void>;
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

/** A number as the API reads a float: `3.0`, not `3`, which it reads as a whole number. */
export function decimalText(n: number): string {
  return Number.isInteger(n) ? `${n}.0` : String(n);
}

/** What a decimal stat accepts typed: a number with an optional point, no exponent. */
export function parseDecimal(text: string): number | null {
  const t = text.trim().replace(',', '.');
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : null;
}
