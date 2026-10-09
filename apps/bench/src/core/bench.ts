// The command layer's state: the mirror (what the server last said), the outbox (commands not
// yet sent), and the runner that sends them. What a person sees is the mirror with every command
// still in the outbox applied in order, so a change shows at once and cancelling one is just
// taking it out. Online-first: the outbox is in memory, it does not survive a closed tab (B4).

import {
  type Command,
  type CommandType,
  type CreateArgs,
  compare,
  docOf,
  inverseOf,
  makesId,
  REGISTRY,
  sameValue,
  usedIds,
  type Value,
} from './commands';
import {
  canEditStat,
  type EntryState,
  type EntrySummary,
  OfflineError,
  RefusedError,
  type StatDef,
  type StatScalar,
  type Transport,
} from './transport';

export type EntryStatus = 'synced' | 'waiting' | 'offline' | 'conflict' | 'attention';

const HISTORY_LIMIT = 50;

export class Bench {
  /** The server's list of entries, as last read. */
  entries: EntrySummary[] = [];
  /** The stats the repository defines, as last read: what an entry can have a value for. */
  statDefs: StatDef[] = [];
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
      this.statDefs = await this.transport.listStatDefinitions();
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
        description: null,
        notes: [],
        stats: [],
        etag: null,
      };
    }
    return this.outbox
      .filter((c) => c.entryId === id)
      .reduce((entry, c) => REGISTRY[c.type].apply(entry, c.mine, c), base);
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
  change(
    type: Exclude<CommandType, 'entry.create' | 'note.add'>,
    entryId: string,
    mine: Value,
    ref?: string,
  ): Command | null {
    const entry = this.view(entryId);
    if (!entry) return null;
    const command: Command = {
      id: this.nextId++,
      type,
      version: 1,
      entryId,
      base: '',
      mine,
      state: 'waiting',
    };
    if (type === 'description.set-text') {
      // A description not there yet is made under an id of the client's own (ADR 0222).
      command.textId = entry.description?.id ?? this.makeId();
    } else if (type === 'note.set-text') {
      if (!ref || !entry.notes.some((n) => n.id === ref)) return null;
      command.textId = ref;
    } else if (type === 'stat.set') {
      const def = this.statDefs.find((d) => d.id === ref);
      if (!def || !canEditStat(def.type)) return null;
      command.stat = { id: def.id, name: def.name, type: def.type };
    }
    const base = REGISTRY[type].read(entry, command);
    if (sameValue(base, mine)) return null;
    command.base = base;
    this.outbox.push(command);
    this.emit();
    queueMicrotask(() => void this.run());
    return command;
  }

  /** Changes the text of the entry's description, making the description if there is none. */
  setDescription(entryId: string, text: string): Command | null {
    return this.change('description.set-text', entryId, text);
  }

  /** Changes the text of one of the entry's notes. */
  setNoteText(entryId: string, noteId: string, text: string): Command | null {
    return this.change('note.set-text', entryId, text, noteId);
  }

  /** Sets the entry's own value for a stat, or with `null` removes it so the entry inherits. */
  setStat(entryId: string, statId: string, value: StatScalar | null): Command | null {
    return this.change('stat.set', entryId, value, statId);
  }

  /** Adds a note to the entry, under an id of its own. It shows at once. */
  addNote(entryId: string, text: string): string | null {
    if (!this.view(entryId) || !text.trim()) return null;
    const noteId = this.makeId();
    this.outbox.push({
      id: this.nextId++,
      type: 'note.add',
      version: 1,
      entryId,
      base: '',
      mine: text,
      state: 'waiting',
      textId: noteId,
    });
    this.emit();
    queueMicrotask(() => void this.run());
    return noteId;
  }

  /**
   * Takes a command that has not been sent out of the outbox. Cancelling a create takes with it
   * everything that waits on what it would have made.
   */
  cancel(commandId: number) {
    const c = this.outbox.find((x) => x.id === commandId);
    if (!c || c.state === 'sending') return;
    const gone = this.withDependants(c);
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
    if (!last || !inv || inv.type === 'entry.create' || inv.type === 'note.add') return false;
    this.history.splice(this.history.indexOf(last), 1);
    this.change(inv.type, inv.entryId, inv.mine, inv.textId ?? inv.stat?.id);
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
    const gone = this.withDependants(c);
    this.outbox = this.outbox.filter((x) => !gone.includes(x));
    this.emit();
  }

  /** The command, and, if it makes an id, every command that waits on that id. */
  private withDependants(c: Command): Command[] {
    const made = makesId(c);
    return made ? this.outbox.filter((x) => x === c || usedIds(x).includes(made)) : [c];
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
      const unmade = before.some((p) => {
        const made = makesId(p);
        return made !== undefined && needs.includes(made);
      });
      return !stuck && !unmade;
    });
  }

  /** Returns true when the runner should stop (there is no connection). */
  private async send(c: Command): Promise<boolean> {
    c.state = 'sending';
    this.emit();
    try {
      if (c.type === 'entry.create') await this.sendCreate(c);
      else if (c.type === 'note.add') await this.sendNote(c);
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

  private async sendNote(c: Command) {
    await this.transport.createText(c.entryId, {
      id: c.textId as string,
      type: 'note',
      title: 'Note',
      text: c.mine as string,
    });
    this.mirror.set(c.entryId, await this.transport.getEntry(c.entryId));
    this.finish(c);
  }

  /** What the server has for the field this command changes: a text, or a name or parents. */
  private theirsOf(c: Command, server: EntryState): Value {
    if (c.type === 'description.set-text' || c.type === 'note.set-text')
      return docOf(server, c)?.text ?? '';
    return REGISTRY[c.type].read(server, c);
  }

  /** Sends a change of text: the three-way compare, then a write of the payload or a create. */
  private async writeText(c: Command, server: EntryState): Promise<void> {
    const doc = docOf(server, c);
    if (doc) {
      await this.transport.setText(doc.payloadId, c.mine as string, doc.version);
    } else if (c.type === 'description.set-text') {
      await this.transport.createText(c.entryId, {
        id: c.textId as string,
        type: 'description',
        title: 'Description',
        text: c.mine as string,
      });
    } else {
      throw new RefusedError('That note is no longer there.');
    }
    this.mirror.set(c.entryId, await this.transport.getEntry(c.entryId));
  }

  private async sendChange(c: Command) {
    const def = REGISTRY[c.type];
    const isText = c.type === 'description.set-text' || c.type === 'note.set-text';
    for (let attempt = 0; attempt < 2; attempt++) {
      const server = await this.transport.getEntry(c.entryId);
      this.mirror.set(c.entryId, server);
      if (c.type === 'note.set-text' && !docOf(server, c))
        throw new RefusedError('That note is no longer there.');
      const verdict = compare(c.base, c.mine, this.theirsOf(c, server));
      if (verdict === 'conflict') {
        c.state = 'conflict';
        c.theirs = this.theirsOf(c, server);
        return;
      }
      if (verdict === 'send') {
        try {
          if (isText) await this.writeText(c, server);
          else this.mirror.set(c.entryId, await def.send(this.transport, server, c.mine, c));
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
