// Commands: every change the user makes is one of these, written down before it is sent
// (RFC 0039 section 2). Each names the field it changes, with the value the person saw (its base)
// next to the new one, so a conflict can be told from a plain write, and so it can be undone.

import type { EntryState, Transport } from './transport';

export type Value = string | string[];
export type CommandType = 'entry.create' | 'entry.set-name' | 'entry.set-parents';
export type CommandState = 'waiting' | 'sending' | 'synced' | 'conflict' | 'attention';

/** What a create makes besides its name. */
export interface CreateArgs {
  kinds: string[];
  parents: string[];
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
  /** What the server has now, when that is a conflict. */
  theirs?: Value;
  /** What the server said, when the command needs attention. */
  error?: string;
}

interface Definition {
  /** The field in a person's words, for messages. */
  label: string;
  read(entry: EntryState): Value;
  apply(entry: EntryState, value: Value): EntryState;
  send(transport: Transport, entry: EntryState, value: Value): Promise<EntryState>;
}

const asList = (v: Value): string[] => (Array.isArray(v) ? v : [v]);

export function sameValue(a: Value, b: Value): boolean {
  if (typeof a === 'string' || typeof b === 'string') return a === b;
  const x = [...asList(a)].sort();
  const y = [...asList(b)].sort();
  return x.length === y.length && x.every((v, i) => v === y[i]);
}

export const REGISTRY: Record<CommandType, Definition> = {
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

/** The command that puts back what this one changed (a create has none: an entry is not deleted here). */
export function inverseOf(c: Command): Pick<Command, 'type' | 'entryId' | 'base' | 'mine'> | null {
  if (c.type === 'entry.create') return null;
  return { type: c.type, entryId: c.entryId, base: c.mine, mine: c.base };
}

/** Every entry this command needs to exist before it can be sent: its own, and its parents'. */
export function usedIds(c: Command): string[] {
  return [c.entryId, ...(Array.isArray(c.mine) ? c.mine : []), ...(c.args?.parents ?? [])];
}
