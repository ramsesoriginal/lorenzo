// Commands: every change the user makes is one of these, written down before it is sent
// (RFC 0039 section 2). Each names the field it changes, with the value the person saw (its base)
// next to the new one, so a conflict can be told from a plain write, and so it can be undone.

import type {
  EditableKind,
  EntryState,
  StatScalar,
  StatType,
  TextDoc,
  Transport,
} from './transport';

/** `null` is no value of its own, for a stat: the entry inherits. */
export type Value = StatScalar | string[] | null;
export type CommandType =
  | 'entry.create'
  | 'entry.set-name'
  | 'entry.set-parents'
  | 'entry.set-kind'
  | 'entry.set-slug'
  | 'stat.set'
  | 'description.set-text'
  | 'note.add'
  | 'note.set-text';
export type CommandState = 'waiting' | 'sending' | 'synced' | 'conflict' | 'attention';

/** What a create makes besides its name. */
export interface CreateArgs {
  kinds: string[];
  parents: string[];
  /** The link name it is made with (the slug of its name), or none. */
  slug?: string | null;
}

export interface Command {
  id: number;
  type: CommandType;
  /** Bumped when a command's shape changes, so an old one stored on the device can be upgraded. */
  version: 1;
  /** For a create, the id the client made for the new entry (ADR 0222). */
  entryId: string;
  /** What the user saw when they made the change. */
  base: Value;
  mine: Value;
  state: CommandState;
  /** A create's kinds and parents. */
  args?: CreateArgs;
  /**
   * For a description or a note: the information it is about. For a description that is not
   * there yet, and for a new note, an id the client made (ADR 0222).
   */
  textId?: string;
  /** For a kind: which one. The value is whether the entry has it. */
  kind?: EditableKind;
  /** For a stat: which one, and its type, which decides how it is sent. */
  stat?: { id: string; name: string; type: StatType };
  /** What the server has now, when that is a conflict. */
  theirs?: Value;
  /** What the server said, when the command needs attention. */
  error?: string;
}

interface Definition {
  /** The field in a person's words, for messages. */
  label: string;
  read(entry: EntryState, c: Command): Value;
  apply(entry: EntryState, value: Value, c: Command): EntryState;
  send(transport: Transport, entry: EntryState, value: Value, c: Command): Promise<EntryState>;
}

const asList = (v: Value): string[] => (Array.isArray(v) ? v : [String(v)]);

export function sameValue(a: Value, b: Value): boolean {
  if (!Array.isArray(a) || !Array.isArray(b)) return a === b;
  const x = [...asList(a)].sort();
  const y = [...asList(b)].sort();
  return x.length === y.length && x.every((v, i) => v === y[i]);
}

const sent = (): Promise<EntryState> => Promise.reject(new Error('This is sent by the runner.'));

/** The text of a piece of information on the entry, or '' when it is not there. */
export function docOf(entry: EntryState, c: Command): TextDoc | undefined {
  return c.type === 'description.set-text'
    ? (entry.description ?? undefined)
    : entry.notes.find((n) => n.id === c.textId);
}

const withText = (doc: TextDoc | undefined, c: Command, text: string, title: string): TextDoc => ({
  id: doc?.id ?? (c.textId as string),
  payloadId: doc?.payloadId ?? '',
  title: doc?.title ?? title,
  text,
  version: doc?.version ?? null,
});

const descriptionDef: Definition = {
  label: 'description',
  read: (entry) => entry.description?.text ?? '',
  apply: (entry, value, c) => ({
    ...entry,
    description: withText(entry.description ?? undefined, c, value as string, 'Description'),
  }),
  send: sent,
};
const noteAddDef: Definition = {
  label: 'note',
  read: (entry, c) => entry.notes.find((n) => n.id === c.textId)?.text ?? '',
  apply: (entry, value, c) =>
    entry.notes.some((n) => n.id === c.textId)
      ? {
          ...entry,
          notes: entry.notes.map((n) => (n.id === c.textId ? { ...n, text: value as string } : n)),
        }
      : { ...entry, notes: [...entry.notes, withText(undefined, c, value as string, 'Note')] },
  send: sent,
};
const noteSetDef: Definition = {
  label: 'note',
  read: (entry, c) => entry.notes.find((n) => n.id === c.textId)?.text ?? '',
  apply: (entry, value, c) => ({
    ...entry,
    notes: entry.notes.map((n) => (n.id === c.textId ? { ...n, text: value as string } : n)),
  }),
  send: sent,
};

