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
  type NewText,
  OfflineError,
  RefusedError,
  type StatDef,
  type StatScalar,
  type StatType,
  type StatValue,
  type TextDoc,
  type Transport,
} from './transport';

export interface SampleEntry {
  id: string;
  name: string;
  kinds: string[];
  parents: string[];
  description?: string;
  notes?: { id: string; title?: string; text: string }[];
  /** Its own stat values, by the stat's id. */
  stats?: Record<string, StatScalar>;
}

interface Text {
  id: string;
  title: string;
  text: string;
  version: number;
}

export type SampleWrite =
  | { id: string; field: 'name' | 'parents'; value: string | string[] }
  | { id: string; field: 'create'; value: string }
  | { id: string; field: 'description' | 'note.add' | 'note.text'; value: string }
  | { id: string; field: `stat:${string}`; value: StatScalar | null };

const doc = (t: Text): TextDoc => ({
  id: t.id,
  payloadId: `p-${t.id}`,
  title: t.title,
  text: t.text,
  version: `"t${t.version}"`,
});

export class SampleTransport implements Transport {
  offline = false;
  /** Every write that reached the server, for tests to look at. */
  writes: SampleWrite[] = [];
  /** Ids that other tenants hold: a create with one is refused the same way the API does. */
  heldElsewhere = new Set<string>();
  private rows = new Map<
    string,
    Omit<SampleEntry, 'description' | 'notes' | 'stats'> & {
      version: number;
      stats: Map<string, StatScalar>;
      description: Text | null;
      notes: Text[];
    }
  >();

  constructor(
    entries: SampleEntry[],
    private readonly defs: StatDef[] = [],
  ) {
    for (const e of entries)
      this.rows.set(e.id, {
        id: e.id,
        name: e.name,
        kinds: e.kinds,
        parents: [...e.parents],
        version: 1,
        stats: new Map(Object.entries(e.stats ?? {})),
        description:
          e.description === undefined
            ? null
            : { id: `${e.id}-description`, title: 'Description', text: e.description, version: 1 },
        notes: (e.notes ?? []).map((n) => ({
          id: n.id,
          title: n.title ?? 'Note',
          text: n.text,
          version: 1,
        })),
      });
  }

  private need() {
    if (this.offline) throw new OfflineError();
  }
  private row(id: string) {
    const row = this.rows.get(id);
    if (!row) throw new RefusedError(`No entry with id ${id}.`);
    return row;
  }
  /** Own values first, then what the parents have, as the API resolves them (first parent wins). */
  private effective(id: string, seen = new Set<string>()): StatValue[] {
    const row = this.row(id);
    seen.add(id);
    const out = new Map<string, StatValue>();
    for (const [statId, value] of row.stats) {
      const def = this.defs.find((d) => d.id === statId);
      if (def) out.set(statId, { statId, name: def.name, value, own: true });
    }
    for (const p of row.parents)
      if (!seen.has(p))
        for (const v of this.effective(p, seen))
          if (!out.has(v.statId)) out.set(v.statId, { ...v, own: false });
    return [...out.values()];
  }
  private state(id: string): EntryState {
    const row = this.row(id);
    return {
      id,
      name: row.name,
      kinds: [...row.kinds],
      parentIds: [...row.parents],
      childIds: [...this.rows.values()].filter((r) => r.parents.includes(id)).map((r) => r.id),
      description: row.description ? doc(row.description) : null,
      notes: row.notes.map(doc),
      stats: this.effective(id),
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
  async listStatDefinitions(): Promise<StatDef[]> {
    this.need();
    return this.defs.map((d) => ({ ...d, enumValues: [...d.enumValues] }));
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
      stats: new Map(),
      description: null,
      notes: [],
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

  async setStat(
    id: string,
    stat: { id: string; type: StatType },
    value: StatScalar | null,
    etag: string | null,
  ) {
    this.need();
    this.guard(id, etag);
    const row = this.row(id);
    const def = this.defs.find((d) => d.id === stat.id);
    if (!def) throw new RefusedError(`No stat with id ${stat.id}.`);
    if (value === null) {
      if (row.stats.delete(stat.id)) {
        row.version++;
        this.writes.push({ id, field: `stat:${stat.id}`, value: null });
      }
      return this.state(id);
    }
    const fits =
      def.type === 'bool'
        ? typeof value === 'boolean'
        : def.type === 'int'
          ? Number.isInteger(value)
          : def.type === 'text'
            ? typeof value === 'string'
            : typeof value === 'string' && def.enumValues.includes(value);
    if (!fits) throw new RefusedError(`That is not a ${def.type} value for ${def.name}.`);
    if (row.stats.get(stat.id) !== value) {
      row.stats.set(stat.id, value);
      row.version++;
      this.writes.push({ id, field: `stat:${stat.id}`, value });
    }
    return this.state(id);
  }

  private findText(payloadId: string): { text: Text; label: 'description' | 'note.text' } {
    const id = payloadId.replace(/^p-/, '');
    for (const row of this.rows.values()) {
      if (row.description?.id === id) return { text: row.description, label: 'description' };
      const note = row.notes.find((n) => n.id === id);
      if (note) return { text: note, label: 'note.text' };
    }
    throw new RefusedError(`No payload ${payloadId}.`);
  }

  async createText(entryId: string, text: NewText) {
    this.need();
    const row = this.row(entryId);
    const known = [...this.rows.values()].flatMap((r) => [r.description, ...r.notes]);
    if (known.some((t) => t?.id === text.id)) return; // a replay
    if (this.heldElsewhere.has(text.id)) throw new RefusedError('That id is not available.');
    const made = { id: text.id, title: text.title, text: text.text, version: 1 };
    if (text.type === 'description') {
      if (row.description) throw new RefusedError('The entry already has a description.');
      row.description = made;
      this.writes.push({ id: entryId, field: 'description', value: text.text });
    } else {
      row.notes.push(made);
      this.writes.push({ id: entryId, field: 'note.add', value: text.text });
    }
  }
  async setText(payloadId: string, text: string, version: string | null) {
    this.need();
    const { text: target, label } = this.findText(payloadId);
    if (version !== null && version !== `"t${target.version}"`)
      throw new RefusedError('The text changed since it was read.', true);
    target.text = text;
    target.version++;
    this.writes.push({ id: target.id, field: label, value: text });
  }

  /** Someone else changes a description or a note, behind the person's back. */
  editTextElsewhere(entryId: string, which: 'description' | string, text: string) {
    const row = this.row(entryId);
    const target =
      which === 'description' ? row.description : row.notes.find((n) => n.id === which);
    if (!target) throw new Error(`No ${which} on ${entryId}.`);
    target.text = text;
    target.version++;
  }

  /** Someone else sets (or with null clears) an entry's own value for a stat, behind its back. */
  setStatElsewhere(id: string, statId: string, value: StatScalar | null) {
    const row = this.row(id);
    if (value === null) row.stats.delete(statId);
    else row.stats.set(statId, value);
    row.version++;
  }

  /** Someone else renames the entry, behind the person's back. */
  renameElsewhere(id: string, name: string) {
    const row = this.row(id);
    row.name = name;
    row.version++;
  }
}
