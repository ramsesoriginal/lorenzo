export const STAT_KEYS = ["a", "b", "c"] as const;
export type StatKey = (typeof STAT_KEYS)[number];
export type Field = "name" | StatKey;

export interface Entry {
  id: string;
  name: string;
  stats: Record<StatKey, number | null>;
  version: string;
}

export type CommandState = "waiting" | "conflict" | "attention";

export interface Command {
  seq?: number; // assigned by IndexedDB, gives the order they were written in
  v: 1; // command version (RFC 0039 §3: the outbox outlives deploys)
  type: "entry.create" | "entry.set-field";
  id: string; // command id
  tab: string; // the tab that wrote it: only that tab may fold later edits into it
  entryId: string; // for create: the client-made id
  field?: Field;
  base?: string | number | null; // what the user saw when they changed it
  value: string | number | null;
  create?: { name: string; stats: Record<StatKey, number | null> };
  state: CommandState;
  theirs?: string | number | null;
  error?: string;
}

export type RowState = "synced" | "waiting" | "saved-on-device" | "conflict" | "attention";

export interface RowView {
  id: string;
  name: string;
  stats: Record<StatKey, number | null>;
  state: RowState;
  pending: number;
  conflict: null | { cmdId: string; field: Field; base: unknown; mine: unknown; theirs: unknown };
}