/** The entry's own value for the command's stat, or null when it has none of its own. */
export function ownStat(entry: EntryState, c: Command): StatScalar | null {
  const s = entry.stats.find((x) => x.statId === c.stat?.id);
  return s?.own ? s.value : null;
}

const statDef: Definition = {
  label: 'stat',
  read: (entry, c) => ownStat(entry, c),
  apply: (entry, value, c) => {
    const stat = c.stat as NonNullable<Command['stat']>;
    const has = entry.stats.some((x) => x.statId === stat.id);
    if (value === null) {
      // Cleared: what it inherits is not known until the server says, so it shows as inherited.
      return {
        ...entry,
        stats: entry.stats.map((x) =>
          x.statId === stat.id ? { ...x, own: false, value: null } : x,
        ),
      };
    }
    const next = { statId: stat.id, name: stat.name, value: value as StatScalar, own: true };
    return {
      ...entry,
      stats: has
        ? entry.stats.map((x) => (x.statId === stat.id ? next : x))
        : [...entry.stats, next],
    };
  },
  send: (t, entry, value, c) =>
    t.setStat(
      entry.id,
      c.stat as NonNullable<Command['stat']>,
      value as StatScalar | null,
      entry.etag,
    ),
};

const slugDef: Definition = {
  label: 'link name',
  read: (entry) => entry.slug,
  apply: (entry, value) => ({ ...entry, slug: value as string | null }),
  send: (t, entry, value) => t.setSlug(entry.id, value as string | null),
};

const KIND_ORDER = ['item', 'item_instance', 'being', 'character'];

const kindDef: Definition = {
  label: 'kind',
  read: (entry, c) => entry.kinds.includes(c.kind as string),
  apply: (entry, value, c) => {
    const rest = entry.kinds.filter((k) => k !== c.kind);
    const kinds = value === true ? [...rest, c.kind as string] : rest;
    return { ...entry, kinds: kinds.sort((a, b) => KIND_ORDER.indexOf(a) - KIND_ORDER.indexOf(b)) };
  },
  send: (t, entry, value, c) =>
    t.setKind(entry.id, c.kind as EditableKind, value === true, entry.etag),
};

export const REGISTRY: Record<CommandType, Definition> = {
  'description.set-text': descriptionDef,
  'note.add': noteAddDef,
  'note.set-text': noteSetDef,
  'stat.set': statDef,
  'entry.set-kind': kindDef,
  'entry.set-slug': slugDef,
  // A create is sent by the runner itself, which has the whole command; this is how it shows.
  'entry.create': {
    label: 'name',
    read: (entry) => entry.name,
    apply: (entry, value) => ({ ...entry, name: value as string }),
    send: () => Promise.reject(new Error('A create is sent whole.')),
  },
  'entry.set-name': {
    label: 'name',
    read: (entry) => entry.name,
    apply: (entry, value) => ({ ...entry, name: value as string }),
    send: (t, entry, value) => t.setName(entry.id, value as string, entry.etag),
  },
  'entry.set-parents': {
    label: 'parents',
    read: (entry) => entry.parentIds,
    apply: (entry, value) => ({ ...entry, parentIds: asList(value) }),
    send: (t, entry, value) => t.setParents(entry.id, asList(value), entry.etag),
  },
};

/** The three-way comparison of RFC 0039 section 5, for one field. */
export type Verdict = 'send' | 'already' | 'conflict';

export function compare(base: Value, mine: Value, theirs: Value): Verdict {
  if (sameValue(theirs, mine)) return 'already';
  if (sameValue(theirs, base)) return 'send';
  return 'conflict';
}

/** The command that puts back what this one changed (a create has none: nothing is deleted here). */
export function inverseOf(
  c: Command,
): Pick<Command, 'type' | 'entryId' | 'base' | 'mine' | 'textId' | 'stat' | 'kind'> | null {
  if (c.type === 'entry.create' || c.type === 'note.add') return null;
  return {
    type: c.type,
    entryId: c.entryId,
    base: c.mine,
    mine: c.base,
    textId: c.textId,
    stat: c.stat,
    kind: c.kind,
  };
}

/** The id this command makes, when it makes one: an entry, or a note. */
export function makesId(c: Command): string | undefined {
  if (c.type === 'entry.create') return c.entryId;
  if (c.type === 'note.add') return c.textId;
  return undefined;
}

/** Every id this command needs to exist before it can be sent: its entry, its parents, its note. */
export function usedIds(c: Command): string[] {
  const ids = [c.entryId, ...(Array.isArray(c.mine) ? c.mine : []), ...(c.args?.parents ?? [])];
  if (c.type === 'note.set-text' && c.textId) ids.push(c.textId);
  return ids;
}
