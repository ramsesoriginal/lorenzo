// Commands: every change the user makes is one of these, written down before it is sent
// (RFC 0039 section 2). Each names the field it changes, with the value the user saw (its base)
// next to the new one, so a conflict can be told from a plain write, and so it can be undone.

import type { ItemState, Transport } from './transport';

export type Value = string | string[];
export type CommandType = 'entry.set-name' | 'entry.set-parents';
export type CommandState = 'waiting' | 'sending' | 'synced' | 'conflict' | 'attention';

export interface Command {
  id: number;
  type: CommandType;
  /** Bumped when a command's shape changes, so an old one stored on the device can be upgraded. */
  version: 1;
  entryId: string;
  /** What the user saw when they made the change. */
  base: Value;
  mine: Value;
  state: CommandState;
  /** What the server has now, when that is a conflict. */
  theirs?: Value;
  /** What the server said, when the command needs attention. */
  error?: string;
}

interface Definition {
  /** The field in a person's words, for messages. */
  label: string;
  read(item: ItemState): Value;
  apply(item: ItemState, value: Value): ItemState;
  send(transport: Transport, item: ItemState, value: Value): Promise<ItemState>;
}

const asList = (v: Value): string[] => (Array.isArray(v) ? v : [v]);

export function sameValue(a: Value, b: Value): boolean {
  if (typeof a === 'string' || typeof b === 'string') return a === b;
  const x = [...asList(a)].sort();
  const y = [...asList(b)].sort();
  return x.length === y.length && x.every((v, i) => v === y[i]);
}

export const REGISTRY: Record<CommandType, Definition> = {
  'entry.set-name': {
    label: 'name',
    read: (item) => item.name,
    apply: (item, value) => ({ ...item, name: value as string }),
    send: (t, item, value) => t.setName(item.id, value as string, item.etag),
  },
  'entry.set-parents': {
    label: 'parents',
    read: (item) => item.parentIds,
    apply: (item, value) => ({ ...item, parentIds: asList(value) }),
    send: (t, item, value) => t.setParents(item.id, asList(value), item.etag),
  },
};

/** The three-way comparison of RFC 0039 section 5, for one field. */
export type Verdict = 'send' | 'already' | 'conflict';

export function compare(base: Value, mine: Value, theirs: Value): Verdict {
  if (sameValue(theirs, mine)) return 'already';
  if (sameValue(theirs, base)) return 'send';
  return 'conflict';
}

/** The command that puts back what this one changed. */
export function inverseOf(c: Command): Pick<Command, 'type' | 'entryId' | 'base' | 'mine'> {
  return { type: c.type, entryId: c.entryId, base: c.mine, mine: c.base };
}
