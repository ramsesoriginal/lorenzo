// The command layer's state: the mirror (what the server last said), the outbox (commands not
// yet sent), and the runner that sends them. What a person sees is the mirror with every command
// still in the outbox applied in order, so a change shows at once and cancelling one is just
// taking it out. Online-first: the outbox is in memory, it does not survive a closed tab (B4).

import {
  type Command,
  type CommandType,
  type CreateArgs,
  compare,
  inverseOf,
  REGISTRY,
  sameValue,
  usedIds,
  type Value,
} from './commands';
import {
  type EntryState,
  type EntrySummary,
  OfflineError,
  RefusedError,
  type Transport,
} from './transport';

export type EntryStatus = 'synced' | 'waiting' | 'offline' | 'conflict' | 'attention';

const HISTORY_LIMIT = 50;

export class Bench {
  /** The server's list of entries, as last read. */
  entries: EntrySummary[] = [];
  /** The mirror: entries as the server last said, by id. */
  private mirror = new Map<string, EntryState>();
  /** Every command that is not synced, in the order written. */
  outbox: Command[] = [];
  /** Commands that were sent, newest last: what undo reaches. */
  history: Command[] = [];
  /** The last send found no connection. */
  offline = false;
  loadError: string | null = null;
  private nextId = 1;
  private listeners = new Set<() => void>();
  private current: Promise<void> | null = null;
  private again = false;

  constructor(
    readonly transport: Transport,
    private readonly makeId: () => string = () => crypto.randomUUID(),
  ) {}

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
  private emit() {
    for (const fn of this.listeners) fn();
  }

  // ---- reading ----------------------------------------------------------------------------

  async loadEntries(): Promise<void> {
    try {
      this.entries = await this.transport.listEntries();
      this.loadError = null;
      this.offline = false;
    } catch (e) {
      this.loadError = e instanceof Error ? e.message : 'Could not load the entries.';
      if (e instanceof OfflineError) this.offline = true;
    }
    this.emit();
  }

  private pendingCreate(id: string): Command | undefined {
    return this.outbox.find((c) => c.type === 'entry.create' && c.entryId === id);
  }

  /** Brings an entry's detail into the mirror, unless it is there or not made yet. */
  async open(id: string): Promise<void> {
    if (this.mirror.has(id) || this.pendingCreate(id)) return;
    if (!this.entries.some((e) => e.id === id)) return;
    try {
      this.mirror.set(id, await this.transport.getEntry(id));
      this.loadError = null;
    } catch (e) {
      this.loadError = e instanceof Error ? e.message : 'Could not load this entry.';
    }
    this.emit();
  }

  /** The entry as the person sees it: the mirror with its pending commands applied. */
  view(id: string): EntryState | null {
    let base = this.mirror.get(id) ?? null;
    if (!base) {
      const create = this.pendingCreate(id);
      if (!create) return null;
      base = {
        id,
        name: '',
        kinds: create.args?.kinds ?? [],
        parentIds: create.args?.parents ?? [],
        childIds: [],
        etag: null,
      };
    }
    return this.outbox
      .filter((c) => c.entryId === id)
      .reduce((entry, c) => REGISTRY[c.type].apply(entry, c.mine), base);
  }

  /** Every entry, the server's and those not made yet, by name. */
  listing(): EntrySummary[] {
    const made = new Set(this.entries.map((e) => e.id));
    const pending = this.outbox
      .filter((c) => c.type === 'entry.create' && !made.has(c.entryId))
      .map((c) => ({ id: c.entryId, name: '', kinds: c.args?.kinds ?? [] }));
    return [...this.entries, ...pending]
      .map((e) => ({ ...e, name: this.displayName(e.id) }))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
  }

  kindsOf(id: string): string[] {
    return this.view(id)?.kinds ?? this.entries.find((e) => e.id === id)?.kinds ?? [];
  }

  displayName(id: string): string {
    return this.view(id)?.name ?? this.entries.find((e) => e.id === id)?.name ?? id;
  }

  /** The entries under this one: what the server lists, and those made here not yet sent. */
  childrenOf(id: string): string[] {
    const ids = new Set(this.mirror.get(id)?.childIds ?? []);
    for (const c of this.outbox)
      if (c.type === 'entry.create' && this.view(c.entryId)?.parentIds.includes(id))
        ids.add(c.entryId);
    return [...ids];
  }

