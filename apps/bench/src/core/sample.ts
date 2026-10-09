// A server in memory, for the page without sign-in and for tests. It behaves as the real one
// does where the command layer cares: an `etag` that moves on every write, a refused write when
// `If-Match` is stale, an id the client chose that is a replay when it is already there, and no
// connection when `offline` is set.

import {
  canRename,
  canSetParents,
  type EntryState,
  type EntrySummary,
  type NewEntry,
  OfflineError,
  RefusedError,
  type Transport,
} from './transport';

export interface SampleEntry {
  id: string;
  name: string;
  kinds: string[];
  parents: string[];
}

export type SampleWrite =
  | { id: string; field: 'name' | 'parents'; value: string | string[] }
  | { id: string; field: 'create'; value: string };

export class SampleTransport implements Transport {
  offline = false;
  /** Every write that reached the server, for tests to look at. */
  writes: SampleWrite[] = [];
  /** Ids that other tenants hold: a create with one is refused the same way the API does. */
  heldElsewhere = new Set<string>();
  private rows = new Map<string, SampleEntry & { version: number }>();

  constructor(entries: SampleEntry[]) {
    for (const e of entries) this.rows.set(e.id, { ...e, parents: [...e.parents], version: 1 });
  }

  private need() {
    if (this.offline) throw new OfflineError();
  }
  private row(id: string) {
    const row = this.rows.get(id);
    if (!row) throw new RefusedError(`No entry with id ${id}.`);
    return row;
  }
  private state(id: string): EntryState {
    const row = this.row(id);
    return {
      id,
      name: row.name,
      kinds: [...row.kinds],
      parentIds: [...row.parents],
      childIds: [...this.rows.values()].filter((r) => r.parents.includes(id)).map((r) => r.id),
      etag: `"v${row.version}"`,
    };
  }
  private guard(id: string, etag: string | null) {
    if (etag !== null && etag !== `"v${this.row(id).version}"`)
      throw new RefusedError('The entry changed since it was read.', true);
  }

  async listEntries(): Promise<EntrySummary[]> {
    this.need();
    return [...this.rows.values()].map(({ id, name, kinds }) => ({ id, name, kinds: [...kinds] }));
  }
  async getEntry(id: string) {
    this.need();
    return this.state(id);
  }
  async createEntry(entry: NewEntry) {
    this.need();
    if (this.rows.has(entry.id)) return this.state(entry.id); // a replay
    if (this.heldElsewhere.has(entry.id)) throw new RefusedError('That id is not available.');
    for (const p of entry.parents)
      if (!this.rows.has(p)) throw new RefusedError(`No entry with id ${p}.`);
    this.rows.set(entry.id, {
      id: entry.id,
      name: entry.name,
      kinds: [...entry.kinds],
      parents: [...new Set(entry.parents)],
      version: 1,
    });
    this.writes.push({ id: entry.id, field: 'create', value: entry.name });
    return this.state(entry.id);
  }
  async setName(id: string, name: string, etag: string | null) {
    this.need();
    this.guard(id, etag);
    const row = this.row(id);
    if (!canRename(row.kinds)) throw new RefusedError('Only an item can be renamed so far.');
    row.name = name;
    row.version++;
    this.writes.push({ id, field: 'name', value: name });
    return this.state(id);
  }
  async setParents(id: string, parentIds: string[], etag: string | null) {
    this.need();
    this.guard(id, etag);
    const row = this.row(id);
    if (!canSetParents(row.kinds)) throw new RefusedError('An inventory item has its own route.');
    for (const p of parentIds) {
      if (p === id) throw new RefusedError('An entry cannot be its own parent.');
      if (!this.rows.has(p)) throw new RefusedError(`No entry with id ${p}.`);
    }
    row.parents = [...parentIds];
    row.version++;
    this.writes.push({ id, field: 'parents', value: [...parentIds] });
    return this.state(id);
  }

  /** Someone else renames the entry, behind the person's back. */
  renameElsewhere(id: string, name: string) {
    const row = this.row(id);
    row.name = name;
    row.version++;
  }
}
