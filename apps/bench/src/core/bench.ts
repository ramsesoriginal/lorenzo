// The command layer's state: the mirror (what the server last said), the outbox (commands not
// yet sent), and the runner that sends them. What a person sees is the mirror with every command
// still in the outbox applied in order, so a change shows at once and cancelling one is just
// taking it out. Online-first: the outbox is in memory, it does not survive a closed tab (B4).

import {
  type Command,
  type CommandType,
  compare,
  inverseOf,
  REGISTRY,
  sameValue,
  type Value,
} from './commands';
import {
  type EntrySummary,
  type ItemState,
  OfflineError,
  RefusedError,
  type Transport,
} from './transport';

export type EntryStatus = 'synced' | 'waiting' | 'offline' | 'conflict' | 'attention';

const HISTORY_LIMIT = 50;

export class Bench {
  entries: EntrySummary[] = [];
  /** The mirror: items as the server last said, by id. */
  private mirror = new Map<string, ItemState>();
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

  constructor(readonly transport: Transport) {}

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

  isItem(id: string): boolean {
    return this.entries.find((e) => e.id === id)?.kinds.includes('item') ?? false;
  }

  /** Brings an item's detail into the mirror, unless it is there. */
  async open(id: string): Promise<void> {
    if (this.mirror.has(id) || !this.isItem(id)) return;
    try {
      this.mirror.set(id, await this.transport.getItem(id));
      this.loadError = null;
    } catch (e) {
      this.loadError = e instanceof Error ? e.message : 'Could not load this entry.';
    }
    this.emit();
  }

  /** The item as the person sees it: the mirror with its pending commands applied. */
  view(id: string): ItemState | null {
    const base = this.mirror.get(id);
    if (!base) return null;
    return this.outbox
      .filter((c) => c.entryId === id)
      .reduce((item, c) => REGISTRY[c.type].apply(item, c.mine), base);
  }

  displayName(id: string): string {
    return this.view(id)?.name ?? this.entries.find((e) => e.id === id)?.name ?? id;
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

  /** Writes a change down and starts sending. Nothing happens if it changes nothing. */
  change(type: CommandType, entryId: string, mine: Value): Command | null {
    const item = this.view(entryId);
    if (!item) return null;
    const base = REGISTRY[type].read(item);
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

  /** Takes a command that has not been sent out of the outbox. */
  cancel(commandId: number) {
    const i = this.outbox.findIndex((c) => c.id === commandId);
    if (i < 0 || this.outbox[i].state === 'sending') return;
    this.outbox.splice(i, 1);
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
    if (!last) return false;
    this.history.splice(this.history.indexOf(last), 1);
    const inv = inverseOf(last);
    this.change(inv.type, inv.entryId, inv.mine);
    return true;
  }

  canUndo(entryId: string): boolean {
    return (
      this.outbox.some((c) => c.entryId === entryId && c.state === 'waiting') ||
      (this.commandsFor(entryId).length === 0 && this.history.some((c) => c.entryId === entryId))
    );
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
    this.outbox.splice(this.outbox.indexOf(c), 1);
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

  /** The first waiting command whose entry has no earlier command that is stuck. */
  private nextToSend(): Command | undefined {
    return this.outbox.find(
      (c, i) =>
        c.state === 'waiting' &&
        !this.outbox
          .slice(0, i)
          .some(
            (p) => p.entryId === c.entryId && (p.state === 'conflict' || p.state === 'attention'),
          ),
    );
  }

  /** Returns true when the runner should stop (there is no connection). */
  private async send(c: Command): Promise<boolean> {
    const def = REGISTRY[c.type];
    c.state = 'sending';
    this.emit();
    try {
      for (let attempt = 0; attempt < 2; attempt++) {
        const server = await this.transport.getItem(c.entryId);
        this.mirror.set(c.entryId, server);
        const verdict = compare(c.base, c.mine, def.read(server));
        if (verdict === 'conflict') {
          c.state = 'conflict';
          c.theirs = def.read(server);
          return false;
        }
        if (verdict === 'send') {
          try {
            this.mirror.set(c.entryId, await def.send(this.transport, server, c.mine));
          } catch (e) {
            // The item changed between the read and the write: read it again once.
            if (e instanceof RefusedError && e.precondition && attempt === 0) continue;
            throw e;
          }
        }
        this.finish(c);
        return false;
      }
      throw new RefusedError(`This ${def.label} kept changing while it was being saved.`);
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

  private finish(c: Command) {
    this.offline = false;
    c.state = 'synced';
    this.outbox.splice(this.outbox.indexOf(c), 1);
    this.history.push(c);
    if (this.history.length > HISTORY_LIMIT) this.history.shift();
    // A rename is in the list too.
    const item = this.mirror.get(c.entryId);
    const row = this.entries.find((e) => e.id === c.entryId);
    if (item && row) row.name = item.name;
    this.emit();
  }
}