  commandsFor(id: string): Command[] {
    return this.outbox.filter((c) => c.entryId === id);
  }

  status(id: string): EntryStatus {
    const cs = this.commandsFor(id);
    if (cs.some((c) => c.state === 'attention')) return 'attention';
    if (cs.some((c) => c.state === 'conflict')) return 'conflict';
    if (cs.length) return this.offline ? 'offline' : 'waiting';
    return 'synced';
  }

  // ---- writing ----------------------------------------------------------------------------

  /** Makes a new entry under an id of its own, and returns the id. It shows at once. */
  create(draft: { name: string; kinds: string[]; parents: string[] }): string {
    const id = this.makeId();
    const args: CreateArgs = { kinds: [...draft.kinds], parents: [...draft.parents] };
    this.outbox.push({
      id: this.nextId++,
      type: 'entry.create',
      version: 1,
      entryId: id,
      base: '',
      mine: draft.name,
      state: 'waiting',
      args,
    });
    this.emit();
    queueMicrotask(() => void this.run());
    return id;
  }

  /** Writes a change down and starts sending. Nothing happens if it changes nothing. */
  change(type: Exclude<CommandType, 'entry.create'>, entryId: string, mine: Value): Command | null {
    const entry = this.view(entryId);
    if (!entry) return null;
    const base = REGISTRY[type].read(entry);
    if (sameValue(base, mine)) return null;
    const command: Command = {
      id: this.nextId++,
      type,
      version: 1,
      entryId,
      base,
      mine,
      state: 'waiting',
    };
    this.outbox.push(command);
    this.emit();
    queueMicrotask(() => void this.run());
    return command;
  }

  /**
   * Takes a command that has not been sent out of the outbox. Cancelling a create takes with it
   * everything that waits on the entry it would have made.
   */
  cancel(commandId: number) {
    const c = this.outbox.find((x) => x.id === commandId);
    if (!c || c.state === 'sending') return;
    const gone =
      c.type === 'entry.create'
        ? this.outbox.filter((x) => x === c || usedIds(x).includes(c.entryId))
        : [c];
    if (gone.some((x) => x.state === 'sending')) return;
    this.outbox = this.outbox.filter((x) => !gone.includes(x));
    this.emit();
  }

  /** Undoes the entry's latest change: cancels it if waiting, else queues its inverse. */
  undo(entryId: string): boolean {
    const waiting = [...this.outbox]
      .reverse()
      .find((c) => c.entryId === entryId && c.state === 'waiting');
    if (waiting) {
      this.cancel(waiting.id);
      return true;
    }
    if (this.commandsFor(entryId).length) return false;
    const last = [...this.history].reverse().find((c) => c.entryId === entryId);
    const inv = last && inverseOf(last);
    if (!last || !inv || inv.type === 'entry.create') return false;
    this.history.splice(this.history.indexOf(last), 1);
    this.change(inv.type, inv.entryId, inv.mine);
    return true;
  }

  canUndo(entryId: string): boolean {
    if (this.outbox.some((c) => c.entryId === entryId && c.state === 'waiting')) return true;
    if (this.commandsFor(entryId).length) return false;
    const last = [...this.history].reverse().find((c) => c.entryId === entryId);
    return !!last && inverseOf(last) !== null;
  }

  /** A conflict resolved in favour of the person's own value: it is sent over theirs. */
  keepMine(commandId: number) {
    const c = this.outbox.find((x) => x.id === commandId);
    if (c?.state !== 'conflict' || c.theirs === undefined) return;
    c.base = c.theirs;
    c.theirs = undefined;
    c.state = 'waiting';
    this.emit();
    queueMicrotask(() => void this.run());
  }

  /** A conflict or a refused command given up: the server's value stands. */
  discard(commandId: number) {
    const c = this.outbox.find((x) => x.id === commandId);
    if (!c || c.state === 'sending' || c.state === 'waiting') return;
    // A create given up takes what waits on it with it.
    const gone =
      c.type === 'entry.create'
        ? this.outbox.filter((x) => x === c || usedIds(x).includes(c.entryId))
        : [c];
    this.outbox = this.outbox.filter((x) => !gone.includes(x));
    this.emit();
  }

