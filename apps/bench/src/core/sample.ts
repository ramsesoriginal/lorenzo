// A server in memory, for the page without sign-in and for tests. It behaves as the real one
// does where the command layer cares: an `etag` that moves on every write, a refused write when
// `If-Match` is stale, and no connection when `offline` is set.

import {
  type EntrySummary,
  type ItemState,
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

export class SampleTransport implements Transport {
  offline = false;
  /** Every write that reached the server, for tests to look at. */
  writes: { id: string; field: 'name' | 'parents'; value: string | string[] }[] = [];
  private rows = new Map<string, SampleEntry & { version: number }>();

  constructor(entries: SampleEntry[]) {
    for (const e of entries) this.rows.set(e.id, { ...e, parents: [...e.parents], version: 1 });
  }

  private need() {
    if (this.offline) throw new OfflineError();
  }
  private row(id: string) {
    const row = this.rows.get(id);
    if (!row?.kinds.includes('item')) throw new RefusedError(`No item with id ${id}.`);
    return row;
  }
  private state(id: string): ItemState {
    const row = this.row(id);
    return { id, name: row.name, parentIds: [...row.parents], etag: `"v${row.version}"` };
  }
  private guard(id: string, etag: string | null) {
    if (etag !== null && etag !== `"v${this.row(id).version}"`)
      throw new RefusedError('The item changed since it was read.', true);
  }

  async listEntries(): Promise<EntrySummary[]> {
    this.need();
    return [...this.rows.values()].map(({ id, name, kinds }) => ({ id, name, kinds: [...kinds] }));
  }
  async getItem(id: string) {
    this.need();
    return this.state(id);
  }
  async setName(id: string, name: string, etag: string | null) {
    this.need();
    this.guard(id, etag);
    const row = this.row(id);
    row.name = name;
    row.version++;
    this.writes.push({ id, field: 'name', value: name });
    return this.state(id);
  }
  async setParents(id: string, parentIds: string[], etag: string | null) {
    this.need();
    this.guard(id, etag);
    for (const p of parentIds) {
      if (p === id) throw new RefusedError('An item cannot be its own parent.');
      if (!this.rows.has(p)) throw new RefusedError(`No entry with id ${p}.`);
    }
    const row = this.row(id);
    row.parents = [...parentIds];
    row.version++;
    this.writes.push({ id, field: 'parents', value: [...parentIds] });
    return this.state(id);
  }

  /** Someone else renames the item, behind the person's back. */
  renameElsewhere(id: string, name: string) {
    const row = this.row(id);
    row.name = name;
    row.version++;
  }
}