  retry(commandId: number) {
    const c = this.outbox.find((x) => x.id === commandId);
    if (c?.state !== 'attention') return;
    c.state = 'waiting';
    c.error = undefined;
    this.emit();
    queueMicrotask(() => void this.run());
  }

  // ---- the runner -------------------------------------------------------------------------

  /**
   * Sends what is waiting, one command at a time, in the order written. Resolves when nothing
   * more can be sent now; called while a run is going, it joins that run.
   */
  run(): Promise<void> {
    if (this.current) {
      this.again = true;
      return this.current;
    }
    this.current = this.loop().finally(() => {
      this.current = null;
      this.emit();
    });
    return this.current;
  }

  private async loop(): Promise<void> {
    do {
      this.again = false;
      for (let next = this.nextToSend(); next; next = this.nextToSend()) {
        const stop = await this.send(next);
        if (stop) break;
      }
    } while (this.again);
  }

  /**
   * The first waiting command that can go: nothing earlier on its entry is stuck, and every
   * entry it needs (its own, and the parents it names) has been made.
   */
  private nextToSend(): Command | undefined {
    return this.outbox.find((c, i) => {
      if (c.state !== 'waiting') return false;
      const before = this.outbox.slice(0, i);
      const stuck = before.some(
        (p) => p.entryId === c.entryId && (p.state === 'conflict' || p.state === 'attention'),
      );
      const needs = usedIds(c);
      const unmade = before.some((p) => p.type === 'entry.create' && needs.includes(p.entryId));
      return !stuck && !unmade;
    });
  }

  /** Returns true when the runner should stop (there is no connection). */
  private async send(c: Command): Promise<boolean> {
    c.state = 'sending';
    this.emit();
    try {
      if (c.type === 'entry.create') await this.sendCreate(c);
      else await this.sendChange(c);
      return false;
    } catch (e) {
      if (e instanceof OfflineError) {
        c.state = 'waiting';
        this.offline = true;
        return true;
      }
      c.state = 'attention';
      c.error = e instanceof Error ? e.message : 'The server refused this change.';
      return false;
    }
  }

  private async sendCreate(c: Command) {
    const made = await this.transport.createEntry({
      id: c.entryId,
      name: c.mine as string,
      kinds: c.args?.kinds ?? [],
      parents: c.args?.parents ?? [],
    });
    this.mirror.set(c.entryId, made);
    // The server's list now has it, and its parents have a new child.
    this.entries = [
      ...this.entries.filter((e) => e.id !== c.entryId),
      { id: made.id, name: made.name, kinds: made.kinds },
    ];
    for (const parentId of made.parentIds) {
      const parent = this.mirror.get(parentId);
      if (parent && !parent.childIds.includes(c.entryId))
        this.mirror.set(parentId, { ...parent, childIds: [...parent.childIds, c.entryId] });
    }
    this.finish(c);
  }

  private async sendChange(c: Command) {
    const def = REGISTRY[c.type];
    for (let attempt = 0; attempt < 2; attempt++) {
      const server = await this.transport.getEntry(c.entryId);
      this.mirror.set(c.entryId, server);
      const verdict = compare(c.base, c.mine, def.read(server));
      if (verdict === 'conflict') {
        c.state = 'conflict';
        c.theirs = def.read(server);
        return;
      }
      if (verdict === 'send') {
        try {
          this.mirror.set(c.entryId, await def.send(this.transport, server, c.mine));
        } catch (e) {
          // The entry changed between the read and the write: read it again once.
          if (e instanceof RefusedError && e.precondition && attempt === 0) continue;
          throw e;
        }
      }
      this.finish(c);
      return;
    }
    throw new RefusedError(`This ${def.label} kept changing while it was being saved.`);
  }

  private finish(c: Command) {
    this.offline = false;
    c.state = 'synced';
    this.outbox.splice(this.outbox.indexOf(c), 1);
    this.history.push(c);
    if (this.history.length > HISTORY_LIMIT) this.history.shift();
    // A rename is in the list too.
    const entry = this.mirror.get(c.entryId);
    const row = this.entries.find((e) => e.id === c.entryId);
    if (entry && row) row.name = entry.name;
    this.emit();
  }
}
